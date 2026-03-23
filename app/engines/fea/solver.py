"""
FEASolver – Giải hệ phương trình K·u = F.
Sử dụng scipy.sparse.linalg.spsolve cho hệ sparse lớn.
"""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, factorized
from typing import Tuple, List, Optional
from dataclasses import dataclass

from app.engines.fea.material import MaterialModel, AnalysisType
from app.engines.fea.stiffness import ElementStiffness
from app.engines.fea.assembly import GlobalAssembler, BoundaryCondition, NodalForce, LineLoad


@dataclass
class SolverConfig:
    """Cấu hình solver."""
    integration_order: str = "3pt"     # cho tam giác: 1pt/3pt/7pt; tứ giác: 2x2/3x3
    bc_method: str = "elimination"    # "penalty" hoặc "elimination"
    penalty: float = 1e20             # penalty factor cho method "penalty"
    solve_tolerance: float = 1e-12    # tolerance cho iterative solver
    use_preconditioner: bool = True


class FEASolver:
    """
    FEA Solver tổng hợp.

    Workflow:
      1. setup()  – Chuẩn bị K, F
      2. solve()  – Giải → displacements
      3. recover() – Tính stress/strain
    """

    def __init__(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        material: MaterialModel,
        analysis_type: AnalysisType = AnalysisType.PLANE_STRESS,
        config: Optional[SolverConfig] = None,
    ):
        """
        Args:
            nodes:         (n_nodes, 2) tọa độ node
            elements:      list of [n1, n2, ...] (1-based từ mesh API)
            material:      MaterialModel
            analysis_type: plane_stress hoặc plane_strain
            config:        SolverConfig
        """
        self.nodes = np.asarray(nodes)
        self.elements = [[e - 1 for e in elem] for elem in elements]
        self.material = material
        self.analysis_type = analysis_type
        self.config = config or SolverConfig()

        self.stiffness_builder = ElementStiffness(material, analysis_type)
        self.assembler = GlobalAssembler(nodes, elements)

        self._K_full: Optional[sp.csr_matrix] = None
        self._K_reduced: Optional[sp.csr_matrix] = None
        self._F: Optional[np.ndarray] = None
        self._F_reduced: Optional[np.ndarray] = None
        self._free_dofs: Optional[List[int]] = None
        self._fixed_dofs: Optional[set] = None
        self._u_reduced: Optional[np.ndarray] = None

    # ---- Setup phase ----

    def setup(self) -> "FEASolver":
        """Build global stiffness matrix K."""
        def K_elem_fn(e_idx: int) -> np.ndarray:
            coords = self.assembler.get_element_coords(e_idx)
            n_nodes = len(coords)
            order = self.config.integration_order
            return self.stiffness_builder.compute(coords, order)

        self._K_full = self.assembler.build_global_K(K_elem_fn)
        return self

    def apply_boundary_conditions(
        self,
        bc_list: List[BoundaryCondition],
        nodal_forces: Optional[List[NodalForce]] = None,
        line_loads: Optional[List[LineLoad]] = None,
    ) -> "FEASolver":
        """
        Áp đặt điều kiện biên và lực.

        Args:
            bc_list:       Dirichlet BCs
            nodal_forces:  Concentrated nodal forces
            line_loads:    Distributed edge loads
        """
        if self._K_full is None:
            self.setup()

        # Force vector
        self._F = self.assembler.build_force_vector(nodal_forces or [])

        # Add line loads
        if line_loads:
            self._F = self.assembler.add_line_load(self._F, line_loads)

        # Apply Dirichlet BC
        if self.config.bc_method == "elimination":
            self._K_reduced, self._F_reduced, self._free_dofs, self._fixed_dofs = \
                self.assembler.apply_dirichlet_bc(
                    self._K_full, self._F, bc_list,
                    method="elimination",
                )
        else:
            self._K_reduced, self._F_reduced = \
                self.assembler.apply_dirichlet_bc(
                    self._K_full, self._F, bc_list,
                    method="penalty",
                    penalty=self.config.penalty,
                )

        return self

    # ---- Solve ----

    def solve(self) -> Tuple[np.ndarray, bool, str]:
        """
        Giải hệ phương trình.

        Returns:
            u_full: (n_nodes, 2) displacements [ux, uy]
            success: True nếu giải thành công
            message: thông điệp trạng thái
        """
        if self._K_reduced is None or self._F_reduced is None:
            return self._empty_u(), False, "Call apply_boundary_conditions() first"

        try:
            # Factorize để tái sử dụng cho parametric runs
            solve_func = factorized(self._K_reduced)
            u_reduced = solve_func(self._F_reduced)

            # Expand to full DOF vector
            u_full = self._expand_u(u_reduced)
            self._u_reduced = u_reduced

            return u_full, True, "Solution converged"

        except Exception as e:
            return self._empty_u(), False, f"Solver error: {str(e)}"

    def _expand_u(self, u_reduced: np.ndarray) -> np.ndarray:
        """Mở rộng vector reduced → full DOF, điền BC values."""
        u_full = np.zeros(self.n_dof)

        if self._free_dofs is not None:
            for i, dof in enumerate(self._free_dofs):
                u_full[dof] = u_reduced[i]

        if hasattr(self, "_bc_values") and self._bc_values:
            for bc in self._bc_values:
                dof = self.assembler._dof_index(bc.node_id, bc.dof)
                u_full[dof] = bc.value

        return u_full

    def _empty_u(self) -> np.ndarray:
        return np.zeros((self.n_nodes, 2))

    # ---- Properties ----

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_dof(self) -> int:
        return 2 * self.n_nodes

    # ---- Quick solve shortcut ----

    def run(
        self,
        bc_list: List[BoundaryCondition],
        nodal_forces: Optional[List[NodalForce]] = None,
        line_loads: Optional[List[LineLoad]] = None,
    ) -> Tuple[np.ndarray, bool, str]:
        """
        Run full analysis in one call.

        Returns:
            u_full: (n_nodes, 2) displacements
        """
        self._bc_values = bc_list
        self.apply_boundary_conditions(bc_list, nodal_forces, line_loads)
        return self.solve()
