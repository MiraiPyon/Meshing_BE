"""
Element Stiffness Matrix – Tính ma trận độ cứng phần tử.
K_e = ∫ B^T · D · B · t · dA
"""

import numpy as np
from typing import Tuple, List
from app.engines.fea.shape_functions import ShapeFunctions
from app.engines.fea.gaussian_quadrature import GaussianQuadrature
from app.engines.fea.material import MaterialModel, AnalysisType


class ElementStiffness:
    """
    Tính ma trận độ cứng phần tử cho tam giác và tứ giác.
    """

    def __init__(self, material: MaterialModel, analysis_type: AnalysisType = AnalysisType.PLANE_STRESS):
        """
        Args:
            material: MaterialModel instance
            analysis_type: plane_stress hoặc plane_strain
        """
        self.material = material
        self.analysis_type = analysis_type
        self.sf = ShapeFunctions()
        self.D = material.D_matrix(analysis_type)
        self.t = material.thickness

    def triangle(self, coords: np.ndarray, order: str = "3pt") -> np.ndarray:
        """
        Ma trận độ cứng phần tử tam giác (3 node, linear).

        K_e = ∫ B^T · D · B · t · dA

        Args:
            coords: (3, 2) – tọa độ 3 node (1-based → 0-based internally)
            order:  "1pt", "3pt", "7pt"

        Returns:
            K_e: (6, 6) symmetric stiffness matrix
        """
        dN_dxi, dN_deta = self.sf.triangle_linear_derivatives()
        n_nodes = 3
        n_dof = 2 * n_nodes
        K_e = np.zeros((n_dof, n_dof))

        if order == "1pt":
            gps = GaussianQuadrature.triangle_1pt()
        elif order == "7pt":
            gps = GaussianQuadrature.triangle_7pt()
        else:
            gps = GaussianQuadrature.triangle_3pt()

        for xi, eta, w in gps:
            # Jacobian
            J, detJ = self.sf.compute_jacobian_tri(dN_dxi, dN_deta, coords)

            if detJ <= 0:
                raise ValueError(f"Negative Jacobian detJ={detJ} at (xi={xi}, eta={eta}). Check element orientation (CCW).")

            J_inv = np.linalg.inv(J)

            # B-matrix
            B = self.sf.build_B_tri(dN_dxi, dN_deta, J_inv, n_nodes)

            # K_e += B^T · D · B · t · detJ · w
            K_e += B.T @ self.D @ B * self.t * detJ * w

        return K_e

    def quad(self, coords: np.ndarray, order: str = "2x2") -> np.ndarray:
        """
        Ma trận độ cứng phần tử tứ giác (4 node, bilinear).

        K_e = ∫ B^T · D · B · t · dA

        Args:
            coords: (4, 2) – tọa độ 4 node CCW
            order:  "2x2" hoặc "3x3"

        Returns:
            K_e: (8, 8) symmetric stiffness matrix
        """
        dN_dxi_fn, dN_deta_fn = self.sf.quad_bilinear_derivatives()
        n_nodes = 4
        n_dof = 2 * n_nodes
        K_e = np.zeros((n_dof, n_dof))

        if order == "3x3":
            gps = GaussianQuadrature.quad_3x3()
        else:
            gps = GaussianQuadrature.quad_2x2()

        for xi, eta, w in gps:
            dN_dxi = dN_dxi_fn(xi, eta)
            dN_deta = dN_deta_fn(xi, eta)

            J, detJ = self.sf.compute_jacobian_quad(dN_dxi, dN_deta, coords)

            if detJ <= 0:
                raise ValueError(f"Negative Jacobian detJ={detJ} at (xi={xi}, eta={eta}). Check element orientation (CCW).")

            J_inv = np.linalg.inv(J)
            B = self.sf.build_B_quad(dN_dxi, dN_deta, J_inv, n_nodes)

            K_e += B.T @ self.D @ B * self.t * detJ * w

        return K_e

    def element_type(self, n_nodes: int) -> str:
        """Xác định loại phần tử từ số node."""
        if n_nodes == 3:
            return "triangle"
        elif n_nodes == 4:
            return "quad"
        else:
            raise ValueError(f"Unsupported element type with {n_nodes} nodes")

    def compute(self, coords: np.ndarray, order: str = "2x2") -> np.ndarray:
        """
        Tự động chọn phương pháp theo số node.

        Args:
            coords: (n, 2) node coordinates
            order:  integration order

        Returns:
            K_e: (2*n, 2*n) stiffness matrix
        """
        n_nodes = len(coords)
        if n_nodes == 3:
            return self.triangle(coords, order)
        elif n_nodes == 4:
            return self.quad(coords, order)
        else:
            raise ValueError(f"Unsupported element with {n_nodes} nodes")
