# FEA 2D Meshing API

API Backend cho bài toán chia lưới (Meshing) trong phân tích phần tử hữu hạn (FEA) 2D.

## Tính năng

- Tạo hình học: Rectangle, Circle, Polygon (vẽ tự do từ array điểm)
- Chia lưới tứ giác (Quad Mesh) - structured grid
- Chia lưới tam giác (Triangular Mesh) - Delaunay triangulation
- Lưu trữ dữ liệu với PostgreSQL (Supabase)

## Yêu cầu

- Python 3.10+
- PostgreSQL (Supabase)

## Cài đặt

1. Clone project và cài dependencies:

```bash
pip install -r requirements.txt
```

2. Cấu hình database trong file `.env`:

```env
POSTGRES_URL=postgresql://postgres:your_password@db.your-project.supabase.co:5432/postgres
DEBUG=true
```

3. Chạy server:

```bash
uvicorn app.main:app --reload
```

Server chạy tại: http://127.0.0.1:8000

## API Endpoints

### Health Check

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/` | Health check |
| GET | `/health` | Health check |

### Geometry

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/geometry/rectangle` | Tạo hình chữ nhật |
| POST | `/api/geometry/circle` | Tạo hình tròn |
| POST | `/api/geometry/polygon` | Tạo hình tự do từ array điểm |
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

## Ví dụ sử dụng

### 1. Tạo hình chữ nhật

```bash
curl -X POST http://127.0.0.1:8000/api/geometry/rectangle \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Rectangle",
    "x_min": 0,
    "y_min": 0,
    "width": 2,
    "height": 1
  }'
```

### 2. Tạo lưới tứ giác

```bash
curl -X POST http://127.0.0.1:8000/api/mesh/quad \
  -H "Content-Type: application/json" \
  -d '{
    "geometry_id": "<UUID>",
    "nx": 10,
    "ny": 5
  }'
```

### 3. Tạo lưới Delaunay

```bash
curl -X POST http://127.0.0.1:8000/api/mesh/delaunay \
  -H "Content-Type: application/json" \
  -d '{
    "geometry_id": "<UUID>",
    "max_area": 0.01
  }'
```

### 4. Tạo hình Polygon (vẽ tự do)

```bash
curl -X POST http://127.0.0.1:8000/api/geometry/polygon \
  -H "Content-Type: application/json" \
  -d '{
    "name": "L-shape",
    "points": [[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]],
    "closed": true
  }'
```

## Data Format

### Response Mesh (cho Frontend)

```json
{
  "id": "uuid",
  "geometry_id": "uuid",
  "mesh_type": "quad" | "delaunay",
  "name": "string",
  "node_count": 25,
  "element_count": 16,
  "nodes": [[0,0], [0.25,0], ...],        // n x 2 array
  "elements": [[1,2,6,5], [2,3,7,6], ...], // m x 4 (quad) hoặc m x 3 (triangle)
  "bounds": {
    "x_min": 0,
    "x_max": 1,
    "y_min": 0,
    "y_max": 1
  },
  "created_at": "2026-03-07T05:00:00"
}
```

### Frontend Integration

Frontend nhận raw data (`nodes` và `elements`) và tự vẽ bằng:

- HTML5 Canvas
- Konva.js / Fabric.js
- Three.js (WebGL)

## Cấu trúc Project

```
Meshing_BE/
├── app/
│   ├── api/
│   │   └── endpoints.py      # API routes
│   ├── core/
│   │   └── config.py         # Settings
│   ├── database/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── session.py        # DB connection
│   ├── engines/
│   │   ├── base.py           # Base mesh engine
│   │   ├── quad_engine.py    # Quad mesh algorithm
│   │   └── delaunay_engine.py # Delaunay algorithm
│   ├── schemas/
│   │   ├── request.py        # Request models
│   │   └── response.py       # Response models
│   ├── services/
│   │   └── mesh_service.py   # Business logic
│   └── main.py               # FastAPI app
├── .env                      # Environment variables
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## License

MIT
