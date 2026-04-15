import numpy as np
import scipy.sparse as sp

from app.engines.fea.assembly import BoundaryCondition, GlobalAssembler
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _single_quad_solver(method: str = "elimination") -> FEASolver:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ]
    )
    elements = [[1, 2, 3, 4]]
    return FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method=method),
    )


def test_solver_all_dofs_prescribed_returns_prescribed_field_for_elimination_and_penalty():
    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=1.0e-6),
        BoundaryCondition(node_id=0, dof="uy", value=-2.0e-6),
        BoundaryCondition(node_id=1, dof="ux", value=3.0e-6),
        BoundaryCondition(node_id=1, dof="uy", value=4.0e-6),
        BoundaryCondition(node_id=2, dof="ux", value=-5.0e-6),
        BoundaryCondition(node_id=2, dof="uy", value=6.0e-6),
        BoundaryCondition(node_id=3, dof="ux", value=7.0e-6),
        BoundaryCondition(node_id=3, dof="uy", value=-8.0e-6),
    ]

    for method in ["elimination", "penalty"]:
        solver = _single_quad_solver(method=method)
        u, success, message = solver.run(bc_list=bc_list, nodal_forces=[])
        assert success, message
        assert u.shape == (4, 2)

        for bc in bc_list:
            dof_idx = solver.assembler._dof_index(bc.node_id, bc.dof)
            assert np.isclose(u.reshape(-1)[dof_idx], bc.value, atol=1e-12)


def test_apply_elimination_without_bc_returns_original_system():
    nodes = np.array([[0.0, 0.0], [1.0, 0.0]])
    assembler = GlobalAssembler(nodes, elements=[])

    K = np.array(
        [
            [4.0, 1.0, 0.0, 0.0],
            [1.0, 5.0, 1.0, 0.0],
            [0.0, 1.0, 6.0, 1.0],
            [0.0, 0.0, 1.0, 7.0],
        ]
    )
    F = np.array([1.0, 2.0, 3.0, 4.0])

    K_red, F_red, free_dofs, fixed_dofs = assembler.apply_dirichlet_bc(
        sp.csr_matrix(K),
        F,
        [],
        method="elimination",
    )

    np.testing.assert_allclose(K_red.toarray(), K, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(F_red, F, rtol=1e-12, atol=1e-12)
    assert free_dofs == [0, 1, 2, 3]
    assert fixed_dofs == set()


def test_dof_index_mapping_and_invalid_dof():
    assert GlobalAssembler._dof_index(2, "ux") == 4
    assert GlobalAssembler._dof_index(2, "uy") == 5

    try:
        GlobalAssembler._dof_index(0, "uz")
    except ValueError as exc:
        assert "Unknown DOF" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid DOF")
