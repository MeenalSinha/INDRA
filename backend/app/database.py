from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from . import config

connect_args = {"check_same_thread": False} if not config.IS_POSTGRES else {}
# §8 Perf fix: handle high concurrency without QueuePool exhaustion.
kwargs = {"pool_size": 100, "max_overflow": 200}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args, **kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema():
    """
    `Base.metadata.create_all()` only creates tables that don't exist yet --
    it never alters an existing table. That's fine for a brand-new SQLite
    file, but it silently breaks a demo database left over from an earlier
    version of the code the moment a new column is added to a model (every
    INSERT starts failing with "table X has no column named Y"). Since this
    prototype has no formal migration tool (Alembic would be the Live Mode
    answer), this does the minimum safe thing for SQLite: diff each
    declared model's columns against what's actually in the table and
    ALTER TABLE ADD COLUMN for anything missing. Postgres/Live Mode is
    expected to run real migrations instead, so this is a no-op there.

    §6 upgrade: also calls create_all() first so that genuinely new tables
    (like `users`) are created even against an existing database -- create_all
    is idempotent (checkfirst is the default).
    """
    # Create any new tables that don't exist yet (idempotent / checkfirst).
    Base.metadata.create_all(bind=engine)

    if config.IS_POSTGRES:
        return
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default_clause = ""
                if column.default is not None and getattr(column.default, "is_scalar", False):
                    val = column.default.arg
                    if isinstance(val, bool):
                        default_clause = f" DEFAULT {int(val)}"
                    elif isinstance(val, (int, float)):
                        default_clause = f" DEFAULT {val}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_clause}'))

            # Missing indexes on existing tables (same drift problem as
            # columns above -- create_all() only creates indexes for
            # brand-new tables, never retrofits an existing one). This
            # must run per-table inside the loop above, not after it --
            # an earlier version of this left it outside the loop, so it
            # only ever checked the last table in sorted_tables.
            existing_index_names = {ix["name"] for ix in inspector.get_indexes(table.name)}
            for index in table.indexes:
                if index.name in existing_index_names:
                    continue
                try:
                    index.create(bind=conn, checkfirst=True)
                except Exception:
                    pass  # best-effort; a failed index create should never block startup
