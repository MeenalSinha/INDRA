# INDRA — Limitations

Honest, current as of this upgrade round. See `docs/INDRA_AUDIT.md` and
`docs/UPGRADE_AUDIT.md` for the full evidence behind each of these.

## Infrastructure not verified end-to-end

- **Docker Compose has not been run** (`docker compose up --build`) in
  the environment this was built in — no Docker daemon was available
  there. The compose file, both Dockerfiles, and the migration
  entrypoint script are reviewed for correctness; their component parts
  (Postgres+PostGIS, Redis, the Alembic migrations) were each verified
  working against real local installations *outside* of Docker.
- **Kafka/Redpanda and MinIO have not been installed or tested at all**
  in this project's build environment — neither is an apt package, and
  their upstream binary distributions are not reachable from a sandbox
  restricted to package-registry mirrors (PyPI, npm, apt, GitHub
  releases). The in-process pub/sub bus and local-disk object storage
  are the genuinely-tested Demo Mode substitutes.

## Infrastructure that IS now verified (as of this upgrade)

- **PostgreSQL 16 + PostGIS 3.4**: real, running, migrated via Alembic
  from an empty database, seeded, and exercised through the full golden
  scenario (Judge Mode → fusion → verification → audit log) — all
  passing identically to SQLite Demo Mode. 34/34 backend tests also pass
  against it directly.
- **Redis**: real, running, backing the rate limiter — confirmed via
  direct `redis-cli` inspection that the actual counter key exists and
  increments, not the in-memory fallback.
- **PostGIS spatial queries**: `ST_DWithin` over a `geography` cast,
  backed by a real GIST index — confirmed correct results and confirmed
  the index exists via `pg_indexes`. (At the current ~9-107 row table
  sizes, Postgres's planner correctly chooses a sequential scan over the
  index — expected, correct behavior for small tables, not a defect.)

## Performance

- Demo Mode's per-insert clustering and duplicate-detection candidate
  queries are now spatially pre-filtered (this upgrade), which measurably
  flattened the latency-growth curve found in the previous audit (22ms→
  65ms became a stable 20-34ms band over 2,000 sequential reports; total
  time for the same run dropped 40%). This does not extend to arbitrary
  scale — it was not tested past ~2,000-4,000 concentrated reports in a
  single run, and Postgres query-planning behavior at much larger table
  sizes (where the GIST/B-tree indexes would actually get chosen over
  sequential scans) has not been measured.
- Judge Mode (125 reports) and normal interactive use are unaffected by
  any of this either way — the finding only matters for bulk historical
  dataset import via sequential individual API calls.

## Security

- JWT auth (ADMIN/ANALYST/VIEWER) and the admin-token abstraction are
  both off by default and additive to each other — a deployment can
  enable either, both, or neither. Neither has been tested under
  concurrent/adversarial load (e.g. token replay, timing attacks);
  this is a demo-grade auth layer, explicitly scoped as "do not
  overcomplicate authentication" per the upgrade instructions, not a
  production-hardened identity system.
- Demo account passwords in `.env.example` are placeholder values meant
  to be overridden — they are not secrets, but a deployment that doesn't
  override them is not meaningfully protected.

## Source adapters

Pipeline/schema adapters, not live external API pollers — by design, so
the core demo needs no external credentials. Real IMD/social-media API
integration remains future scope.

## Frontend

Hand-written HTML/CSS/vanilla JS rather than the React/Next.js/shadcn
stack mentioned as a target in the upgrade instructions. This was a
deliberate scoping decision: the instructions' own first rule is "do not
rewrite the project from scratch," and the current frontend already
meets the functional requirements (real API/WebSocket wiring, matches
the approved visual direction) and passed its own audit round. A
framework migration was judged not to be "preserve the working core."

## Testing

No browser-based visual regression or accessibility audit has been
performed (keyboard navigation, screen-reader labels, contrast ratios
were reviewed by inspection of the CSS/markup, not measured with
automated tooling).
