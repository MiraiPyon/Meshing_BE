import numpy as np

from app.engines.fea.assembly import BoundaryCondition
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _single_quad_solver() -> FEASolver:
    nodes = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 1.0],
            [0.0, 1.0],
        ]
    )
    elements = [[1, 2, 3, 4]]
    return FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )


def test_global_stiffness_is_symmetric():
    solver = _single_quad_solver()
    solver.setup()

    K = solver._K_full.toarray()
    np.testing.assert_allclose(K, K.T, rtol=1e-12, atol=1e-12)


def test_unconstrained_single_quad_has_three_rigid_body_modes():
    solver = _single_quad_solver()
    solver.setup()

    K = solver._K_full.toarray()
    eigvals = np.linalg.eigvalsh(K)

    max_abs = max(abs(eigvals[-1]), 1.0)
    # 2 translations + 1 in-plane rotation.
    near_zero = np.sum(np.abs(eigvals) < 1e-10 * max_abs)
    assert near_zero == 3

    positive_modes = eigvals[np.abs(eigvals) >= 1e-10 * max_abs]
    assert np.all(positive_modes > 0.0)


def test_constrained_reduced_stiffness_is_positive_definite():
    solver = _single_quad_solver()
    solver.setup()

    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=0.0),
        BoundaryCondition(node_id=0, dof="uy", value=0.0),
        BoundaryCondition(node_id=1, dof="uy", value=0.0),
    ]

    solver.apply_boundary_conditions(bc_list=bc_list, nodal_forces=[])
    K_red = solver._K_reduced.toarray()

    eigvals = np.linalg.eigvalsh(K_red)
    assert np.all(eigvals > 0.0)
