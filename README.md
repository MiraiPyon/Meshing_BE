# Meshing_BE

Backend API cho nền tảng Web mô phỏng **Meshing 2D đa phương thức** và **Dashboard quản lý chất lượng phần tử hữu hạn**.

Hệ thống hỗ trợ luồng:
- Khởi tạo hình học từ primitive, boolean CSG, sketch/PSLG, hoặc `shape.dat`
- Chia lưới `T3` và `Q4`
- Dashboard realtime với thống kê nút/phần tử, chất lượng lưới và ma trận connectivity
- Lưu project snapshot và export dữ liệu cho solver bên ngoài
- Giải FEA 2D với plane stress / plane strain

---

## Tổng Quan

### Geometry Modeling
- Primitive: `Rectangle`, `Circle`, `Polygon`
- Boolean CSG: `union`, `subtract`, `intersect`
- Sketch to PSLG: chuẩn hóa biên ngoài / biên trong, loại điểm trùng, kiểm tra tự cắt
- `shape.dat`: hỗ trợ `OUTER`, `HOLE`, `END`

### Meshing Engine
- `Q4` structured mesh cho hình chữ nhật
- `T3` Delaunay mesh cho PSLG/phức tạp hơn
- Refinement theo `min_angle`, `max_area`, `max_edge_length`
- Kiểm tra chất lượng: `theta_min`, `circumradius / shortest edge`, empty circumcircle

### Dashboard & Analysis
- `node_count`, `element_count`, `dof_total`
- `mesh_quality` metrics
- `nodes_matrix`, `edges_matrix`, `tris_matrix`
- WebSocket realtime cho dashboard

### Project & Export
- Project snapshot CRUD theo user
- Export mesh: `json`, `dat`, `csv` legacy, `csv_zip` chuẩn mới, `shape`
- `csv_zip` chứa cả `nodes.csv` và `elements.csv`

### FEA
- Plane stress / plane strain
- Linear elastic 2D
- Assembly sparse, giải `K·u = F`
- Stress / strain recovery, Von Mises, benchmark cantilever

---

## Tech Stack

- FastAPI
- PostgreSQL + SQLAlchemy
- Pydantic v2 / pydantic-settings
- NumPy, SciPy
- Shapely
- WebSocket realtime

---

## API Contracts Quan Trọng

- FEA request dùng `node_id` dạng **0-based**
- Quad mesh chỉ hỗ trợ **axis-aligned rectangle**, không hỗ trợ holes
- Boolean CSG có thể trả về **nhiều component**
- `format=csv` là legacy nodes-only export
- `format=csv_zip` là format được khuyến nghị cho solver
- WebSocket dashboard: `/api/ws/dashboard`

### Boolean CSG Response

Khi kết quả boolean rời rạc, backend trả thêm:
- `components`
- `component_count`
- `total_area`
- `is_multipolygon`

Field cũ vẫn giữ để tương thích ngược:
- `outer_boundary`
- `holes`
- `area`
- `num_vertices`

---

## Quick Start

### 1. Chuẩn bị môi trường

```sh
make install
make bootstrap-env
cp docker/.env.example docker/.env
```

`make bootstrap-env` tạo `.env` ở project root từ `env.example`.
`docker/.env` là file Docker Compose dùng cho `make up`.

### 2. Chạy database

```sh
make up
```

### 3. Chạy API

```sh
make run
```

Mở Swagger UI:

```txt
http://localhost:8000/docs
```

### 4. Dừng dịch vụ

```sh
make down
```

---

## Auth Flow

```txt
1. GET /api/auth/google/url
2. Đăng nhập Google
3. Google redirect về /api/auth/callback?code=...
4. POST /api/auth/callback {code}
5. Dùng Authorization: Bearer <access_token> cho API protected
6. Hết hạn thì POST /api/auth/refresh {refresh_token}
```

---

## API Endpoints

### Public

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/health` | Health check |
| GET | `/api/health/db` | Database health check |
| GET | `/api/auth/google/url` | Lấy Google OAuth URL |
| GET | `/api/auth/callback?code=...` | OAuth callback cho test / không có frontend |
| POST | `/api/auth/callback` | Đổi Google code lấy JWT |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/me` | User hiện tại |

### Geometry

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/geometry/rectangle` | Tạo rectangle |
| POST | `/api/geometry/circle` | Tạo circle |
| POST | `/api/geometry/polygon` | Tạo polygon |
| POST | `/api/geometry/boolean` | Boolean CSG |
| GET | `/api/geometry/{id}` | Lấy geometry |
| GET | `/api/geometry` | List geometry của user |
| DELETE | `/api/geometry/{id}` | Xóa geometry |

### Mesh

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/mesh/quad` | Tạo Q4 mesh |
| POST | `/api/mesh/delaunay` | Tạo T3 mesh |
| POST | `/api/mesh/from-sketch` | Sketch / PSLG → geometry + mesh |
| POST | `/api/mesh/from-shape-dat` | Tạo mesh từ `shape.dat` |
| GET | `/api/mesh/{id}` | Lấy mesh |
| GET | `/api/mesh` | List mesh của user |
| GET | `/api/mesh/{id}/export?format=json\|dat\|csv\|csv_zip\|shape` | Export mesh |
| DELETE | `/api/mesh/{id}` | Xóa mesh |

### Projects

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/projects` | Tạo project snapshot |
| GET | `/api/projects` | List project snapshots |
| GET | `/api/projects/{id}` | Lấy project snapshot |
| PUT | `/api/projects/{id}` | Cập nhật project snapshot |
| DELETE | `/api/projects/{id}` | Xóa project snapshot |

### FEA

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/fea/solve` | Giải bài toán FEA |

### Realtime

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| WS | `/api/ws/dashboard` | Observer realtime cho mesh events |

---

## Ví Dụ Sử Dụng

### 1. Rectangle → Quad mesh → FEA

```bash
# Login
curl -X POST http://localhost:8000/api/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code":"<google_auth_code>"}'

# Tạo rectangle
curl -X POST http://localhost:8000/api/geometry/rectangle \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Beam","x_min":0,"y_min":0,"width":1,"height":0.2}'

# Tạo quad mesh
curl -X POST http://localhost:8000/api/mesh/quad \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"geometry_id":"<uuid>","nx":10,"ny":4}'

# Giải FEA
curl -X POST http://localhost:8000/api/fea/solve \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mesh_id":"<uuid>",
    "material":{"E":210000000000,"nu":0.3,"thickness":0.01},
    "analysis_type":"plane_stress",
    "boundary_conditions":[
      {"node_id":0,"dof":"ux","value":0},
      {"node_id":0,"dof":"uy","value":0}
    ],
    "nodal_forces":[
      {"node_id":33,"dof":"fy","value":-1000}
    ]
  }'
```

### 2. Sketch / shape.dat → Delaunay mesh

```bash
curl -X POST http://localhost:8000/api/mesh/from-shape-dat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"plate_with_hole",
    "shape_dat":"OUTER\n0 0\n5 0\n5 3\n0 3\nEND\nHOLE\n1 1\n2 1\n2 2\n1 2\nEND",
    "max_area":0.05,
    "min_angle":20.7,
    "max_edge_length":0.4
  }'
```

### 3. Boolean CSG

```bash
curl -X POST http://localhost:8000/api/geometry/boolean \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"disjoint_union",
    "operation":"union",
    "polygon_a":[[0,0],[1,0],[1,1],[0,1]],
    "polygon_b":[[3,0],[4,0],[4,1],[3,1]]
  }'
```

Kết quả boolean rời rạc sẽ có `components` để frontend chọn component cần meshing.

---

## Environment Variables

### Root `.env`

```sh
POSTGRES_URL=postgresql://admin:change-this-password@db:5432/meshing_db
DB_USER=admin
DB_PASS=change-this-password
DB_NAME=meshing_db
DB_PORT=5432
DB_HOST=db

APP_NAME=FEA 2D Meshing API
DEBUG=true

JWT_SECRET=replace-with-your-jwt-secret
GOOGLE_CLIENT_ID=replace-with-your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=replace-with-your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

### Docker `docker/.env`

```sh
DB_USER=admin
DB_PASS=change-this-password
DB_NAME=meshing_db
DB_PORT=5432
DB_HOST=localhost
POSTGRES_URL=postgresql+psycopg://admin:change-this-password@localhost:5432/meshing_db
PGADMIN_EMAIL=admin@meshing.local
PGADMIN_PASS=change-this-password
```

---

## Useful Commands

| Command | Mô tả |
|--------|-------|
| `make test` | Chạy toàn bộ test |
| `make test-fea` | Chạy nhóm test FEA |
| `make test-fea-stress` | Chạy nhóm FEA 5 lần |
| `make test-stress` | Chạy toàn bộ test 5 lần |
| `make lint` | Ruff lint |
| `make format` | Black format |
| `make check` | Lint + test |
| `make secret-scan` | Quét secret trong staged changes |
| `make ci` | Secret scan + lint + test |
| `make hooks` | Bật git hooks |
| `make up` | Start PostgreSQL / PGAdmin |
| `make down` | Stop Docker services |
| `make run` | Chạy API server |
| `make run-alt` | Chạy API server ở port 8001 |

---

## Validation

Các mục dưới đây đã được kiểm tra trong repo hiện tại:
- Full regression suite
- Ruff lint
- Benchmark 10k phần tử Q4 bằng test opt-in

Chạy benchmark:

```sh
RUN_PERFORMANCE_BENCHMARK=1 .venv/bin/python -m pytest -q tests/test_performance_benchmark.py
```

Có thể override ngưỡng bằng:

```sh
PERF_NX=100 PERF_NY=100 PERF_MAX_MESH_S=2.0 PERF_MAX_ASSEMBLE_S=10.0 PERF_MAX_SOLVE_S=5.0 PERF_MAX_TOTAL_S=20.0
```

---

## Project Structure

```text
Meshing_BE/
├── app/
│   ├── api/           # REST API + WebSocket
│   ├── core/          # Settings + dependencies
│   ├── database/      # SQLAlchemy models/session
│   ├── engines/       # Geometry, meshing, FEA engines
│   ├── schemas/       # Pydantic request/response models
│   └── services/      # Business logic
├── docker/            # Docker Compose + env example
├── scripts/           # Bootstrap + secret scan scripts
├── tests/             # Regression + benchmark tests
└── Makefile
```
