import numpy as np
import scipy.sparse as sp

from app.engines.fea.assembly import BoundaryCondition, GlobalAssembler, LineLoad, NodalForce
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def test_global_sparse_assembly_matches_dense_assembly():
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
            [2.0, 1.0],
        ]
    )
    elements = [[1, 2, 5, 4], [2, 3, 6, 5]]
    assembler = GlobalAssembler(nodes, elements)

    def K_elem_fn(e_idx: int) -> np.ndarray:
        base = e_idx + 1.0
        K = np.full((8, 8), 0.1 * base)
        K += np.eye(8) * (5.0 + base)
        return (K + K.T) / 2.0

    K_sparse = assembler.build_global_K(K_elem_fn).toarray()
    K_dense = assembler.build_global_K_dense(K_elem_fn)

    np.testing.assert_allclose(K_sparse, K_dense, rtol=1e-12, atol=1e-12)


def test_force_vector_and_line_load_conservation():
    nodes = np.array([[0.0, 0.0], [2.0, 0.0]])
    assembler = GlobalAssembler(nodes, elements=[])

    F = assembler.build_force_vector(
        [
            NodalForce(node_id=0, dof="fx", value=12.0),
            NodalForce(node_id=1, dof="uy", value=-5.0),
        ]
    )
    assert np.isclose(F[0], 12.0)
    assert np.isclose(F[3], -5.0)

    F_line = np.zeros(4)
    F_line = assembler.add_line_load(
        F_line,
        [LineLoad(start_node=0, end_node=1, dof="ty", value=100.0)],
    )

    # Total distributed load = q * L = 100 * 2 = 200 N on y-direction.
    assert np.isclose(F_line[1] + F_line[3], 200.0, rtol=1e-12, atol=1e-12)
    assert np.isclose(F_line[0] + F_line[2], 0.0, rtol=1e-12, atol=1e-12)


def test_penalty_bc_modifies_diagonal_and_rhs():
    nodes = np.array([[0.0, 0.0]])
    assembler = GlobalAssembler(nodes, elements=[])

    K = sp.csr_matrix(np.array([[2.0, 0.0], [0.0, 3.0]]))
    F = np.array([0.0, 0.0])
    penalty = 1.0e6
    bc_list = [BoundaryCondition(node_id=0, dof="ux", value=0.1)]

    K_mod, F_mod = assembler.apply_dirichlet_bc(
        K,
        F,
        bc_list,
        method="penalty",
        penalty=penalty,
    )

    assert np.isclose(K_mod[0, 0], 2.0 + penalty)
    assert np.isclose(F_mod[0], penalty * 0.1)


def test_elimination_bc_with_duplicate_dof_uses_last_value():
    nodes = np.array([[0.0, 0.0], [1.0, 0.0]])
    assembler = GlobalAssembler(nodes, elements=[])

    K_dense = np.array(
        [
            [6.0, 1.0, 0.5, 0.0],
            [1.0, 7.0, 0.0, 0.2],
            [0.5, 0.0, 8.0, 1.5],
            [0.0, 0.2, 1.5, 9.0],
        ]
    )
    K = sp.csr_matrix(K_dense)
    F = np.array([1.0, 2.0, 3.0, 4.0])

    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=0.1),
        BoundaryCondition(node_id=0, dof="ux", value=0.3),  # duplicated DOF: keep last
        BoundaryCondition(node_id=1, dof="uy", value=-0.2),
    ]

    K_reduced, F_reduced, free_dofs, fixed_dofs = assembler.apply_dirichlet_bc(
        K,
        F,
        bc_list,
        method="elimination",
    )

    expected_fixed = [0, 3]
    expected_free = [1, 2]
    u_fixed = np.array([0.3, -0.2])

    expected_K = K_dense[np.ix_(expected_free, expected_free)]
    expected_F = (F - K_dense[:, expected_fixed] @ u_fixed)[expected_free]

    assert free_dofs == expected_free
    assert fixed_dofs == set(expected_fixed)
    np.testing.assert_allclose(K_reduced.toarray(), expected_K, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(F_reduced, expected_F, rtol=1e-12, atol=1e-12)


def test_recover_reactions_accepts_nodal_displacement_shape():
    nodes = np.array([[0.0, 0.0]])
    assembler = GlobalAssembler(nodes, elements=[])

    K = sp.csr_matrix(np.array([[10.0, 0.0], [0.0, 20.0]]))
    u = np.array([[0.1, -0.2]])
    bc_list = [
        BoundaryCondition(node_id=0, dof="ux", value=0.1),
        BoundaryCondition(node_id=0, dof="uy", value=-0.2),
    ]
    reactions = assembler.recover_reactions(K, u, bc_list, F_external=np.array([0.0, 0.0]))

    np.testing.assert_allclose(reactions, np.array([1.0, -4.0]), rtol=1e-12, atol=1e-12)


def _build_single_quad_solver(config: SolverConfig) -> FEASolver:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ]
    )
    elements = [[1, 2, 3, 4]]
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)

    return FEASolver(
        nodes=nodes,
        elements=elements,
        material=material,
        analysis_type=AnalysisType.PLANE_STRESS,
        config=config,
    )


def _stable_bc_with_nonzero_constraint() -> list[BoundaryCondition]:
    return [
        BoundaryCondition(node_id=0, dof="ux", value=0.0),
        BoundaryCondition(node_id=0, dof="uy", value=0.0),
        BoundaryCondition(node_id=1, dof="uy", value=0.0),
        BoundaryCondition(node_id=3, dof="ux", value=0.0),
        BoundaryCondition(node_id=1, dof="ux", value=1.0e-4),
    ]


def test_solver_requires_boundary_application_before_solve():
    solver = _build_single_quad_solver(SolverConfig(integration_order="2x2", bc_method="elimination"))
    solver.setup()
    u, success, message = solver.solve()

    assert not success
    assert "apply_boundary_conditions" in message
    assert u.shape == (4, 2)
    assert np.allclose(u, 0.0)


def test_solver_preserves_nonzero_dirichlet_values_in_output():
    solver = _build_single_quad_solver(SolverConfig(integration_order="2x2", bc_method="elimination"))
    bc_list = _stable_bc_with_nonzero_constraint()

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=[])
    assert success, message

    for bc in bc_list:
        dof_idx = solver.assembler._dof_index(bc.node_id, bc.dof)
        node = dof_idx // 2
        comp = dof_idx % 2
        assert np.isclose(u_nodes[node, comp], bc.value, atol=1e-12)


def test_solver_penalty_and_elimination_are_consistent():
    bc_list = _stable_bc_with_nonzero_constraint()

    nodal_forces = [NodalForce(node_id=2, dof="fy", value=-50.0)]

    solver_elim = _build_single_quad_solver(
        SolverConfig(integration_order="2x2", bc_method="elimination")
    )
    u_elim, ok_elim, msg_elim = solver_elim.run(bc_list=bc_list, nodal_forces=nodal_forces)
    assert ok_elim, msg_elim

    solver_penalty = _build_single_quad_solver(
        SolverConfig(integration_order="2x2", bc_method="penalty", penalty=1.0e18)
    )
    u_penalty, ok_penalty, msg_penalty = solver_penalty.run(
        bc_list=bc_list,
        nodal_forces=nodal_forces,
    )
    assert ok_penalty, msg_penalty

    np.testing.assert_allclose(u_penalty, u_elim, rtol=1e-6, atol=1e-10)
