import numpy as np

from app.engines.fea.assembly import BoundaryCondition, NodalForce
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _build_two_quad_solver(elements: list[list[int]]) -> FEASolver:
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
    return FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )


def _clamped_left_edge_bcs() -> list[BoundaryCondition]:
    return [
        BoundaryCondition(node_id=0, dof="ux", value=0.0),
        BoundaryCondition(node_id=0, dof="uy", value=0.0),
        BoundaryCondition(node_id=3, dof="ux", value=0.0),
        BoundaryCondition(node_id=3, dof="uy", value=0.0),
    ]


def _solve_with_forces(forces: list[NodalForce], elements: list[list[int]] | None = None) -> np.ndarray:
    elements = elements or [[1, 2, 5, 4], [2, 3, 6, 5]]
    solver = _build_two_quad_solver(elements)
    u_nodes, success, message = solver.run(_clamped_left_edge_bcs(), nodal_forces=forces)
    assert success, message
    return u_nodes.reshape(-1)


def test_solution_invariant_to_element_ordering():
    forces = [
        NodalForce(node_id=2, dof="fy", value=-100.0),
        NodalForce(node_id=5, dof="fy", value=-100.0),
    ]

    u_ref = _solve_with_forces(forces, elements=[[1, 2, 5, 4], [2, 3, 6, 5]])
    u_rev = _solve_with_forces(forces, elements=[[2, 3, 6, 5], [1, 2, 5, 4]])

    np.testing.assert_allclose(u_ref, u_rev, rtol=1e-12, atol=1e-12)


def test_linearity_under_load_scaling():
    base_forces = [
        NodalForce(node_id=2, dof="fy", value=-40.0),
        NodalForce(node_id=5, dof="fx", value=25.0),
    ]
    alpha = 3.75

    u_base = _solve_with_forces(base_forces)
    scaled_forces = [
        NodalForce(node_id=f.node_id, dof=f.dof, value=alpha * f.value)
        for f in base_forces
    ]
    u_scaled = _solve_with_forces(scaled_forces)

    np.testing.assert_allclose(u_scaled, alpha * u_base, rtol=5e-11, atol=1e-13)


def test_superposition_for_independent_load_cases():
    forces_a = [
        NodalForce(node_id=2, dof="fx", value=70.0),
        NodalForce(node_id=5, dof="fy", value=-50.0),
    ]
    forces_b = [
        NodalForce(node_id=2, dof="fy", value=-30.0),
        NodalForce(node_id=5, dof="fx", value=20.0),
    ]

    u_a = _solve_with_forces(forces_a)
    u_b = _solve_with_forces(forces_b)

    forces_sum = [
        NodalForce(node_id=2, dof="fx", value=70.0),
        NodalForce(node_id=2, dof="fy", value=-30.0),
        NodalForce(node_id=5, dof="fx", value=20.0),
        NodalForce(node_id=5, dof="fy", value=-50.0),
    ]
    u_sum = _solve_with_forces(forces_sum)

    np.testing.assert_allclose(u_sum, u_a + u_b, rtol=5e-11, atol=1e-13)
