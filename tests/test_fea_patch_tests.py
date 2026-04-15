import numpy as np

from app.engines.fea.assembly import BoundaryCondition
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _u_linear(x: float, y: float) -> tuple[float, float]:
    ux = 1.2e-4 * x - 4.0e-5 * y + 2.0e-6
    uy = 3.5e-5 * x + 8.0e-5 * y - 1.0e-6
    return ux, uy


def _make_boundary_bcs(nodes: np.ndarray, boundary_node_ids: list[int]) -> list[BoundaryCondition]:
    bcs: list[BoundaryCondition] = []
    for nid in boundary_node_ids:
        ux, uy = _u_linear(float(nodes[nid, 0]), float(nodes[nid, 1]))
        bcs.append(BoundaryCondition(node_id=nid, dof="ux", value=ux))
        bcs.append(BoundaryCondition(node_id=nid, dof="uy", value=uy))
    return bcs


def test_patch_t3_linear_displacement_reproduced_at_interior_node():
    # Square patch with one interior node; 4 linear triangles around center.
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [0.5, 0.5],
        ]
    )
    elements = [
        [1, 2, 5],
        [2, 3, 5],
        [3, 4, 5],
        [4, 1, 5],
    ]

    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="3pt", bc_method="elimination"),
    )

    bc_list = _make_boundary_bcs(nodes, boundary_node_ids=[0, 1, 2, 3])
    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=[])

    assert success, message
    ux_expected, uy_expected = _u_linear(0.5, 0.5)
    np.testing.assert_allclose(u_nodes[4, 0], ux_expected, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(u_nodes[4, 1], uy_expected, rtol=1e-10, atol=1e-12)


def test_patch_q4_linear_displacement_reproduced_at_center_node_plane_strain():
    # 2x2 Q4 patch with center node free.
    nodes = np.array(
        [
            [0.0, 0.0],
            [0.5, 0.0],
            [1.0, 0.0],
            [0.0, 0.5],
            [0.5, 0.5],
            [1.0, 0.5],
            [0.0, 1.0],
            [0.5, 1.0],
            [1.0, 1.0],
        ]
    )
    elements = [
        [1, 2, 5, 4],
        [2, 3, 6, 5],
        [4, 5, 8, 7],
        [5, 6, 9, 8],
    ]

    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=70e9, nu=0.28, thickness=0.02),
        analysis_type=AnalysisType.PLANE_STRAIN,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )

    boundary_ids = [0, 1, 2, 3, 5, 6, 7, 8]
    bc_list = _make_boundary_bcs(nodes, boundary_node_ids=boundary_ids)

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=[])

    assert success, message
    ux_expected, uy_expected = _u_linear(0.5, 0.5)
    np.testing.assert_allclose(u_nodes[4, 0], ux_expected, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(u_nodes[4, 1], uy_expected, rtol=1e-9, atol=1e-12)
