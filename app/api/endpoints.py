from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.request import (
    RectangleCreate,
    CircleCreate,
    PolygonCreate,
    QuadMeshCreate,
    DelaunayMeshCreate,
)
from app.schemas.response import GeometryResponse, MeshResponse, HealthResponse
from app.services.mesh_service import mesh_service

# Router
router = APIRouter(prefix="/api")


# ============== Health Check ==============

@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="ok", app_name="FEA 2D Meshing API")


# ============== Geometry Endpoints ==============

@router.post(
    "/geometry/rectangle",
    response_model=GeometryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rectangle(data: RectangleCreate, db: Session = Depends(get_db)):
    """Tạo hình chữ nhật"""
    return mesh_service.create_rectangle(db, data)


@router.post(
    "/geometry/circle",
    response_model=GeometryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_circle(data: CircleCreate, db: Session = Depends(get_db)):
    """Tạo hình tròn"""
    return mesh_service.create_circle(db, data)


@router.post(
    "/geometry/polygon",
    response_model=GeometryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_polygon(data: PolygonCreate, db: Session = Depends(get_db)):
    """Tạo hình tự do từ array các điểm"""
    return mesh_service.create_polygon(db, data)


@router.get("/geometry/{geometry_id}", response_model=GeometryResponse)
async def get_geometry(geometry_id: UUID, db: Session = Depends(get_db)):
    """Lấy geometry theo ID"""
    geometry = mesh_service.get_geometry(db, geometry_id)
    if not geometry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geometry {geometry_id} not found",
        )
    return geometry


@router.get("/geometry", response_model=List[GeometryResponse])
async def list_geometries(db: Session = Depends(get_db)):
    """List tất cả geometries"""
    return mesh_service.list_geometries(db)


@router.delete("/geometry/{geometry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geometry(geometry_id: UUID, db: Session = Depends(get_db)):
    """Xóa geometry"""
    success = mesh_service.delete_geometry(db, geometry_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geometry {geometry_id} not found",
        )


# ============== Mesh Endpoints ==============

@router.post(
    "/mesh/quad",
    response_model=MeshResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_quad_mesh(data: QuadMeshCreate, db: Session = Depends(get_db)):
    """Tạo lưới tứ giác (structured grid)"""
    try:
        return mesh_service.create_quad_mesh(db, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/mesh/delaunay",
    response_model=MeshResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_delaunay_mesh(data: DelaunayMeshCreate, db: Session = Depends(get_db)):
    """Tạo lưới tam giác Delaunay"""
    try:
        return mesh_service.create_delaunay_mesh(db, data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/mesh/{mesh_id}", response_model=MeshResponse)
async def get_mesh(mesh_id: UUID, db: Session = Depends(get_db)):
    """Lấy mesh theo ID"""
    mesh = mesh_service.get_mesh(db, mesh_id)
    if not mesh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )
    return mesh


@router.get("/mesh", response_model=List[MeshResponse])
async def list_meshes(db: Session = Depends(get_db)):
    """List tất cả meshes"""
    return mesh_service.list_meshes(db)


@router.delete("/mesh/{mesh_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mesh(mesh_id: UUID, db: Session = Depends(get_db)):
    """Xóa mesh"""
    success = mesh_service.delete_mesh(db, mesh_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )
