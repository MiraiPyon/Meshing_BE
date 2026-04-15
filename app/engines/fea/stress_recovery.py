"""
Stress Recovery – Tính stress/strain tại integration points và nodes.
"""

import numpy as np
from typing import List, Tuple
from app.engines.fea.shape_functions import ShapeFunctions
from app.engines.fea.gaussian_quadrature import GaussianQuadrature
from app.engines.fea.material import MaterialModel, AnalysisType


class StressRecovery:
    """
    Tính toán ứng suất (stress) và biến dạng (strain) từ displacements.

    Tại mỗi phần tử:
      ε = B · u_e
      σ = D · ε
    """

    def __init__(self, material: MaterialModel, analysis_type: AnalysisType = AnalysisType.PLANE_STRESS):
        self.material = material
        self.analysis_type = analysis_type
        self.sf = ShapeFunctions()
        self.D = material.D_matrix(analysis_type)
        self.t = material.thickness

    def compute_element_stress(
        self,
        coords: np.ndarray,
        u_elem: np.ndarray,
        order: str = "3pt",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Tính stress và strain tại mỗi Gauss point của phần tử.

        Args:
            coords:  (n_nodes, 2) tọa độ node (0-based)
            u_elem: (2*n_nodes,) vector chuyển vị phần tử
            order:  "1pt", "3pt", "7pt" cho tam giác; "2x2", "3x3" cho tứ giác

        Returns:
            stresses_gp:  (n_gp, 3) – [sxx, syy, txy] tại mỗi GP
            strains_gp:  (n_gp, 3) – [exx, eyy, gxy] tại mỗi GP
            gp_coords:   (n_gp, 2) – tọa độ Gauss points (physical)
        """
        n_nodes = len(coords)
        is_tri = n_nodes == 3

        if is_tri:
            gps = self._get_gps_tri(order)
            dN_dxi, dN_deta = self.sf.triangle_linear_derivatives()
        else:
            gps = self._get_gps_quad(order)
            dN_dxi_fn, dN_deta_fn = self.sf.quad_bilinear_derivatives()

        stresses_gp = []
        strains_gp = []
        gp_coords = []

        for gp in gps:
            if is_tri:
                xi, eta, w = gp
                dN_dxi_gp = dN_dxi
                dN_deta_gp = dN_deta
            else:
                xi, eta, w = gp
                dN_dxi_gp = dN_dxi_fn(xi, eta)
                dN_deta_gp = dN_deta_fn(xi, eta)

            # Jacobian
            if is_tri:
                J, detJ = self.sf.compute_jacobian_tri(dN_dxi_gp, dN_deta_gp, coords)
            else:
                J, detJ = self.sf.compute_jacobian_quad(dN_dxi_gp, dN_deta_gp, coords)

            J_inv = np.linalg.inv(J)

            # B-matrix
            if is_tri:
                B = self.sf.build_B_tri(dN_dxi_gp, dN_deta_gp, J_inv, 3)
            else:
                B = self.sf.build_B_quad(dN_dxi_gp, dN_deta_gp, J_inv, 4)

            # Strain & stress
            strain = B @ u_elem
            stress = self.D @ strain

            stresses_gp.append(stress)
            strains_gp.append(strain)

            # Gauss point coordinate in physical space
            if is_tri:
                N = self.sf.triangle_linear(xi, eta)
            else:
                N = self.sf.quad_bilinear(xi, eta)
            gp_coords.append(self.sf.physical_coords(N, coords))

        return (
            np.array(stresses_gp),
            np.array(strains_gp),
            np.array(gp_coords),
        )

    def average_to_nodes(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        displacements: np.ndarray,
        gp_stresses: List[np.ndarray],
        gp_gp_coords: List[np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Nội suy stress từ Gauss points về nodes (extrapolation).

        Sử dụng: σ_node = Σ N_i(GP) * σ(GP) / Σ N_i(GP)

        Args:
            nodes:        (n_nodes, 2)
            elements:     list of (n_nodes_per_elem,) connectivity
            displacements: (n_nodes, 2)
            gp_stresses:  list of (n_gp_elem, 3) stress per element
            gp_gp_coords: list of (n_gp_elem, 2) GP coordinates per element

        Returns:
            node_stresses:  (n_nodes, 3) – averaged stress at each node
            node_strains:  (n_nodes, 3) – averaged strain at each node
        """
        n_nodes = len(nodes)
        node_stress_sum = np.zeros((n_nodes, 3))
        weight_sum = np.zeros(n_nodes)

        for e_idx, elem in enumerate(elements):
            coords = nodes[elem]
            is_tri = len(elem) == 3

            gp_stress = gp_stresses[e_idx]
            gp_coords_elem = gp_gp_coords[e_idx]

            for gp_i in range(len(gp_stress)):
                gp_pos = gp_coords_elem[gp_i]

                # Shape functions evaluated at GP in physical space
                # For extrapolation: find natural coords
                if is_tri:
                    xi, eta = self._physical_to_natural_tri(gp_pos, coords)
                    N = self.sf.triangle_linear(xi, eta)
                else:
                    xi, eta = self._physical_to_natural_quad(gp_pos, coords)
                    N = self.sf.quad_bilinear(xi, eta)

                # Accumulate weighted contributions
                for local_i, node_g in enumerate(elem):
                    w = max(N[local_i], 0.0)  # non-negative weight
                    node_stress_sum[node_g] += w * gp_stress[gp_i]
                    weight_sum[node_g] += w

        # Average
        node_stresses = np.zeros((n_nodes, 3))
        for n in range(n_nodes):
            if weight_sum[n] > 0:
                node_stresses[n] = node_stress_sum[n] / weight_sum[n]

        # Compute strains from displacements directly
        node_strains = self._compute_nodal_strains(nodes, elements, displacements)

        return node_stresses, node_strains

    def _extract_elem_disp(self, elem: List[int], displacements: np.ndarray) -> np.ndarray:
        """Extract element DOF vector from global displacement."""
        u_elem = np.zeros(2 * len(elem))
        for i, n in enumerate(elem):
            u_elem[2 * i]     = displacements[n, 0]
            u_elem[2 * i + 1] = displacements[n, 1]
        return u_elem

    def _compute_nodal_strains(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        displacements: np.ndarray,
    ) -> np.ndarray:
        """Compute strain at each node by averaging element contributions."""
        n_nodes = len(nodes)

        strain_sum = np.zeros((n_nodes, 3))
        count = np.zeros(n_nodes)

        for elem in elements:
            coords = nodes[elem]
            u_elem = self._extract_elem_disp(elem, displacements)
            n_nodes_elem = len(elem)

            # Compute strain at element centroid
            if n_nodes_elem == 3:
                dN_dxi, dN_deta = self.sf.triangle_linear_derivatives()
                centroid_xi, centroid_eta = 1.0 / 3.0, 1.0 / 3.0
                dN_dxi_gp = dN_dxi
                dN_deta_gp = dN_deta
            else:
                dN_dxi_fn, dN_deta_fn = self.sf.quad_bilinear_derivatives()
                centroid_xi, centroid_eta = 0.0, 0.0
                dN_dxi_gp = dN_dxi_fn(centroid_xi, centroid_eta)
                dN_deta_gp = dN_deta_fn(centroid_xi, centroid_eta)

            if n_nodes_elem == 3:
                J, detJ = self.sf.compute_jacobian_tri(dN_dxi_gp, dN_deta_gp, coords)
            else:
                J, detJ = self.sf.compute_jacobian_quad(dN_dxi_gp, dN_deta_gp, coords)

            J_inv = np.linalg.inv(J)

            if n_nodes_elem == 3:
                B = self.sf.build_B_tri(dN_dxi_gp, dN_deta_gp, J_inv, 3)
            else:
                B = self.sf.build_B_quad(dN_dxi_gp, dN_deta_gp, J_inv, 4)

            strain = B @ u_elem

            # Average to nodes
            for node_g in elem:
                strain_sum[node_g] += strain
                count[node_g] += 1

        # Average
        node_strains = np.zeros((n_nodes, 3))
        for n in range(n_nodes):
            if count[n] > 0:
                node_strains[n] = strain_sum[n] / count[n]

        return node_strains

    @staticmethod
    def _physical_to_natural_tri(p: np.ndarray, coords: np.ndarray) -> Tuple[float, float]:
        """Map physical point → natural coords for triangle (approximate)."""
        x, y = p
        x1, y1 = coords[0]
        x2, y2 = coords[1]
        x3, y3 = coords[2]

        area = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))
        if area < 1e-12:
            return 0.0, 0.0

        xi  = ((y2 - y1) * (x - x3) - (x2 - x1) * (y - y3)) / area + 1.0 / 3.0
        eta = ((y3 - y1) * (x - x2) - (x3 - x1) * (y - y2)) / area + 1.0 / 3.0

        xi = np.clip(xi, 0.0, 1.0)
        eta = np.clip(eta, 0.0, 1.0 - xi)
        return xi, eta

    @staticmethod
    def _physical_to_natural_quad(p: np.ndarray, coords: np.ndarray) -> Tuple[float, float]:
        """Map physical point → natural coords for quad (approximate)."""
        x, y = p
        # For a bilinear quad, invert approximately using centroid + Newton
        cx = coords[:, 0].mean()
        cy = coords[:, 1].mean()
        dx = x - cx
        dy = y - cy

        # Estimate from element size
        dx_elem = max(abs(coords[1, 0] - coords[0, 0]), abs(coords[3, 0] - coords[0, 0]))
        dy_elem = max(abs(coords[3, 1] - coords[0, 1]), abs(coords[1, 1] - coords[0, 1]))

        if dx_elem > 1e-12:
            xi = np.clip(dx / (dx_elem / 2.0), -1.0, 1.0)
        else:
            xi = 0.0

        if dy_elem > 1e-12:
            eta = np.clip(dy / (dy_elem / 2.0), -1.0, 1.0)
        else:
            eta = 0.0

        return xi, eta

    @staticmethod
    def _get_gps_tri(order: str) -> List[Tuple[float, float, float]]:
        if order == "1pt":
            return GaussianQuadrature.triangle_1pt()
        elif order == "7pt":
            return GaussianQuadrature.triangle_7pt()
        return GaussianQuadrature.triangle_3pt()

    @staticmethod
    def _get_gps_quad(order: str) -> List[Tuple[float, float, float]]:
        if order == "3x3":
            return GaussianQuadrature.quad_3x3()
        return GaussianQuadrature.quad_2x2()
