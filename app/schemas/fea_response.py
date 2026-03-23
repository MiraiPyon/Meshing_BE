from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID


class FEAResultResponse(BaseModel):
    """Response kết quả FEA - displacement, stress, strain."""
    id: UUID
    mesh_id: UUID
    name: str
    analysis_type: str
    material: dict  # E, nu, thickness

    # Node results (n x 2)
    node_count: int
    displacements: List[List[float]]   # [[ux, uy], ...]

    # Element results (m x 3)
    element_count: int
    stresses: List[List[float]]          # [[sxx, syy, txy], ...]
    strains: List[List[float]]            # [[exx, eyy, gxy], ...]
    von_mises: List[float]              # [sigma_vm per element]

    # Summary statistics
    max_displacement: float
    max_von_mises_stress: float
    max_stress_xx: float
    max_stress_yy: float
    max_shear_xy: float

    # Nodal averaged results
    nodal_stresses: Optional[List[List[float]]] = None  # [[sxx, syy, txy], ...] at nodes
    nodal_von_mises: Optional[List[float]] = None      # at nodes

    class Config:
        from_attributes = True


class FEASolveResponse(BaseModel):
    """Response trả về sau khi solve xong."""
    result: FEAResultResponse
    success: bool
    message: str
