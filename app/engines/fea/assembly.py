"""
Global Assembly – Lắp ráp ma trận độ cứng tổng thể K từ các phần tử.
Hỗ trợ Dirichlet (displacement) và Neumann (force) boundary conditions.
"""

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve
from typing import Tuple, List, Optional
from dataclasses import dataclass, field


@dataclass
class BoundaryCondition:
    """Điều kiện biên."""
    node_id: int          # 0-based node index
    dof: str              # "ux" or "uy"
    value: float          # giá trị (thường là 0 cho Dirichlet)


@dataclass
class NodalForce:
    """Lực tập trung tại node."""
    node_id: int
    dof: str              # "fx" hoặc "fy"
    value: float


@dataclass
class LineLoad:
    """Lực phân bố trên cạnh (edge)."""
    start_node: int       # 0-based
    end_node: int         # 0-based
    dof: str              # "tx" hoặc "ty" (traction)
    value: float          # giá trị lực trên đơn vị chiều dài


@dataclass
class FEAResult:
    """Kết quả phân tích FEA."""
    displacements: np.ndarray          # (n_nodes, 2) – [ux, uy]
    reactions: Optional[np.ndarray] = None  # (n_nodes, 2) – phản lực liên kết
    success: bool = True
    message: str = ""


class GlobalAssembler:
    """
    Lắp ráp ma trận độ cứng tổng thể và áp đặt boundary conditions.

    Workflow:
      1. build_global_K()    – Ghép K từ mọi phần tử
      2. apply_bc()          – Áp đặt điều kiện biên (Dirichlet)
      3. apply_loads()       – Áp đặt lực nút (Neumann)
      4. solve()             – Giải hệ phương trình
    """

    def __init__(self, nodes: np.ndarray, elements: List[List[int]]):
        """
        Args:
            nodes:    (n_nodes, 2) tọa độ node
            elements: list of element connectivity (1-based indices từ mesh API)
        """
        self.nodes = np.asarray(nodes)
        self.elements = [[e - 1 for e in elem] for elem in elements]  # → 0-based
        self.n_nodes = len(nodes)
        self.n_dof = 2 * self.n_nodes

        # Kiểm tra element type
        self._elem_type = "unknown"
        if elements:
            n_nodes_per_elem = len(elements[0])
            if n_nodes_per_elem == 3:
                self._elem_type = "triangle"
            elif n_nodes_per_elem == 4:
                self._elem_type = "quad"
            else:
                self._elem_type = "mixed"

    # ---- Getters cho stiffness builder ----

    def get_element_coords(self, elem_idx: int) -> np.ndarray:
        """Lấy tọa độ node của một phần tử."""
        node_ids = self.elements[elem_idx]
        return self.nodes[node_ids]

    def get_element_dofs(self, elem_idx: int) -> np.ndarray:
        """
        Lấy global DOF indices cho một phần tử.

        Returns:
            (2*n_nodes_per_elem,) – flattened [ux0, uy0, ux1, uy1, ...]
        """
        node_ids = self.elements[elem_idx]
        dofs = []
        for n in node_ids:
            dofs.extend([2 * n, 2 * n + 1])
        return np.array(dofs)

    # ---- Global stiffness matrix (sparse) ----

    def build_global_K(
        self,
        K_elem_fn,
    ) -> sp.csr_matrix:
        """
        Lắp ráp ma trận độ cứng tổng thể dạng sparse.

        Args:
            K_elem_fn: callable(elem_idx) → K_e (local stiffness matrix)

        Returns:
            K: (n_dof, n_dof) sparse CSR matrix
        """
        n_dof = self.n_dof
        rows = []
        cols = []
        data = []

        for e_idx in range(len(self.elements)):
            K_e = K_elem_fn(e_idx)
            dofs = self.get_element_dofs(e_idx)

            for i_local, i_global in enumerate(dofs):
                for j_local, j_global in enumerate(dofs):
                    rows.append(i_global)
                    cols.append(j_global)
                    data.append(K_e[i_local, j_local])

        K = sp.csr_matrix((data, (rows, cols)), shape=(n_dof, n_dof))
        K.sum_duplicates()  # cộng gộp các entry trùng nhau
        return K

    def build_global_K_dense(self, K_elem_fn) -> np.ndarray:
        """
        Lắp ráp K dạng dense (chậm, chỉ dùng cho debug/micro meshes).
        """
        n_dof = self.n_dof
        K = np.zeros((n_dof, n_dof))

        for e_idx in range(len(self.elements)):
            K_e = K_elem_fn(e_idx)
            dofs = self.get_element_dofs(e_idx)

            for i_local, i_global in enumerate(dofs):
                for j_local, j_global in enumerate(dofs):
                    K[i_global, j_global] += K_e[i_local, j_local]

        return K

    # ---- Force vector ----

    def build_force_vector(self, nodal_forces: List[NodalForce]) -> np.ndarray:
        """Tạo vector lực nút F từ lực tập trung."""
        F = np.zeros(self.n_dof)

        for force in nodal_forces:
            n = force.node_id
            if force.dof in ("fx", "ux"):
                F[2 * n] += force.value
            elif force.dof in ("fy", "uy"):
                F[2 * n + 1] += force.value

        return F

    def add_line_load(
        self,
        F: np.ndarray,
        line_loads: List[LineLoad],
    ) -> np.ndarray:
        """
        Thêm lực phân bố trên cạnh vào vector lực.

        Mỗi cạnh được chia thành nhiều điểm Gauss để tích phân.

        Args:
            F:          current force vector (modified in-place)
            line_loads: list of LineLoad

        Returns:
            F: updated force vector
        """
        for load in line_loads:
            n1, n2 = load.start_node, load.end_node
            x1, y1 = self.nodes[n1]
            x2, y2 = self.nodes[n2]

            # Edge length
            L = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

            # 2-point Gauss for edge
            gp_xi = np.array([-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0)])
            gp_w = np.array([0.5, 0.5])

            # Shape functions for 2-node line element
            # N1 = (1 - xi)/2, N2 = (1 + xi)/2
            for xi, w in zip(gp_xi, gp_w):
                N1 = (1.0 - xi) / 2.0
                N2 = (1.0 + xi) / 2.0

                # Jacobian for edge = L/2
                J_edge = L / 2.0

                # Equivalent nodal forces
                f_edge = load.value * J_edge * w

                if load.dof in ("tx", "ux"):
                    F[2 * n1] += N1 * f_edge
                    F[2 * n2] += N2 * f_edge
                elif load.dof in ("ty", "uy"):
                    F[2 * n1 + 1] += N1 * f_edge
                    F[2 * n2 + 1] += N2 * f_edge

        return F

    # ---- Boundary conditions ----

    def apply_dirichlet_bc(
        self,
        K: sp.csr_matrix,
        F: np.ndarray,
        bc_list: List[BoundaryCondition],
        method: str = "penalty",
        penalty: float = 1e20,
    ) -> Tuple[sp.csr_matrix, np.ndarray]:
        """
        Áp đặt Dirichlet BC (displacement constraints).

        Methods:
          - "penalty": thêm penalty vào diagonal của K
          - "elimination": xóa DOF khỏi hệ (reduction)

        Args:
            K:         global stiffness matrix
            F:         force vector
            bc_list:   list of BoundaryCondition
            method:    "penalty" hoặc "elimination"
            penalty:   penalty factor cho method "penalty"

        Returns:
            K_mod, F_mod
        """
        if method == "elimination":
            return self._apply_elimination(K, F, bc_list)
        else:
            return self._apply_penalty(K, F, bc_list, penalty)

    def _apply_penalty(
        self,
        K: sp.csr_matrix,
        F: np.ndarray,
        bc_list: List[BoundaryCondition],
        penalty: float,
    ) -> Tuple[sp.csr_matrix, np.ndarray]:
        """Penalty method."""
        K_mod = K.copy()
        F_mod = F.copy()

        for bc in bc_list:
            dof_idx = self._dof_index(bc.node_id, bc.dof)
            K_mod[dof_idx, dof_idx] += penalty
            F_mod[dof_idx] += penalty * bc.value

        return K_mod, F_mod

    def _apply_elimination(
        self,
        K: sp.csr_matrix,
        F: np.ndarray,
        bc_list: List[BoundaryCondition],
    ) -> Tuple[sp.csr_matrix, np.ndarray]:
        """
        Elimination method – giảm kích thước hệ.

        Trả về K_reduced (n_free, n_free) sparse và F_reduced.
        """
        K_coo = K.tocoo()
        F_mod = F.copy()

        # Xác định all fixed DOFs
        fixed_dofs = set()
        for bc in bc_list:
            fixed_dofs.add(self._dof_index(bc.node_id, bc.dof))

        free_dofs = [d for d in range(self.n_dof) if d not in fixed_dofs]
        fixed_list = sorted(fixed_dofs)
        free_set = set(free_dofs)

        # Filter COO data: keep only rows/cols in free_dofs
        mask = [r in free_set and c in free_set for r, c in zip(K_coo.row, K_coo.col)]
        rows = K_coo.row[mask]
        cols = K_coo.col[mask]
        data = K_coo.data[mask]

        # Remap indices to reduced space
        index_map = {old: new for new, old in enumerate(free_dofs)}
        rows = np.array([index_map[r] for r in rows])
        cols = np.array([index_map[c] for c in cols])

        n_free = len(free_dofs)
        K_reduced = sp.csr_matrix((data, (rows, cols)), shape=(n_free, n_free))

        # Điều chỉnh F: F_i -= Σ K_ij * u_j (với j là fixed)
        for bc in bc_list:
            dof_j = self._dof_index(bc.node_id, bc.dof)
            F_mod[:] -= K[dof_j, :] * bc.value

        F_reduced = np.delete(F_mod, list(fixed_dofs))

        return K_reduced, F_reduced, free_dofs, fixed_dofs

    def recover_reactions(
        self,
        K_full: sp.csr_matrix,
        u_full: np.ndarray,
        bc_list: List[BoundaryCondition],
        F_external: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Khôi phục phản lực liên kết tại các DOF bị ràng buộc.

        R = K_full @ u_full - F_external

        Nếu F_external=None, trả về K*u (internal forces chưa trừ external).

        Args:
            K_full:      ma trận độ cứng đầy đủ (sparse)
            u_full:      vector chuyển vị đầy đủ (n_dof,)
            bc_list:     list of BoundaryCondition
            F_external:  vector lực ngoài đầy đủ (n_dof,) — KHÔNG phải F_reduced

        Returns:
            reactions: (n_dof,) – chỉ các DOF trong bc_list có giá trị
        """
        reactions = np.zeros(self.n_dof)

        # R = K @ u
        r_internal = K_full @ u_full

        if F_external is not None:
            r_internal = r_internal - F_external

        for bc in bc_list:
            dof_idx = self._dof_index(bc.node_id, bc.dof)
            reactions[dof_idx] = float(r_internal[dof_idx])

        return reactions

    # ---- Utility ----

    @staticmethod
    def _dof_index(node_id: int, dof: str) -> int:
        """Chuyển (node_id, dof) → global DOF index."""
        if dof in ("ux", "fx", "tx"):
            return 2 * node_id
        elif dof in ("uy", "fy", "ty"):
            return 2 * node_id + 1
        else:
            raise ValueError(f"Unknown DOF: {dof}")
