# Meshing_BE

FastAPI backend for the Meshing 2D platform. It owns authentication, geometry CRUD, PSLG normalization, meshing engines, mesh exports, realtime dashboard events, and 2D FEA solving.

## Capabilities

- Geometry primitives: rectangle, circle, triangle, polygon.
- Geometry records: create, list, get, delete, plus Boolean CSG (`union`, `subtract`, `intersect`) with disconnected multi-component output preserved end to end.
- PSLG processing: duplicate point cleanup, outer-loop CCW normalization, hole-loop CW normalization, and self-intersection validation.
- Meshing:
  - `Q4`: mapped structured grid for axis-aligned rectangular components.
  - `T3`: native `BuildDelaunay` path with quad-edge divide-and-conquer, InCircle checks, PSLG domain filtering, encroached-segment splitting, adaptive size field, Laplacian smoothing, and quality refinement.
- Dashboard analysis: DOF, mesh quality, element-size distribution, empty-circumcircle check, `nodes_matrix`, `edges_matrix`, `tris_matrix`.
- FEA: plane stress / plane strain, sparse stiffness assembly, nodal/line loads, Dirichlet BC, reactions, stress/strain/Von Mises recovery.
- Exports: `json`, `dat`, full `csv`, and `csv_zip`.

## Quick Start

```bash
make install
cp env.example .env
# Edit .env before running: DB_*, JWT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
make up
make run
```

Swagger UI: `http://localhost:8000/docs`

## Important API Notes

- Protected endpoints require `Authorization: Bearer <access_token>`.
- FEA request `node_id` values are 0-based.
- Mesh response connectivity (`elements`) is always 0-based for both `Q4` and `T3`.
- Polygon mesh responses apply viewport-safe bounds padding to avoid extreme auto-zoom on tiny coordinate ranges.
- Q4 meshing accepts only axis-aligned rectangular components and does not support holes.

- Delaunay multi-component meshing keeps disconnected domains in a single mesh response and dashboard payload.
- Delaunay mesh elements are normalized before FEA so T3 elements are non-degenerate and CCW.
- `format=csv` returns one full mesh CSV; `format=csv_zip` returns separate `nodes.csv` and `elements.csv`.
- Existing PostgreSQL databases created before `triangle` support may need enum upgrade; `init_db()` attempts to add it automatically.

## Main Endpoints

| Area | Endpoint |
|---|---|
| Health | `GET /api/health`, `GET /api/health/db` |
| Auth | `GET /api/auth/google/url`, `POST /api/auth/callback`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Geometry | `POST /api/geometry/rectangle`, `/circle`, `/triangle`, `/polygon`, `/boolean`; `GET /api/geometry`; `GET/DELETE /api/geometry/{id}` |
| Mesh | `POST /api/mesh/quad`, `/delaunay`, `/from-sketch`; `GET/DELETE /api/mesh/{id}`; `GET /api/mesh/{id}/export` |
| FEA | `POST /api/fea/solve` |
| Realtime | `WS /api/ws/dashboard` |

## Validation Commands

```bash
.venv/bin/ruff check app tests
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_cantilever_benchmark.py
```

Optional 10k-element performance gate:

```bash
RUN_PERFORMANCE_BENCHMARK=1 .venv/bin/python -m pytest -q tests/test_performance_benchmark.py -s
```

## Pre-push Checklist

```bash
make ci
.venv/bin/python scripts/run_cantilever_benchmark.py
git --no-pager status --short --ignored
```

## Cantilever Accuracy Benchmark

Release evidence is generated from Section IV parameters of the reference paper:

- `P=10 kN`, `L=10 m`, `h=1 m`, `nu=0.3`, `E=2e11 N/m^2`, `thickness=1 m`.
- Exact neutral-axis curve: `v(x)=P*x^2*(3L-x)/(6EI)`, `I=t*h^3/12`.
- Exact tip deflection: `-2.0e-4 m`.

Generated artifacts:

- `docs/cantilever-benchmark-report-2026-04-28.md`
- `docs/cantilever-benchmark-2026-04-28.csv`

The paper uses LST/T6 elements. This backend validates the same beam problem with the supported T3/Q4 elements and records that assumption in the report.

## Environment

Use `env.example` as the source of truth. Never commit `.env` or real OAuth/JWT secrets.

## Project Structure

```txt
app/api/          FastAPI routes
app/core/         settings and security helpers
app/database/     SQLAlchemy models/session
app/engines/      PSLG, meshing, Delaunay, FEA engines
app/schemas/      request/response contracts
app/services/     business services and persistence orchestration
tests/            backend regression/integration tests
scripts/          local release/benchmark helpers
docs/             benchmark reports intended for submission evidence
```
