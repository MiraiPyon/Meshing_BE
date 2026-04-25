"""
API Endpoints — tất cả geometry/mesh/FEA endpoints đều được bảo vệ bằng JWT.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import List
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.deps import get_current_user
from app.schemas.request import (
    RectangleCreate, CircleCreate, PolygonCreate,
    QuadMeshCreate, DelaunayMeshCreate, MeshFromSketchCreate,
)
from app.schemas.response import GeometryResponse, MeshResponse
from app.schemas.fea_request import FEASolveRequest
from app.schemas.fea_response import FEASolveResponse
from app.services.mesh_service import mesh_service
from app.services.fea_service import fea_service


router = APIRouter()


# ============== Health (public) ==============

@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db", tags=["health"])
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(content={"status": "ok", "database": "connected"})
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected", "reason": str(exc)},
        )


# ============== Geometry (protected) ==============

@router.post("/geometry/rectangle", response_model=GeometryResponse, status_code=status.HTTP_201_CREATED, tags=["geometry"])
def create_rectangle(data: RectangleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return mesh_service.create_rectangle(db, data, user.id)


@router.post("/geometry/circle", response_model=GeometryResponse, status_code=status.HTTP_201_CREATED, tags=["geometry"])
def create_circle(data: CircleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return mesh_service.create_circle(db, data, user.id)


@router.post("/geometry/polygon", response_model=GeometryResponse, status_code=status.HTTP_201_CREATED, tags=["geometry"])
def create_polygon(data: PolygonCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return mesh_service.create_polygon(db, data, user.id)


@router.get("/geometry/{geometry_id}", response_model=GeometryResponse, tags=["geometry"])
def get_geometry(geometry_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    geometry = mesh_service.get_geometry(db, geometry_id, user.id)
    if not geometry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Geometry {geometry_id} not found")
    return geometry


@router.get("/geometry", response_model=List[GeometryResponse], tags=["geometry"])
def list_geometries(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return mesh_service.list_geometries(db, user.id)


@router.delete("/geometry/{geometry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["geometry"])
def delete_geometry(geometry_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    success = mesh_service.delete_geometry(db, geometry_id, user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Geometry {geometry_id} not found")


# ============== Mesh (protected) ==============

@router.post("/mesh/quad", response_model=MeshResponse, status_code=status.HTTP_201_CREATED, tags=["mesh"])
def create_quad_mesh(data: QuadMeshCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return mesh_service.create_quad_mesh(db, data, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/mesh/delaunay", response_model=MeshResponse, status_code=status.HTTP_201_CREATED, tags=["mesh"])
def create_delaunay_mesh(data: DelaunayMeshCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        return mesh_service.create_delaunay_mesh(db, data, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/mesh/{mesh_id}", response_model=MeshResponse, tags=["mesh"])
def get_mesh(mesh_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    mesh = mesh_service.get_mesh(db, mesh_id, user.id)
    if not mesh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mesh {mesh_id} not found")
    return mesh


@router.get("/mesh", response_model=List[MeshResponse], tags=["mesh"])
def list_meshes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return mesh_service.list_meshes(db, user.id)


@router.delete("/mesh/{mesh_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["mesh"])
def delete_mesh(mesh_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    success = mesh_service.delete_mesh(db, mesh_id, user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mesh {mesh_id} not found")


@router.post("/mesh/from-sketch", response_model=MeshResponse, status_code=status.HTTP_201_CREATED, tags=["mesh"])
def create_mesh_from_sketch(data: MeshFromSketchCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """One-shot: nhận sketch từ FE, tạo geometry + mesh trong một request."""
    try:
        return mesh_service.create_mesh_from_sketch(db, data, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/mesh/{mesh_id}/export", tags=["mesh"])
def export_mesh(
    mesh_id: UUID,
    format: str = "json",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Export mesh sang json/dat/csv. format=json|dat|csv"""
    from fastapi.responses import PlainTextResponse, JSONResponse
    try:
        result = mesh_service.export_mesh(db, mesh_id, user.id, format)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if result["format"] == "json":
        return JSONResponse(
            content=result["data"],
            headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
        )
    if result["format"] == "csv":
        # Return nodes CSV (elements available in result["data"]["elements"])
        return PlainTextResponse(
            content=result["data"]["nodes"],
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
        )
    # dat
    return PlainTextResponse(
        content=result["data"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


# ============== FEA (protected) ==============

@router.post("/fea/solve", response_model=FEASolveResponse, status_code=status.HTTP_201_CREATED, tags=["fea"])
def solve_fea(req: FEASolveRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        result, success, message = fea_service.solve(db, req, user.id)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        return FEASolveResponse(result=result, success=success, message=message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
