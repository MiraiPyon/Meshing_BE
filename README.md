# FEA 2D Meshing & Analysis API

API Backend cho bài toán **tạo lưới (Meshing)** và **phân tích phần tử hữu hạn (FEA)** 2D.

## Tính năng

### Meshing
- Tạo hình học: Rectangle, Circle, Polygon (tự do từ array điểm)
- Chia lưới tứ giác (Quad Mesh) — structured grid
- Chia lưới tam giác (Triangular Mesh) — Delaunay triangulation
- Hỗ trợ holes (vùng trống bên trong) cho Delaunay

### FEA 2D
- Định luật Hooke cho plane stress và plane strain
- Shape functions: tam giác tuyến tính (3 nút) + tứ giác song tuyến tính (4 nút)
- Tích phân số Gaussian Quadrature: 1pt, 3pt, 7pt (tam giác) / 2×2, 3×3 (tứ giác)
- Ma trận độ cứng phần tử và lắp ráp ma trận tổng thể K (sparse)
- Giải hệ phương trình K·u = F (Dirichlet + Neumann BC)
- Stress recovery: ε, σ (σ_xx, σ_yy, τ_xy), σ_von_mises
- Visualization: contour stress, deformed mesh (PNG)

## Kiến trúc FEA

```
app/engines/fea/
├── shape_functions.py     # N(xi,eta), dN/dxi, dN/deta, Jacobian, B-matrix
├── gaussian_quadrature.py # Gauss points & weights
├── material.py            # Hooke D-matrix, plane stress/strain, presets
├── stiffness.py           # K_e = ∫ Bᵀ D B |J| dΩ
├── assembly.py            # Global K assembly, BC elimination, reactions
├── solver.py              # K·u=F solver (sparse LU)
├── stress_recovery.py     # Compute ε, σ at Gauss points → average to nodes
└── visualization.py       # Plot contours & deformed mesh
```

## Yêu cầu

- Python 3.10+
- PostgreSQL (Supabase)
- Packages: `fastapi`, `uvicorn`, `sqlalchemy`, `numpy`, `scipy`, `matplotlib`

## Cài đặt

```bash
pip install -r requirements.txt
```

Cấu hình `.env`:
```env
POSTGRES_URL=postgresql://postgres:your_password@db.your-project.supabase.co:5432/postgres
DEBUG=true
```

Chạy server:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Health
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/` | Health check |
| GET | `/api/health` | Health check |

### Geometry
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/geometry/rectangle` | Tạo hình chữ nhật |
| POST | `/api/geometry/circle` | Tạo hình tròn |
| POST | `/api/geometry/polygon` | Tạo polygon tự do |
| GET | `/api/geometry/{id}` | Lấy geometry theo ID |
| GET | `/api/geometry` | List tất cả geometries |
| DELETE | `/api/geometry/{id}` | Xóa geometry |

### Mesh
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/mesh/quad` | Tạo lưới tứ giác |
| POST | `/api/mesh/delaunay` | Tạo lưới tam giác Delaunay |
| GET | `/api/mesh/{id}` | Lấy mesh theo ID |
| GET | `/api/mesh` | List tất cả meshes |
| DELETE | `/api/mesh/{id}` | Xóa mesh |

### FEA
| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/fea/solve` | Giải bài toán FEA 2D |
| GET | `/api/fea/plot-mesh/{mesh_id}` | Plot mesh / contour / deformed (PNG) |

## Ví dụ sử dụng

### 1. Tạo hình + lưới + giải FEA

```bash
# Tạo geometry (hình chữ nhật 1m x 0.2m)
curl -X POST http://127.0.0.1:8000/api/geometry/rectangle \
  -H "Content-Type: application/json" \
  -d '{"name":"Beam","x_min":0,"y_min":0,"width":1,"height":0.2}'

# Tạo mesh (geometry_id từ response trên)
curl -X POST http://127.0.0.1:8000/api/mesh/quad \
  -H "Content-Type: application/json" \
  -d '{"geometry_id":"<UUID>","nx":10,"ny":2}'

# Giải FEA — cantilever beam, fixed left, load downward at right
curl -X POST http://127.0.0.1:8000/api/fea/solve \
  -H "Content-Type: application/json" \
  -d '{
    "mesh_id": "<UUID>",
    "analysis_type": "plane_stress",
    "material": {"E": 210e9, "nu": 0.3, "thickness": 0.01},
    "boundary_conditions": [
      {"node_id": 0, "dof": "ux", "value": 0},
      {"node_id": 0, "dof": "uy", "value": 0},
      {"node_id": 1, "dof": "ux", "value": 0},
      {"node_id": 1, "dof": "uy", "value": 0},
      {"node_id": 2, "dof": "ux", "value": 0},
      {"node_id": 2, "dof": "uy", "value": 0}
    ],
    "nodal_forces": [
      {"node_id": 30, "dof": "fy", "value": -500},
      {"node_id": 31, "dof": "fy", "value": -500}
    ]
  }'
```

### 2. Material presets
```json
"material": {
  "preset": "steel",
  "thickness": 0.01
}
```
Presets: `steel`, `aluminum`, `titanium`, `concrete`

### 3. Plot visualization
```bash
# Mesh thường
curl http://127.0.0.1:8000/api/fea/plot-mesh/<UUID>?plot_type=mesh -o mesh.png

# Von Mises contour
curl http://127.0.0.1:8000/api/fea/plot-mesh/<UUID>?plot_type=von_mises -o stress.png

# Mesh biến dạng (với displacement scale)
curl "http://127.0.0.1:8000/api/fea/plot-mesh/<UUID>?plot_type=displacement&displacement_scale=50" -o deformed.png
```

## FEA Response

```json
{
  "id": "uuid",
  "mesh_id": "uuid",
  "analysis_type": "plane_stress",
  "material": {"E": 2.1e11, "nu": 0.3, "thickness": 0.01},
  "node_count": 33,
  "element_count": 20,
  "displacements": [[ux, uy], ...],   // n_nodes x 2
  "stresses": [[sxx, syy, txy], ...], // n_elements x 3 (element avg)
  "strains": [[exx, eyy, gxy], ...],   // n_elements x 3
  "von_mises": [vm1, vm2, ...],        // n_elements
  "nodal_stresses": [[sxx, syy, txy], ...], // n_nodes x 3 (averaged)
  "nodal_von_mises": [vm_n1, vm_n2, ...],
  "max_displacement": 8.48e-05,
  "max_von_mises_stress": 1.83e+08,
  "max_stress_xx": 1.52e+08,
  "max_stress_yy": 4.62e+07,
  "max_shear_xy": 2.04e+07
}
```

## Validation

Module FEA được kiểm tra với bài toán **cantilever beam** (1m × 0.2m, E=210 GPa, ν=0.3, t=0.01m):

| Check | Result |
|-------|--------|
| Solver converges | ✓ |
| Fixed nodes = 0 displacement | ✓ |
| u_y tăng về tip (pure bending) | ✓ |
| Shear locking → Timoshenko (≈0.36× Euler-Bernoulli) | ✓ |
| Reaction force balance | ✓ 0.00% error |
| Energy balance (strain energy = external work) | ✓ 1.0000 |

Chạy tests:
```bash
python -m pytest tests/test_fea_core.py -v
```

## Cấu trúc Project

```
Meshing_BE/
├── app/
│   ├── api/
│   │   ├── endpoints.py        # Geometry + Mesh routes
│   │   └── endpoints_fea.py    # FEA routes
│   ├── core/
│   │   └── config.py           # Settings
│   ├── database/
│   │   ├── models.py           # SQLAlchemy models (Geometry, Mesh)
│   │   └── session.py          # DB connection
│   ├── engines/
│   │   ├── base.py             # MeshEngine interface
│   │   ├── quad_engine.py      # Structured quad mesh
│   │   ├── delaunay_engine.py  # Delaunay triangulation
│   │   └── fea/                # FEA core modules
│   │       ├── shape_functions.py
│   │       ├── gaussian_quadrature.py
│   │       ├── material.py
│   │       ├── stiffness.py
│   │       ├── assembly.py
│   │       ├── solver.py
│   │       ├── stress_recovery.py
│   │       └── visualization.py
│   ├── schemas/
│   │   ├── request.py
│   │   ├── response.py
│   │   ├── fea_request.py
│   │   └── fea_response.py
│   ├── services/
│   │   ├── mesh_service.py
│   │   └── fea_service.py
│   └── main.py                 # FastAPI app
├── tests/
│   └── test_fea_core.py         # FEA validation tests
├── .env
├── requirements.txt
└── README.md
```

## License

MIT
