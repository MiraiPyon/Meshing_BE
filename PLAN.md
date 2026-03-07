# FEA 2D Meshing Backend - API Plan

## Project Overview
- **Project name**: FEA 2D Meshing API
- **Framework**: FastAPI (Python)
- **Purpose**: Cung cấp API để tạo hình học và chia lưới (meshing) cho bài toán FEA 2D

---

## Core Features (từ yêu cầu)

### 1. Tạo hình học cơ bản (Geometry Creation)
- Vẽ các dạng hình học cơ bản: hình chữ nhật (rectangle), hình tròn (circle)
- Lưu trữ boundary/edges của hình

### 2. Chia lưới tứ giác (Quad Meshing)
- Chia lưới có cấu trúc (structured grid) cho hình đã tạo
- Output: Node (n x 2) và Elem (m x 4)
- Plot lại lưới đã chia

### 3. Chia lưới tam giác (Triangular Meshing - Delaunay)
- Sử dụng thuật toán Delaunay để tạo lưới tam giác
- Output: Node (n x 2) và Elem (m x 3)
- Plot lại lưới đã chia

---

## API Endpoints

### Health Check
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check endpoint |
| GET | `/health` | Health check endpoint |

### Geometry Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/geometry/rectangle` | Tạo hình chữ nhật với tọa độ và kích thước |
| POST | `/api/geometry/circle` | Tạo hình tròn với tâm và bán kính |
| POST | `/api/geometry/polygon` | Tạo hình tự do từ array các điểm (x,y) |
| GET | `/api/geometry/{id}` | Lấy thông tin geometry theo ID |
| GET | `/api/geometry` | List tất cả geometries |
| DELETE | `/api/geometry/{id}` | Xóa geometry |

### Mesh Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/mesh/quad` | Chia lưới tứ giác (structured) cho geometry |
| POST | `/api/mesh/delaunay` | Chia lưới tam giác bằng Delaunay |
| GET | `/api/mesh/{id}` | Lấy thông tin mesh theo ID |
| GET | `/api/mesh` | List tất cả meshes |
| DELETE | `/api/mesh/{id}` | Xóa mesh |

### Visualization Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mesh/{id}/plot` | Trả về image/png của mesh đã vẽ |

### Geometry (Request/Response)
```python
# Rectangle
{
  "type": "rectangle",
  "name": "string",
  "x_min": float,
  "y_min": float,
  "width": float,
  "height": float
}

# Circle
{
  "type": "circle",
  "name": "string",
  "center_x": float,
  "center_y": float,
  "radius": float
}

# Polygon (free drawing - array of points)
{
  "type": "polygon",
  "name": "string",
  "points": [[x1,y1], [x2,y2], ...],  // array of (x,y) from canvas
  "closed": boolean  // True if polygon is closed
}
```

### Mesh (Response)
```python
{
  "id": "uuid",
  "geometry_id": "uuid",
  "mesh_type": "quad" | "delaunay",
  "node_count": int,
  "element_count": int,
  "nodes": [[x, y], ...],      # List[List[float]] - n x 2
  "elements": [[n1, n2, n3], ...] | [[n1, n2, n3, n4], ...],  # m x 3 or m x 4
  "created_at": "datetime"
}
```

### Mesh Parameters (Request)
```python
# Quad mesh
{
  "geometry_id": "uuid",
  "nx": int,  # số phần tử theo x
  "ny": int   # số phần tử theo y
}

# Delaunay mesh
{
  "geometry_id": "uuid",
  "max_area": float,  # diện tích tối đa mỗi tam giác (optional)
  "min_angle": float  # góc tối thiểu (optional)
}
```

---

## Service Layer

### MeshService
- `create_rectangle_geometry()` - Tạo geometry hình chữ nhật
- `create_circle_geometry()` - Tạo geometry hình tròn
- `create_quad_mesh()` - Tạo lưới tứ giác
- `create_delaunay_mesh()` - Tạo lưới tam giác Delaunay
- `plot_mesh()` - Tạo hình ảnh mesh

---

## Engines (Meshing Algorithms)

### QuadEngine
- Chia lưới structured grid cho rectangle
- Input: bounds, nx, ny
- Output: Node array (n x 2), Element array (m x 4)

### DelaunayEngine
- Sử dụng scipy.spatial.Delaunay hoặc triangle library
- Input: boundary points, max_area, min_angle
- Output: Node array (n x 2), Element array (m x 3)

---

## Công nghệ sử dụng
- **FastAPI** - Web framework
- **NumPy** - Xử lý mảng, tính toán
- **SciPy** - Delaunay triangulation
- **Supabase** - Database & Storage (PostgreSQL + REST API)
- **Pydantic** - Data validation

---

## Frontend Integration

Frontend sẽ nhận raw data (Node/Elem array) và tự vẽ bằng Canvas hoặc WebGL.

### Response format cho frontend
```json
{
  "id": "uuid",
  "geometry_id": "uuid",
  "mesh_type": "quad" | "delaunay",
  "node_count": 25,
  "element_count": 16,
  "nodes": [[0,0], [0.25,0], [0.5,0], ...],  // n x 2 array
  "elements": [[1,2,6,5], [2,3,7,6], ...],     // m x 4 (quad) hoặc m x 3 (triangle)
  "bounds": {
    "x_min": 0,
    "x_max": 1,
    "y_min": 0,
    "y_max": 1
  }
}
```

### Frontend rendering
- Dùng HTML5 Canvas hoặc thư viện như Konva.js, Fabric.js
- Hoặc WebGL với Three.js để render mesh 2D
- Hỗ trợ zoom, pan, highlight elements/nodes

---

## Flow hoạt động

```
1. Client gửi request tạo geometry (rectangle/circle)
   → API lưu geometry, trả về geometry_id

2. Client gửi request tạo mesh (quad/delaunay) kèm geometry_id
   → API gọi engine tương ứng
   → Engine tạo Node array và Element array
   → API lưu mesh, trả về mesh_id

3. Client gọi endpoint plot với mesh_id
   → API tạo hình ảnh matplotlib và trả về PNG
```

---

## Ưu tiên triển khai

1. **Phase 1**: Setup FastAPI, tạo geometry rectangle + circle
2. **Phase 2**: Quad mesh engine cho rectangle
3. **Phase 3**: Delaunay mesh engine
4. **Phase 4**: Plotting endpoint
5. **Phase 5**: Validation, error handling, testing
