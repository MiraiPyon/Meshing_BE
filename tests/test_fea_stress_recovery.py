import numpy as np

from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.stress_recovery import StressRecovery


def _linear_field_displacements(
    nodes: np.ndarray,
    a: float,
    b: float,
    c: float,
    d: float,
    e: float,
    f: float,
) -> np.ndarray:
    """u_x = a*x + b*y + c, u_y = d*x + e*y + f"""
    u = np.zeros((len(nodes), 2))
    for i, (x, y) in enumerate(nodes):
        u[i, 0] = a * x + b * y + c
        u[i, 1] = d * x + e * y + f
    return u


def _to_u_elem(coords: np.ndarray, disp_nodes: np.ndarray) -> np.ndarray:
    u_elem = np.zeros(2 * len(coords))
    for i in range(len(coords)):
        u_elem[2 * i] = disp_nodes[i, 0]
        u_elem[2 * i + 1] = disp_nodes[i, 1]
    return u_elem


def test_compute_element_stress_zero_displacement_returns_zero_for_triangle_and_quad():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    recovery = StressRecovery(material, AnalysisType.PLANE_STRESS)

    tri_coords = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    tri_u = np.zeros(6)
    tri_stress, tri_strain, tri_gp = recovery.compute_element_stress(tri_coords, tri_u, order="3pt")
    np.testing.assert_allclose(tri_stress, 0.0, atol=1e-14)
    np.testing.assert_allclose(tri_strain, 0.0, atol=1e-14)
    assert tri_gp.shape == (3, 2)

    quad_coords = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]])
    quad_u = np.zeros(8)
    quad_stress, quad_strain, quad_gp = recovery.compute_element_stress(quad_coords, quad_u, order="2x2")
    np.testing.assert_allclose(quad_stress, 0.0, atol=1e-14)
    np.testing.assert_allclose(quad_strain, 0.0, atol=1e-14)
    assert quad_gp.shape == (4, 2)


def test_compute_element_stress_triangle_matches_linear_field_exactly():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    recovery = StressRecovery(material, AnalysisType.PLANE_STRESS)

    coords = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 1.5]])
    disp_nodes = _linear_field_displacements(coords, a=1.0e-4, b=2.0e-5, c=0.0, d=-3.0e-5, e=6.0e-5, f=1.0e-6)
    u_elem = _to_u_elem(coords, disp_nodes)

    stress_gp, strain_gp, _ = recovery.compute_element_stress(coords, u_elem, order="7pt")

    expected_strain = np.array([1.0e-4, 6.0e-5, -1.0e-5])  # [exx, eyy, gxy=b+d]
    expected_stress = recovery.D @ expected_strain

    np.testing.assert_allclose(
        strain_gp,
        np.tile(expected_strain, (strain_gp.shape[0], 1)),
        rtol=1e-10,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        stress_gp,
        np.tile(expected_stress, (stress_gp.shape[0], 1)),
        rtol=1e-10,
        atol=1e-3,
    )


def test_compute_element_stress_quad_matches_linear_field_exactly():
    material = MaterialModel(E=70e9, nu=0.33, thickness=0.02)
    recovery = StressRecovery(material, AnalysisType.PLANE_STRESS)

    coords = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]])
    disp_nodes = _linear_field_displacements(coords, a=2.0e-4, b=-4.0e-5, c=3.0e-6, d=1.0e-5, e=-1.0e-4, f=-2.0e-6)
    u_elem = _to_u_elem(coords, disp_nodes)

    for order, expected_gp in [("2x2", 4), ("3x3", 9)]:
        stress_gp, strain_gp, gp_coords = recovery.compute_element_stress(coords, u_elem, order=order)
        expected_strain = np.array([2.0e-4, -1.0e-4, -3.0e-5])
        expected_stress = recovery.D @ expected_strain

        np.testing.assert_allclose(
            strain_gp,
            np.tile(expected_strain, (strain_gp.shape[0], 1)),
            rtol=1e-10,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            stress_gp,
            np.tile(expected_stress, (stress_gp.shape[0], 1)),
            rtol=1e-10,
            atol=1e-2,
        )
        assert gp_coords.shape == (expected_gp, 2)


def test_average_to_nodes_single_quad_uniform_field():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    recovery = StressRecovery(material, AnalysisType.PLANE_STRESS)

    nodes = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]])
    elements = [[0, 1, 2, 3]]

    disp_nodes = _linear_field_displacements(nodes, a=1.5e-4, b=4.0e-5, c=0.0, d=2.0e-5, e=-7.0e-5, f=0.0)
    u_elem = _to_u_elem(nodes, disp_nodes)

    gp_stress, _gp_strain, gp_coords = recovery.compute_element_stress(nodes, u_elem, order="2x2")
    nodal_stress, nodal_strain = recovery.average_to_nodes(
        nodes=nodes,
        elements=elements,
        displacements=disp_nodes,
        gp_stresses=[gp_stress],
        gp_gp_coords=[gp_coords],
    )

    expected_strain = np.array([1.5e-4, -7.0e-5, 6.0e-5])
    expected_stress = recovery.D @ expected_strain

    for n in range(len(nodes)):
        np.testing.assert_allclose(nodal_strain[n], expected_strain, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(nodal_stress[n], expected_stress, rtol=1e-10, atol=1e-2)
