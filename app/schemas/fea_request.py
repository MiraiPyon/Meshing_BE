from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class MaterialInput(BaseModel):
    """Input material properties."""
    E: float = Field(..., gt=0, description="Young's modulus (Pa)")
    nu: float = Field(..., ge=0, lt=0.5, description="Poisson's ratio")
    thickness: float = Field(default=1.0, gt=0, description="Thickness (m) - for plane stress")
    preset: Optional[str] = Field(default=None, description="Material preset: steel, aluminum, titanium, concrete")


class BoundaryConditionInput(BaseModel):
    """Input boundary condition."""
    node_id: int = Field(..., ge=0, description="0-based node index")
    dof: str = Field(..., description="DOF: ux, uy")
    value: float = Field(default=0.0, description="Displacement value")


class NodalForceInput(BaseModel):
    """Input nodal force."""
    node_id: int = Field(..., ge=0, description="0-based node index")
    dof: str = Field(..., description="DOF: fx, fy")
    value: float = Field(..., description="Force value (N)")


class LineLoadInput(BaseModel):
    """Input distributed line load."""
    start_node: int = Field(..., ge=0, description="0-based start node index")
    end_node: int = Field(..., ge=0, description="0-based end node index")
    dof: str = Field(..., description="DOF: tx, ty")
    value: float = Field(..., description="Traction value (N/m)")


class FEASolveRequest(BaseModel):
    """Request giải bài toán FEA."""
    mesh_id: UUID = Field(..., description="UUID của mesh đã tạo")
    material: MaterialInput = Field(..., description="Material properties")
    analysis_type: str = Field(default="plane_stress", description="plane_stress hoặc plane_strain")
    boundary_conditions: List[BoundaryConditionInput] = Field(
        default_factory=list, description="Dirichlet BCs (displacement constraints)"
    )
    nodal_forces: List[NodalForceInput] = Field(
        default_factory=list, description="Nodal forces"
    )
    line_loads: Optional[List[LineLoadInput]] = Field(
        default=None, description="Distributed edge loads"
    )
    integration_order: Optional[str] = Field(
        default=None,
        description="Integration order: 1pt/3pt/7pt (tri), 2x2/3x3 (quad)"
    )
