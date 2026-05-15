import numpy as np
import pytest

from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.stiffness import ElementStiffness


def test_material_parameter_validation():
    with pytest.raises(ValueError):
        MaterialModel(E=0.0, nu=0.3)
    with pytest.raises(ValueError):
        MaterialModel(E=210e9, nu=-0.1)
    with pytest.raises(ValueError):
        MaterialModel(E=210e9, nu=0.5)
    # nu=0 is now valid (e.g. cork-like materials)
    m = MaterialModel(E=210e9, nu=0.0)
    assert m.nu == 0.0


def test_material_stress_strain_roundtrip_for_plane_modes():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    strain = np.array([1.2e-4, -2.0e-5, 8.0e-5])

    for mode in [AnalysisType.PLANE_STRESS, AnalysisType.PLANE_STRAIN]:
        stress = material.stress_from_strain(strain, mode)
        strain_back = material.strain_from_stress(stress, mode)
        np.testing.assert_allclose(strain_back, strain, rtol=1e-12, atol=1e-12)


def test_von_mises_known_uniaxial_case():
    sigma = np.array([150e6, 0.0, 0.0])
    vm = MaterialModel.von_mises_stress(sigma)
    assert np.isclose(vm, 150e6, rtol=1e-12, atol=1e-12)


def test_material_presets_create_valid_models():
    presets = [
        MaterialModel.steel(),
        MaterialModel.aluminum(),
        MaterialModel.titanium(),
        MaterialModel.concrete(),
    ]
    for m in presets:
        assert m.E > 0.0
        assert 0.0 < m.nu < 0.5
        assert m.D_matrix(AnalysisType.PLANE_STRESS).shape == (3, 3)


def _rigid_body_modes(coords: np.ndarray) -> list[np.ndarray]:
    tx = np.array([v for _x, _y in coords for v in (1.0, 0.0)])
    ty = np.array([v for _x, _y in coords for v in (0.0, 1.0)])
    rz = np.array([v for x, y in coords for v in (-y, x)])
    return [tx, ty, rz]


def _assert_rigid_modes_near_nullspace(K: np.ndarray, coords: np.ndarray):
    normK = np.linalg.norm(K)
    for mode in _rigid_body_modes(coords):
        residual = np.linalg.norm(K @ mode)
        assert residual <= 1e-10 * max(1.0, normK)


def test_triangle_stiffness_symmetry_and_rigid_modes():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    builder = ElementStiffness(material, AnalysisType.PLANE_STRESS)
    coords = np.array([[0.0, 0.0], [2.0, 0.0], [0.3, 1.2]])

    K1 = builder.triangle(coords, order="1pt")
    K3 = builder.triangle(coords, order="3pt")
    K7 = builder.triangle(coords, order="7pt")

    np.testing.assert_allclose(K1, K1.T, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(K3, K3.T, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(K7, K7.T, rtol=1e-12, atol=1e-12)

    np.testing.assert_allclose(K1, K3, rtol=1e-12, atol=1e-8)
    np.testing.assert_allclose(K1, K7, rtol=1e-12, atol=1e-8)

    _assert_rigid_modes_near_nullspace(K3, coords)


def test_quad_stiffness_symmetry_and_rigid_modes():
    material = MaterialModel(E=70e9, nu=0.33, thickness=0.02)
    builder = ElementStiffness(material, AnalysisType.PLANE_STRESS)
    coords = np.array([[0.0, 0.0], [2.0, 0.0], [2.2, 1.1], [0.1, 1.0]])

    K2 = builder.quad(coords, order="2x2")
    K3 = builder.quad(coords, order="3x3")

    np.testing.assert_allclose(K2, K2.T, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(K3, K3.T, rtol=1e-12, atol=1e-12)

    # 2x2 and 3x3 should be very close on mild distortion.
    np.testing.assert_allclose(K2, K3, rtol=5e-3, atol=1e-3)
    _assert_rigid_modes_near_nullspace(K2, coords)


def test_element_stiffness_detects_negative_jacobian_orientation():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    builder = ElementStiffness(material, AnalysisType.PLANE_STRESS)

    tri_cw = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0]])
    with pytest.raises(ValueError, match="Negative Jacobian"):
        builder.triangle(tri_cw, order="3pt")

    quad_cw = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0]])
    with pytest.raises(ValueError, match="Negative Jacobian"):
        builder.quad(quad_cw, order="2x2")


def test_element_type_and_compute_dispatch():
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    builder = ElementStiffness(material, AnalysisType.PLANE_STRESS)

    tri = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    quad = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])

    assert builder.element_type(3) == "triangle"
    assert builder.element_type(4) == "quad"

    assert builder.compute(tri, order="3pt").shape == (6, 6)
    assert builder.compute(quad, order="2x2").shape == (8, 8)

    with pytest.raises(ValueError):
        builder.element_type(5)

    with pytest.raises(ValueError):
        builder.compute(np.zeros((5, 2)))
