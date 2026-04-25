# Meshing_BE

Backend API cho bài toán **tạo lưới (Meshing)** và **phân tích phần tử hữu hạn (FEA)** 2D. Xác thực qua **Google OAuth2 → JWT**.

---

## Tính năng

### Auth
- Đăng nhập qua **Google OAuth2**, trả về **JWT access + refresh tokens**
- Mỗi user chỉ thấy data của mình (ownership isolation)

### Meshing
- Tạo hình học: **Rectangle**, **Circle**, **Polygon**
- Chia lưới **Quad** (structured grid) — chỉ hỗ trợ hình chữ nhật
- Chia lưới **Tam giác** (Delaunay triangulation) — hỗ trợ mọi hình

### FEA 2D
- **Định luật Hooke** — plane stress và plane strain
- **Shape functions** — tam giác tuyến tính (3 nút) + tứ giác song tuyến tính (4 nút)
- **Gaussian Quadrature** — 1pt, 3pt, 7pt (tam giác) / 2×2, 3×3 (tứ giác)
- **Ma trận độ cứng** phần tử → lắp ráp tổng thể K (sparse)
- **Giải K·u = F** — Dirichlet + Neumann BC (elimination method)
- **Stress recovery** — ε, σ (σ_xx, σ_yy, τ_xy), σ_von_mises
- **Benchmark payload** — reaction forces, force-balance check, cantilever analytical ratios
- **Visualization** — contour plot (PNG) của displacement/stress/von_mises

---

## Quick start

```sh
make install          # Tạo venv + cài dependencies
make bootstrap-env   # Tạo .env từ env.example
make hooks           # Bật pre-commit hook (chặn secret leak)
make up              # Start PostgreSQL (docker compose)
make run             # Chạy API server
```

Sau đó mở: `http://localhost:8000/docs` (Swagger UI)

### Auth flow (Google OAuth2)

```txt
1. GET /api/auth/google/url        → Lấy Google OAuth URL
2. Redirect user sang URL đó       → User đăng nhập Google
3. Google redirect về /api/auth/callback?code=xxx
4. POST /api/auth/callback {code} → Nhận JWT tokens
5. Gắn Authorization: Bearer <access_token> cho các API protected
6. Hết hạn → POST /api/auth/refresh {refresh_token} → token mới
```

---

## API Endpoints

### Public
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/health` | Health check |
| GET | `/api/health/db` | Database check |
| GET | `/api/auth/google/url` | Lấy Google OAuth URL |
| POST | `/api/auth/callback` | Đổi Google code → JWT |
| POST | `/api/auth/refresh` | Refresh token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET | `/api/auth/me` | Thông tin user hiện tại |

### Protected (cần `Authorization: Bearer <token>`)

#### Geometry
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/geometry/rectangle` | Tạo hình chữ nhật |
| POST | `/api/geometry/circle` | Tạo hình tròn |
| POST | `/api/geometry/polygon` | Tạo polygon tự do |
| GET | `/api/geometry/{id}` | Lấy geometry |
| GET | `/api/geometry` | List geometries của user |
| DELETE | `/api/geometry/{id}` | Xóa geometry |

#### Mesh
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/mesh/quad` | Tạo lưới tứ giác |
| POST | `/api/mesh/delaunay` | Tạo lưới tam giác |
| POST | `/api/mesh/from-sketch` | One-shot: sketch → geometry + mesh |
| GET | `/api/mesh/{id}` | Lấy mesh |
| GET | `/api/mesh` | List meshes của user |
| GET | `/api/mesh/{id}/export?format=json\|dat\|csv` | Export mesh |
| DELETE | `/api/mesh/{id}` | Xóa mesh |

#### FEA
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/fea/solve` | Giải bài toán FEA |

---

## Ví dụ sử dụng

### Tạo hình + mesh + giải FEA

```bash
# 1. Login (lấy token)
curl -X POST http://localhost:8000/api/auth/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "<google_auth_code>"}'
# → {access_token, refresh_token, expires_in}

# 2. Tạo geometry (rectangle)
curl -X POST http://localhost:8000/api/geometry/rectangle \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Beam","x_min":0,"y_min":0,"width":1,"height":0.2}'

# 3. Tạo quad mesh
curl -X POST http://localhost:8000/api/mesh/quad \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"geometry_id":"<uuid>","nx":10,"ny":4}'

# 4. Giải FEA (cantilever beam)
curl -X POST http://localhost:8000/api/fea/solve \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "mesh_id": "<uuid>",
    "material": {"E": 210e9, "nu": 0.3, "thickness": 0.01},
    "analysis_type": "plane_stress",
    "boundary_conditions": [
      {"node_id": 0, "dof": "ux", "value": 0},
      {"node_id": 0, "dof": "uy", "value": 0}
    ],
    "nodal_forces": [
      {"node_id": 33, "dof": "fy", "value": -1000}
    ]
  }'
# → {displacements, stresses, strains, von_mises, max_displacement, ...}
```

---

## Benchmark: Section IV (editor_in_chief)

Repo có benchmark kiểm chứng cantilever theo bài báo **Oladejo et al. (2018)**,
`docs/editor_in_chief.txt` (Section IV/V), dùng đúng bộ tham số:

| Tham số | Giá trị |
|---------|---------|
| Tải trọng `P` | 10 kN (10 000 N) |
| Chiều cao `h` | 1.0 m |
| Chiều dài `L` | 10 m |
| Hệ số Poisson `ν` | 0.3 |
| Mô đun Young `E` | 2×10¹¹ N/m² |
| Bề dày `t` | 1.0 m (unit width) |

**Nghiệm giải tích Euler-Bernoulli** (Eq. 2 trong bài báo):

```
δ_max = PL³ / (3EI)  với  I = t·h³/12 = 0.0833 m⁴
      = (10000 × 10³) / (3 × 2e11 × 0.0833)
      = 2.00 × 10⁻⁴ m  ≈ 0.20 mm
```

### Kết quả so sánh (Q4 bilinear, plane stress)

| Lưới | nx × ny | Tip deflection FEA | Exact | Sai số |
|------|---------|-------------------|-------|--------|
| Coarse | 4 × 2 | −5.85 × 10⁻⁵ m | −2.00 × 10⁻⁴ m | 70.8% |
| Fine | 10 × 2 | −1.42 × 10⁻⁴ m | −2.00 × 10⁻⁴ m | 28.9% |

> **Nhận xét**: Kết quả định tính **phù hợp với Section V của bài báo** —
> lưới fine cho kết quả gần nghiệm chính xác hơn lưới coarse.
> Sai số tuyệt đối lớn hơn trong bài báo gốc vì bài báo dùng **LST (6-nút tam giác)**
> trong khi code này dùng **Q4 (4-nút tứ giác bilinear)** — phần tử Q4 gặp hiện tượng
> **shear locking** khi tỉ lệ h/L nhỏ, làm giảm độ võng tính toán. Xu hướng hội tụ
> khi tăng số phần tử là đúng với lý thuyết FEM.

Benchmark test nằm trong `tests/test_fea_cantilever_analytical.py`, gồm so sánh lưới coarse/fine với nghiệm Euler-Bernoulli tại đầu tự do.

Chạy benchmark:

```sh
make test-fea
# hoặc
.venv/bin/python -m pytest -q tests/test_fea_cantilever_analytical.py
```

---

## Cấu trúc project

```
Meshing_BE/
├── app/
│   ├── api/
│   │   ├── auth.py          # Auth endpoints (OAuth2 → JWT)
│   │   └── endpoints.py     # Geometry / Mesh / FEA endpoints
│   ├── core/
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   └── deps.py          # JWT dependency (get_current_user)
│   ├── database/
│   │   ├── models.py        # User, RefreshToken, Geometry, Mesh
│   │   └── session.py       # SQLAlchemy engine + session
│   ├── engines/
│   │   ├── base.py          # MeshEngine interface
│   │   ├── quad_engine.py   # Quad mesh generator
│   │   ├── delaunay_engine.py
│   │   └── fea/             # FEA core modules
│   │       ├── shape_functions.py
│   │       ├── gaussian_quadrature.py
│   │       ├── material.py          # Hooke 2D (plane stress/strain)
│   │       ├── stiffness.py         # Element K matrices
│   │       ├── assembly.py          # Global K assembly + BC
│   │       ├── solver.py            # Solve K·u=F
│   │       ├── stress_recovery.py   # ε, σ, σ_vm
│   │       └── visualization.py     # Contour plots (PNG)
│   ├── schemas/
│   │   ├── auth.py          # Login/token/refresh schemas
│   │   ├── request.py       # Geometry/mesh request models
│   │   ├── response.py      # Response models
│   │   ├── fea_request.py   # FEA solve request
│   │   └── fea_response.py   # FEA result response
│   └── services/
│       ├── auth_service.py   # JWT + Google OAuth logic
│       ├── mesh_service.py   # Geometry/mesh CRUD
│       └── fea_service.py   # FEA solve workflow
├── docker/
│   └── docker-compose.yml     # PostgreSQL + PGAdmin
├── scripts/
│   ├── bootstrap-env.sh      # Tạo .env từ env.example
│   └── precommit-secret-scan.sh
├── tests/
│   ├── test_fea_core.py                      # Shape, material, stiffness, assembly, cantilever
│   ├── test_fea_cantilever_analytical.py      # Section IV benchmark (Oladejo 2018)
│   ├── test_fea_assembly_solver_cases.py      # BC elimination/penalty, reaction recovery
│   ├── test_fea_convergence.py                # Q4 mesh convergence trend
│   ├── test_fea_global_stiffness_properties.py # K symmetry, PD, rigid-body modes
│   ├── test_fea_linear_system_properties.py   # Linearity, superposition, ordering invariance
│   ├── test_fea_material_stiffness.py         # Hooke 2D, Von Mises, presets, K-elem
│   ├── test_fea_patch_tests.py                # T3/Q4 patch tests (linear field exactness)
│   ├── test_fea_randomized_invariants.py      # Randomized elimination vs penalty consistency
│   ├── test_fea_shape_quadrature.py           # Shape functions, Gauss rules, B-matrix
│   ├── test_fea_solver_edge_cases.py          # Edge cases (all DOF prescribed, invalid DOF)
│   ├── test_fea_stress_recovery.py            # ε, σ, σ_vm recovery for T3 and Q4
│   ├── test_fea_u_validation.py               # Non-zero Dirichlet BC partition correctness
│   └── test_health.py                         # API health/DB endpoints
│   # Total: 58 tests — all passing
├── .githooks/               # Pre-commit hooks
├── env.example              # Template biến môi trường
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## Developer commands

```sh
make test          # Run test suite
make test-fea      # Run focused FEA test suite
make test-fea-stress # Repeat focused FEA suite 5x (stability burn-in)
make test-stress   # Repeat full suite 5x (broader stability burn-in)
make lint          # Ruff lint checks
make format        # Black formatter
make check        # Lint + tests
make secret-scan  # Scan staged changes cho secrets
make ci           # secret-scan + lint + tests
make up           # Start compose services
make down         # Stop compose services
```

---

## Environment variables

```sh
# Database
POSTGRES_URL=postgresql://admin:password@db:5432/meshing_db
DB_USER=admin
DB_PASS=change-this-password
DB_NAME=meshing_db
DB_PORT=5432
DB_HOST=db

# App
APP_NAME=FEA 2D Meshing API
DEBUG=true

# JWT
JWT_SECRET=<auto-generated-nếu-không-đặt>

# Google OAuth2 (lấy từ Google Cloud Console)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/callback
```

---

## Git secret guard

Pre-commit hook chặn commit chứa:
- File `.env`
- Các dòng staged có dạng secret (`SECRET=`, `PASSWORD=`, `API_KEY=`, `TOKEN=`, ...)

```sh
make hooks
```

---

## License

MIT
