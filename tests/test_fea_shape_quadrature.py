import numpy as np
from math import factorial

from app.engines.fea.gaussian_quadrature import GaussianQuadrature
from app.engines.fea.shape_functions import ShapeFunctions


def test_triangle_shape_functions_kronecker_and_partition_unity():
    sf = ShapeFunctions()

    node_points = [
        ((0.0, 0.0), np.array([1.0, 0.0, 0.0])),
        ((1.0, 0.0), np.array([0.0, 1.0, 0.0])),
        ((0.0, 1.0), np.array([0.0, 0.0, 1.0])),
    ]
    for (xi, eta), expected in node_points:
        np.testing.assert_allclose(sf.triangle_linear(xi, eta), expected, atol=1e-14)

    samples = [(0.2, 0.1), (0.1, 0.7), (1.0 / 3.0, 1.0 / 3.0)]
    for xi, eta in samples:
        N = sf.triangle_linear(xi, eta)
        assert np.isclose(np.sum(N), 1.0)
        assert np.all(N >= -1e-14)


def test_quad_shape_functions_kronecker_and_partition_unity():
    sf = ShapeFunctions()

    node_points = [
        ((-1.0, -1.0), np.array([1.0, 0.0, 0.0, 0.0])),
        ((1.0, -1.0), np.array([0.0, 1.0, 0.0, 0.0])),
        ((1.0, 1.0), np.array([0.0, 0.0, 1.0, 0.0])),
        ((-1.0, 1.0), np.array([0.0, 0.0, 0.0, 1.0])),
    ]
    for (xi, eta), expected in node_points:
        np.testing.assert_allclose(sf.quad_bilinear(xi, eta), expected, atol=1e-14)

    samples = [(-0.2, 0.1), (0.7, -0.4), (0.0, 0.0)]
    for xi, eta in samples:
        N = sf.quad_bilinear(xi, eta)
        assert np.isclose(np.sum(N), 1.0)


def test_shape_function_derivative_sums_are_zero():
    sf = ShapeFunctions()

    dN_dxi_tri, dN_deta_tri = sf.triangle_linear_derivatives()
    assert np.isclose(np.sum(dN_dxi_tri), 0.0)
    assert np.isclose(np.sum(dN_deta_tri), 0.0)

    dN_dxi_fn, dN_deta_fn = sf.quad_bilinear_derivatives()
    for xi, eta in [(-0.5, 0.2), (0.3, -0.9), (0.0, 0.0)]:
        assert np.isclose(np.sum(dN_dxi_fn(xi, eta)), 0.0)
        assert np.isclose(np.sum(dN_deta_fn(xi, eta)), 0.0)


def test_triangle_jacobian_orientation_sign():
    sf = ShapeFunctions()
    dN_dxi, dN_deta = sf.triangle_linear_derivatives()

    coords_ccw = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    _, det_ccw = sf.compute_jacobian_tri(dN_dxi, dN_deta, coords_ccw)
    assert det_ccw > 0.0

    coords_cw = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    _, det_cw = sf.compute_jacobian_tri(dN_dxi, dN_deta, coords_cw)
    assert det_cw < 0.0


def test_B_matrix_rigid_body_modes_give_zero_strain_triangle_and_quad():
    sf = ShapeFunctions()

    tri_coords = np.array([[0.0, 0.0], [1.2, 0.0], [0.2, 1.1]])
    dN_dxi_tri, dN_deta_tri = sf.triangle_linear_derivatives()
    J_tri, _ = sf.compute_jacobian_tri(dN_dxi_tri, dN_deta_tri, tri_coords)
    B_tri = sf.build_B_tri(dN_dxi_tri, dN_deta_tri, np.linalg.inv(J_tri), 3)

    u_tx_tri = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    u_ty_tri = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    theta = 1.0e-3
    u_rot_tri = np.array([v for x, y in tri_coords for v in (-theta * y, theta * x)])

    np.testing.assert_allclose(B_tri @ u_tx_tri, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(B_tri @ u_ty_tri, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(B_tri @ u_rot_tri, np.zeros(3), atol=1e-12)

    quad_coords = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]])
    dN_dxi_fn, dN_deta_fn = sf.quad_bilinear_derivatives()
    xi, eta = 0.23, -0.41
    dN_dxi_q = dN_dxi_fn(xi, eta)
    dN_deta_q = dN_deta_fn(xi, eta)
    J_quad, _ = sf.compute_jacobian_quad(dN_dxi_q, dN_deta_q, quad_coords)
    B_quad = sf.build_B_quad(dN_dxi_q, dN_deta_q, np.linalg.inv(J_quad), 4)

    u_tx_quad = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    u_ty_quad = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    u_rot_quad = np.array([v for x, y in quad_coords for v in (-theta * y, theta * x)])

    np.testing.assert_allclose(B_quad @ u_tx_quad, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(B_quad @ u_ty_quad, np.zeros(3), atol=1e-12)
    np.testing.assert_allclose(B_quad @ u_rot_quad, np.zeros(3), atol=1e-12)


def test_gaussian_rule_weight_sums():
    tri1 = GaussianQuadrature.triangle_1pt()
    tri3 = GaussianQuadrature.triangle_3pt()
    tri7 = GaussianQuadrature.triangle_7pt()

    assert np.isclose(sum(w for _, _, w in tri1), 0.5)
    assert np.isclose(sum(w for _, _, w in tri3), 0.5)
    assert np.isclose(sum(w for _, _, w in tri7), 0.5)

    quad2 = GaussianQuadrature.quad_2x2()
    quad3 = GaussianQuadrature.quad_3x3()
    assert np.isclose(sum(w for _, _, w in quad2), 4.0)
    assert np.isclose(sum(w for _, _, w in quad3), 4.0)


def test_integrate_constant_matches_area_for_all_rules():
    tri_coords = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 1.0]])
    tri_area = 1.0

    for rule in ["1pt", "3pt", "7pt"]:
        val = GaussianQuadrature.integrate_triangle(lambda xi, eta: 1.0, tri_coords, rule=rule)
        assert np.isclose(val, tri_area, rtol=1e-12, atol=1e-12)

    quad_coords = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 3.0], [0.0, 3.0]])
    quad_area = 6.0

    for rule in ["2x2", "3x3"]:
        val = GaussianQuadrature.integrate_quad(lambda xi, eta: 1.0, quad_coords, rule=rule)
        assert np.isclose(val, quad_area, rtol=1e-12, atol=1e-12)


def _triangle_reference_integral_monomial(p: int, q: int) -> float:
    # Integral over reference triangle {xi>=0, eta>=0, xi+eta<=1}
    return factorial(p) * factorial(q) / factorial(p + q + 2)


def _line_integral_even_power_on_minus1_1(power: int) -> float:
    if power % 2 == 1:
        return 0.0
    return 2.0 / (power + 1)


def test_triangle_gauss_rules_polynomial_exactness_orders():
    tri_ref = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])

    # 1-point centroid rule: exact for total degree <= 1.
    for p, q in [(0, 0), (1, 0), (0, 1)]:
        num = GaussianQuadrature.integrate_triangle(
            lambda xi, eta, p=p, q=q: xi**p * eta**q,
            tri_ref,
            rule="1pt",
        )
        exact = _triangle_reference_integral_monomial(p, q)
        assert np.isclose(num, exact, rtol=1e-12, atol=1e-12)

    # 3-point triangle rule: exact for total degree <= 2.
    for p, q in [(2, 0), (1, 1), (0, 2)]:
        num = GaussianQuadrature.integrate_triangle(
            lambda xi, eta, p=p, q=q: xi**p * eta**q,
            tri_ref,
            rule="3pt",
        )
        exact = _triangle_reference_integral_monomial(p, q)
        assert np.isclose(num, exact, rtol=1e-12, atol=1e-12)

    # 7-point Dunavant rule: exact for total degree <= 5.
    for p, q in [(5, 0), (4, 1), (3, 2), (2, 3), (1, 4), (0, 5)]:
        num = GaussianQuadrature.integrate_triangle(
            lambda xi, eta, p=p, q=q: xi**p * eta**q,
            tri_ref,
            rule="7pt",
        )
        exact = _triangle_reference_integral_monomial(p, q)
        assert np.isclose(num, exact, rtol=1e-12, atol=1e-12)


def test_quad_gauss_rules_polynomial_exactness_orders():
    # Identity mapping from natural to physical square [-1,1]x[-1,1].
    quad_ref = np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])

    # 2x2 tensor Gauss: exact for power <= 3 in each axis.
    for p, q in [(3, 0), (0, 3), (2, 2), (3, 2), (2, 3)]:
        num = GaussianQuadrature.integrate_quad(
            lambda xi, eta, p=p, q=q: xi**p * eta**q,
            quad_ref,
            rule="2x2",
        )
        exact = _line_integral_even_power_on_minus1_1(p) * _line_integral_even_power_on_minus1_1(q)
        assert np.isclose(num, exact, rtol=1e-12, atol=1e-12)

    # 3x3 tensor Gauss: exact for power <= 5 in each axis.
    for p, q in [(5, 0), (0, 5), (4, 4), (5, 4), (4, 5)]:
        num = GaussianQuadrature.integrate_quad(
            lambda xi, eta, p=p, q=q: xi**p * eta**q,
            quad_ref,
            rule="3x3",
        )
        exact = _line_integral_even_power_on_minus1_1(p) * _line_integral_even_power_on_minus1_1(q)
        assert np.isclose(num, exact, rtol=1e-12, atol=1e-12)
