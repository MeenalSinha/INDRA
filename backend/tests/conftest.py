import os
import tempfile

# Respect an already-exported DATABASE_URL (e.g. pointing this suite at a
# real Postgres/PostGIS instance to prove backend portability) -- only
# fall back to an isolated temp SQLite file when nothing is set.
if "DATABASE_URL" not in os.environ:
    _tmp_dir = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test_indra.db"
