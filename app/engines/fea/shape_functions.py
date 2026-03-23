"""
Shape Functions cho phần tử 2D.
Hỗ trợ:
  - Tam giác tuyến tính (3 node): N1 = (1-xi-eta), N2 = xi, N3 = eta
  - Tứ giác song tuyến (4 node): N_i = 0.25 * (1 + xi*xi_i) * (1 + eta*eta_i)
"""

import numpy as np
from typing import Tuple, List


class ShapeFunctions:
    """Bộ hàm dạng (shape functions) cho phần tử 2D."""

    # ========== Natural coordinates ==========

    @staticmethod
    def triangle_linear(xi: float, eta: float) -> np.ndarray:
        """
        Shape functions cho tam giác tuyến tính (3 node).

        N1 = 1 - xi - eta
        N2 = xi
        N3 = eta

        Args:
            xi:  Natural coordinate [0, 1]
            eta: Natural coordinate [0, 1]

        Returns:
            N: array shape (3,) – [N1, N2, N3]
        """
        N1 = 1.0 - xi - eta
        N2 = xi
        N3 = eta
        return np.array([N1, N2, N3])

    @staticmethod
    def triangle_linear_derivatives() -> Tuple[np.ndarray, np.ndarray]:
        """
        Đạo hàm của shape functions tam giác tuyến tính theo xi, eta.

        dN/dxi  = [-1, 1, 0]
        dN/deta = [-1, 0, 1]

        Returns:
            dN_dxi:  (3,) array
            dN_deta: (3,) array
        """
        dN_dxi = np.array([-1.0, 1.0, 0.0])
        dN_deta = np.array([-1.0, 0.0, 1.0])
        return dN_dxi, dN_deta

    @staticmethod
    def quad_bilinear(xi: float, eta: float) -> np.ndarray:
        """
        Shape functions cho tứ giác song tuyến tính (4 node).

        Node ordering (CCW):
          4 --- 3
          |     |
          1 --- 2

        N1 = 0.25*(1-xi)*(1-eta)  @ (-1, -1)
        N2 = 0.25*(1+xi)*(1-eta)  @ ( 1, -1)
        N3 = 0.25*(1+xi)*(1+eta)  @ ( 1,  1)
        N4 = 0.25*(1-xi)*(1+eta)  @ (-1,  1)

        Args:
            xi:  Natural coord [-1, 1]
            eta: Natural coord [-1, 1]

        Returns:
            N: array shape (4,) – [N1, N2, N3, N4]
        """
        N1 = 0.25 * (1.0 - xi) * (1.0 - eta)
        N2 = 0.25 * (1.0 + xi) * (1.0 - eta)
        N3 = 0.25 * (1.0 + xi) * (1.0 + eta)
        N4 = 0.25 * (1.0 - xi) * (1.0 + eta)
        return np.array([N1, N2, N3, N4])

    @staticmethod
    def quad_bilinear_derivatives() -> Tuple[np.ndarray, np.ndarray]:
        """
        Đạo hàm shape functions tứ giác song tuyến tính.

        dN/dxi  =  0.25 * [ -(1-eta), (1-eta), (1+eta), -(1+eta) ]
        dN/deta =  0.25 * [ -(1-xi), -(1+xi), (1+xi),  (1-xi) ]

        Returns:
            dN_dxi:  (4,) array evaluated at generic (xi, eta)
            dN_deta: (4,) array evaluated at generic (xi, eta)
        """
        # Return symbolic lambda so caller passes xi, eta
        def dN_dxi(xi: float, eta: float) -> np.ndarray:
            return 0.25 * np.array([
                -(1.0 - eta),
                 (1.0 - eta),
                 (1.0 + eta),
                -(1.0 + eta),
            ])

        def dN_deta(xi: float, eta: float) -> np.ndarray:
            return 0.25 * np.array([
                -(1.0 - xi),
                -(1.0 + xi),
                 (1.0 + xi),
                 (1.0 - xi),
            ])

        return dN_dxi, dN_deta

    # ========== Jacobian ==========

    @staticmethod
    def compute_jacobian_tri(
        dN_dxi: np.ndarray,
        dN_deta: np.ndarray,
        coords: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """
        Jacobian cho phần tử tam giác.

        J = [dx/dxi   dy/dxi  ]
            [dx/deta  dy/deta ]

        Với: dx/dxi = sum(dN_dxi[i] * x_i), etc.

        Args:
            dN_dxi:  (3,) – đạo hàm theo xi
            dN_deta: (3,) – đạo hàm theo eta
            coords:  (3, 2) – tọa độ node [x, y]

        Returns:
            J:  (2, 2) Jacobian matrix
            detJ: determinant
        """
        dx_dxi  = np.dot(dN_dxi,  coords[:, 0])
        dy_dxi  = np.dot(dN_dxi,  coords[:, 1])
        dx_deta = np.dot(dN_deta, coords[:, 0])
        dy_deta = np.dot(dN_deta, coords[:, 1])

        J = np.array([
            [dx_dxi,  dy_dxi],
            [dx_deta, dy_deta],
        ])
        detJ = dx_dxi * dy_deta - dy_dxi * dx_deta

        return J, detJ

    @staticmethod
    def compute_jacobian_quad(
        dN_dxi: np.ndarray,
        dN_deta: np.ndarray,
        coords: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """
        Jacobian cho phần tử tứ giác.

        Args:
            dN_dxi:  (4,) – đạo hàm theo xi
            dN_deta: (4,) – đạo hàm theo eta
            coords:  (4, 2) – tọa độ node CCW

        Returns:
            J:  (2, 2)
            detJ: determinant
        """
        dx_dxi  = np.dot(dN_dxi,  coords[:, 0])
        dy_dxi  = np.dot(dN_dxi,  coords[:, 1])
        dx_deta = np.dot(dN_deta, coords[:, 0])
        dy_deta = np.dot(dN_deta, coords[:, 1])

        J = np.array([
            [dx_dxi,  dy_dxi],
            [dx_deta, dy_deta],
        ])
        detJ = dx_dxi * dy_deta - dy_dxi * dx_deta

        return J, detJ

    # ========== B-matrix (strain-displacement) ==========

    @staticmethod
    def build_B_tri(
        dN_dxi: np.ndarray,
        dN_deta: np.ndarray,
        J_inv: np.ndarray,
        n_nodes: int = 3,
    ) -> np.ndarray:
        """
        Build B-matrix cho tam giác tuyến tính.

        B = [ dN1/dx   0      dN2/dx   0      dN3/dx   0    ]
            [   0    dN1/dy     0    dN2/dy     0    dN3/dy ]
            [ dN1/dy dN1/dx  dN2/dy dN2/dx  dN3/dy dN3/dx ]

        Với: [dN/dx, dN/dy]^T = J^{-1} * [dN/dxi, dN/deta]^T

        Args:
            dN_dxi:  (3,)
            dN_deta: (3,)
            J_inv:   (2, 2) – inverse Jacobian
            n_nodes: 3 for triangle

        Returns:
            B: (3, 6) strain-displacement matrix
        """
        # Transform derivatives to physical space
        dN_dx = J_inv[0, 0] * dN_dxi + J_inv[0, 1] * dN_deta
        dN_dy = J_inv[1, 0] * dN_dxi + J_inv[1, 1] * dN_deta

        B = np.zeros((3, 2 * n_nodes))
        for i in range(n_nodes):
            B[0, 2 * i]     = dN_dx[i]
            B[1, 2 * i + 1] = dN_dy[i]
            B[2, 2 * i]     = dN_dy[i]
            B[2, 2 * i + 1] = dN_dx[i]

        return B

    @staticmethod
    def build_B_quad(
        dN_dxi: np.ndarray,
        dN_deta: np.ndarray,
        J_inv: np.ndarray,
        n_nodes: int = 4,
    ) -> np.ndarray:
        """
        Build B-matrix cho tứ giác song tuyến tính (4 node).

        Args:
            dN_dxi:  (4,)
            dN_deta: (4,)
            J_inv:   (2, 2)
            n_nodes: 4 for quad

        Returns:
            B: (3, 8) strain-displacement matrix
        """
        dN_dx = J_inv[0, 0] * dN_dxi + J_inv[0, 1] * dN_deta
        dN_dy = J_inv[1, 0] * dN_dxi + J_inv[1, 1] * dN_deta

        B = np.zeros((3, 2 * n_nodes))
        for i in range(n_nodes):
            B[0, 2 * i]     = dN_dx[i]
            B[1, 2 * i + 1] = dN_dy[i]
            B[2, 2 * i]     = dN_dy[i]
            B[2, 2 * i + 1] = dN_dx[i]

        return B

    # ========== Strain from displacement ==========

    @staticmethod
    def compute_strain(B: np.ndarray, u_elem: np.ndarray) -> np.ndarray:
        """
        Tính strain từ B-matrix và displacement vector.

        strain = B * u_elem

        Args:
            B:       (3, n_dof) strain-displacement matrix
            u_elem: (n_dof,) displacement của phần tử

        Returns:
            strain: (3,) – [exx, eyy, gxy]
        """
        return B @ u_elem

    # ========== Coordinate mapping ==========

    @staticmethod
    def physical_coords(N: np.ndarray, coords: np.ndarray) -> np.ndarray:
        """
        Map từ natural → physical coordinates.

        x_phys = sum(N_i * x_i)

        Args:
            N:     (n_nodes,) shape function values
            coords: (n_nodes, 2) node coordinates

        Returns:
            (2,) – [x, y] in physical space
        """
        return N @ coords
