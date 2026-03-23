"""
FEA API Endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import Response
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.fea_request import FEASolveRequest
from app.schemas.fea_response import FEAResultResponse, FEASolveResponse
from app.services.fea_service import fea_service
from app.engines.fea.visualization import FEAVisualizer

router = APIRouter(prefix="/api/fea")


@router.post(
    "/solve",
    response_model=FEASolveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def solve_fea(req: FEASolveRequest, db: Session = Depends(get_db)):
    """Giải bài toán FEA 2D (plane stress / plane strain)."""
    try:
        result, success, message = fea_service.solve(db, req)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            )
        return FEASolveResponse(result=result, success=success, message=message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/plot/{result_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def plot_fea_result(result_id: UUID, db: Session = Depends(get_db)):
    """
    Trả về hình ảnh PNG kết quả FEA.

    Query params:
      - type: "displacement", "von_mises", "stress_xx", "stress_yy", "shear_xy" (default: "von_mises")
      - scale: displacement scale factor (default: auto)
      - show_deformed: show deformed mesh overlay (default: true)
    """
    # NOTE: result_id here is the mesh_id passed to solve
    # For full result persistence, integrate with database
    # This endpoint returns a placeholder — real impl needs result storage
    raise HTTPException(
        status_code=status.HTTP_501_NOT_FOUND,
        detail="Result plotting requires result_id to be persisted. "
               "Use /api/fea/plot-mesh/{mesh_id} for quick preview.",
    )


@router.get(
    "/plot-mesh/{mesh_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def plot_mesh_preview(
    mesh_id: UUID,
    db: Session = Depends(get_db),
    displacement_scale: float = 0.0,
    plot_type: str = "mesh",
):
    """
    Plot mesh hoặc deformed mesh preview.

    Query params:
      - displacement_scale: factor để nhân displacement (0 = chưa có displacement, chỉ vẽ mesh thường)
      - plot_type: "mesh", "von_mises", "displacement"
    """
    try:
        viz = FEAVisualizer()
        img_bytes = viz.plot_mesh_from_db(
            db=db,
            mesh_id=mesh_id,
            displacement_scale=displacement_scale,
            plot_type=plot_type,
        )
        return Response(content=img_bytes, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
