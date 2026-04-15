import numpy as np

from app.engines.fea.assembly import BoundaryCondition, NodalForce
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _build_cantilever_mesh(nx: int, ny: int, length: float = 1.0, height: float = 0.2):
    x_nodes = np.linspace(0.0, length, nx + 1)
    y_nodes = np.linspace(0.0, height, ny + 1)

    nodes = np.array(
        [[x_nodes[i], y_nodes[j]] for i in range(nx + 1) for j in range(ny + 1)],
        dtype=float,
    )

    elements = []
    for i in range(nx):
        for j in range(ny):
            n1 = i * (ny + 1) + j + 1
            n2 = (i + 1) * (ny + 1) + j + 1
            n3 = (i + 1) * (ny + 1) + j + 2
            n4 = i * (ny + 1) + j + 2
            elements.append([n1, n2, n3, n4])

    return nodes, elements


def _solve_right_edge_avg_uy(nx: int, ny: int = 2, total_load: float = 1000.0) -> float:
    nodes, elements = _build_cantilever_mesh(nx=nx, ny=ny)

    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=210e9, nu=0.3, thickness=0.01),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )

    # Clamp left edge (x=0)
    bc_list = []
    for j in range(ny + 1):
        bc_list.append(BoundaryCondition(node_id=j, dof="ux", value=0.0))
        bc_list.append(BoundaryCondition(node_id=j, dof="uy", value=0.0))

    right_edge_nodes = [nx * (ny + 1) + j for j in range(ny + 1)]
    nodal_forces = [
        NodalForce(node_id=n, dof="fy", value=-total_load / len(right_edge_nodes))
        for n in right_edge_nodes
    ]

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=nodal_forces)
    assert success, message

    return float(np.mean(u_nodes[right_edge_nodes, 1]))


def test_cantilever_q4_displacement_sequence_shows_mesh_convergence_trend():
    # Refinement levels (coarse -> fine)
    nx_levels = [4, 8, 12, 16]
    u_vals = np.array([_solve_right_edge_avg_uy(nx) for nx in nx_levels])

    # Downward load should yield negative average vertical displacement.
    assert np.all(u_vals < 0.0)

    # For this setup, refinement should reduce locking and increase displacement magnitude.
    mags = np.abs(u_vals)
    assert np.all(np.diff(mags) > 0.0)

    # Differences between successive refinements should shrink (convergence trend).
    deltas = np.abs(np.diff(u_vals))
    assert deltas[1] < deltas[0]
    assert deltas[2] < deltas[1] * 1.05
