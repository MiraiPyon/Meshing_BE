import numpy as np
import scipy.sparse as sp

from app.engines.fea.assembly import BoundaryCondition, GlobalAssembler
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _reference_solution_with_prescribed_bc(
    K_full: np.ndarray,
    F_full: np.ndarray,
    prescribed: dict[int, float],
) -> np.ndarray:
    """Solve constrained linear system using matrix partitioning."""
    n_dof = K_full.shape[0]
    fixed = np.array(sorted(prescribed.keys()), dtype=int)
    free = np.array([d for d in range(n_dof) if d not in prescribed], dtype=int)

    u_full = np.zeros(n_dof, dtype=float)
    if fixed.size > 0:
        u_full[fixed] = np.array([prescribed[d] for d in fixed], dtype=float)

    if free.size > 0:
        K_ff = K_full[np.ix_(free, free)]
        rhs = F_full[free].copy()
        if fixed.size > 0:
            K_fc = K_full[np.ix_(free, fixed)]
            rhs -= K_fc @ u_full[fixed]
        u_full[free] = np.linalg.solve(K_ff, rhs)

    return u_full


def test_apply_elimination_uses_column_coupling_for_rhs():
    """F_reduced must use F - K[:, fixed] * u_fixed, not a row-based subtraction."""
    nodes = np.array([[0.0, 0.0], [1.0, 0.0]])
    elements = [[1, 2, 2, 1]]
    assembler = GlobalAssembler(nodes, elements)

    K_dense = np.array(
        [
            [20.0, 2.0, -5.0, 1.0],
            [2.0, 18.0, 3.0, -4.0],
            [-5.0, 3.0, 22.0, 2.0],
            [1.0, -4.0, 2.0, 16.0],
        ]
    )
    K = sp.csr_matrix(K_dense)
    F = np.array([10.0, 7.0, 5.0, -2.0])

    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=0.2),
        BoundaryCondition(node_id=1, dof="uy", value=-0.1),
    ]

    K_reduced, F_reduced, free_dofs, _ = assembler.apply_dirichlet_bc(
        K, F, bc_list, method="elimination"
    )

    fixed = np.array([0, 3], dtype=int)
    u_fixed = np.array([0.2, -0.1])
    expected_free = [1, 2]

    expected_K = K_dense[np.ix_(expected_free, expected_free)]
    expected_F = (F - K_dense[:, fixed] @ u_fixed)[expected_free]

    np.testing.assert_allclose(K_reduced.toarray(), expected_K, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(F_reduced, expected_F, rtol=1e-12, atol=1e-12)
    assert free_dofs == expected_free


def test_solver_u_matches_partition_reference_with_nonzero_dirichlet_bc():
    """End-to-end check: computed nodal U must match constrained system reference solution."""
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ]
    )
    elements = [[1, 2, 3, 4]]

    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )

    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=0.0),
        BoundaryCondition(node_id=0, dof="uy", value=0.0),
        BoundaryCondition(node_id=1, dof="uy", value=0.0),
        BoundaryCondition(node_id=3, dof="ux", value=0.0),
        BoundaryCondition(node_id=1, dof="ux", value=1.0e-4),
    ]

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=[])

    assert success, message
    assert u_nodes.shape == (4, 2)

    prescribed = {
        solver.assembler._dof_index(bc.node_id, bc.dof): bc.value
        for bc in bc_list
    }
    K_full = solver._K_full.toarray()
    F_full = solver._F.copy()

    u_ref = _reference_solution_with_prescribed_bc(K_full, F_full, prescribed)

    np.testing.assert_allclose(
        u_nodes.reshape(-1),
        u_ref,
        rtol=1e-9,
        atol=1e-12,
    )

    # Non-trivial propagation: interior response should not be exactly zero.
    assert abs(u_nodes[2, 0]) > 1e-12
