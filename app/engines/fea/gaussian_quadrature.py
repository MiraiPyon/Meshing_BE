"""
Gaussian Quadrature – Tích phân số cho phần tử 2D.
"""

import numpy as np
from typing import List, Tuple


class GaussianQuadrature:
    """Các scheme tích phân Gaussian 2D."""

    # ---- 1 điểm (order 1) ----
    @staticmethod
    def triangle_1pt() -> List[Tuple[float, float, float]]:
        """
        1 điểm Gauss cho tam giác.
        Trọng số = 1/2 (vì diện tích tam giác chuẩn = 1/2)

        Point: centroid (1/3, 1/3)
        Weight: 1/2

        Returns:
            List of (xi, eta, weight)
        """
        return [(1.0 / 3.0, 1.0 / 3.0, 0.5)]

    # ---- 3 điểm (order 2) ----
    @staticmethod
    def triangle_3pt() -> List[Tuple[float, float, float]]:
        """
        3 điểm Gauss cho tam giác.

        Points:
          (1/2, 1/2), (1/2, 0), (0, 1/2)
        Weights:
          1/6 each

        Returns:
            List of (xi, eta, weight)
        """
        return [
            (0.5, 0.5, 1.0 / 6.0),
            (0.5, 0.0, 1.0 / 6.0),
            (0.0, 0.5, 1.0 / 6.0),
        ]

    # ---- 7 điểm (order 4) ----
    @staticmethod
    def triangle_7pt() -> List[Tuple[float, float, float]]:
        """
        7 điểm Gauss cho tam giác (Dunavant, exact đến bậc 5).

        Lưu ý: các trọng số Dunavant chuẩn có tổng bằng 1.0 trên tam giác
        tham chiếu diện tích 1.0, trong khi phần tử tam giác chuẩn ở đây có
        diện tích 0.5. Vì vậy ta nhân 0.5 cho toàn bộ trọng số.

        Returns:
            List of (xi, eta, weight)
        """
        scale = 0.5
        w1 = 0.225000000000000 * scale
        w2 = 0.132394152788506 * scale
        w3 = 0.125939180544827 * scale

        a = 0.059715871789770
        b = 0.470142064105115
        c = 0.797426985353087
        d = 0.101286507323456

        return [
            (1.0 / 3.0, 1.0 / 3.0, w1),
            (a, b, w2),
            (b, a, w2),
            (b, b, w2),
            (c, d, w3),
            (d, c, w3),
            (d, d, w3),
        ]

    # ---- 2×2 Gauss (tứ giác) ----
    @staticmethod
    def quad_2x2() -> List[Tuple[float, float, float]]:
        """
        2×2 = 4 điểm Gauss cho tứ giác.

        Points: (±1/√3, ±1/√3)
        Weights: 1.0 each

        Returns:
            List of (xi, eta, weight)
        """
        g = 1.0 / np.sqrt(3.0)
        return [
            (-g, -g, 1.0),
            ( g, -g, 1.0),
            ( g,  g, 1.0),
            (-g,  g, 1.0),
        ]

    # ---- 3×3 Gauss (tứ giác) ----
    @staticmethod
    def quad_3x3() -> List[Tuple[float, float, float]]:
        """
        3×3 = 9 điểm Gauss cho tứ giác.

        Points: (±√(3/5), ±√(3/5))
        Weights: 5/9 each (corner) and 8/9 (center edges)

        Returns:
            List of (xi, eta, weight)
        """
        ga = np.sqrt(3.0 / 5.0)
        w_a = 5.0 / 9.0
        w_b = 8.0 / 9.0

        return [
            # 4 corners
            (-ga, -ga, w_a * w_a),
            ( ga, -ga, w_a * w_a),
            ( ga,  ga, w_a * w_a),
            (-ga,  ga, w_a * w_a),
            # 4 edge midpoints
            (0.0, -ga, w_b * w_a),
            (0.0,  ga, w_b * w_a),
            (-ga, 0.0, w_a * w_b),
            ( ga, 0.0, w_a * w_b),
            # center
            (0.0, 0.0, w_b * w_b),
        ]

    # ---- Integration helpers ----

    @staticmethod
    def integrate_triangle(
        func,
        coords: np.ndarray,
        rule: str = "3pt",
    ) -> float:
        """
        Tích phân hàm trên tam giác.

        ∫ f(x,y) dA  ≈  Σ  f(xi,eta) * detJ(gp) * w(gp)

        Args:
            func:    callable f(xi, eta) → scalar or array
            coords:  (3, 2) node coordinates
            rule:    "1pt", "3pt", or "7pt"

        Returns:
            Integral value
        """
        from app.engines.fea.shape_functions import ShapeFunctions

        sf = ShapeFunctions()
        dN_dxi, dN_deta = sf.triangle_linear_derivatives()

        if rule == "1pt":
            gps = GaussianQuadrature.triangle_1pt()
        elif rule == "7pt":
            gps = GaussianQuadrature.triangle_7pt()
        else:
            gps = GaussianQuadrature.triangle_3pt()

        result = 0.0
        for xi, eta, w in gps:
            J, detJ = sf.compute_jacobian_tri(dN_dxi, dN_deta, coords)
            val = func(xi, eta)
            result += val * detJ * w

        return result

    @staticmethod
    def integrate_quad(
        func,
        coords: np.ndarray,
        rule: str = "2x2",
    ) -> float:
        """
        Tích phân hàm trên tứ giác.

        ∫ f(x,y) dA  ≈  Σ  f(xi,eta) * detJ(gp) * w_xi * w_eta

        Args:
            func:  callable f(xi, eta) → scalar or array
            coords: (4, 2) node coordinates (CCW)
            rule:  "2x2" or "3x3"

        Returns:
            Integral value
        """
        from app.engines.fea.shape_functions import ShapeFunctions

        sf = ShapeFunctions()
        dN_dxi_fn, dN_deta_fn = sf.quad_bilinear_derivatives()

        if rule == "3x3":
            gps = GaussianQuadrature.quad_3x3()
        else:
            gps = GaussianQuadrature.quad_2x2()

        result = 0.0
        for xi, eta, w in gps:
            dN_dxi  = dN_dxi_fn(xi, eta)
            dN_deta = dN_deta_fn(xi, eta)
            J, detJ = sf.compute_jacobian_quad(dN_dxi, dN_deta, coords)
            val = func(xi, eta)
            result += val * detJ * w

        return result
