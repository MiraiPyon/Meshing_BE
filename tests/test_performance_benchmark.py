import os
import time

import numpy as np
import pytest

from app.engines.factory import MeshEngineFactory
from app.engines.fea.assembly import BoundaryCondition, NodalForce
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@pytest.mark.performance
def test_q4_10k_elements_benchmark():
    if not _env_flag("RUN_PERFORMANCE_BENCHMARK"):
        pytest.skip("Set RUN_PERFORMANCE_BENCHMARK=1 to run 10k-element benchmark.")

    nx = int(os.getenv("PERF_NX", "100"))
    ny = int(os.getenv("PERF_NY", "100"))
    outer = [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)]

    max_mesh_s = _env_float("PERF_MAX_MESH_S", 2.0)
    max_assemble_s = _env_float("PERF_MAX_ASSEMBLE_S", 10.0)
    max_solve_s = _env_float("PERF_MAX_SOLVE_S", 5.0)
    max_total_s = _env_float("PERF_MAX_TOTAL_S", 20.0)

    t0 = time.perf_counter()
    mesh_engine = MeshEngineFactory.create("quad")
    nodes_raw, elements = mesh_engine.generate(points=outer, nx=nx, ny=ny)
    t1 = time.perf_counter()

    nodes = np.asarray(nodes_raw, dtype=float)
    material = MaterialModel(E=2e11, nu=0.3, thickness=0.01)
    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=material,
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2"),
    )

    left_nodes = [idx for idx, (x, _y) in enumerate(nodes) if abs(x) <= 1e-12]
    bc_list = []
    for idx in left_nodes:
        bc_list.append(BoundaryCondition(node_id=idx, dof="ux", value=0.0))
        bc_list.append(BoundaryCondition(node_id=idx, dof="uy", value=0.0))

    right_top_node = int(np.argmax(nodes[:, 0] * 1000.0 + nodes[:, 1]))
    forces = [NodalForce(node_id=right_top_node, dof="fy", value=-1000.0)]

    solver.setup()
    t2 = time.perf_counter()
    solver.apply_boundary_conditions(bc_list=bc_list, nodal_forces=forces)
    t3 = time.perf_counter()
    u, success, message = solver.solve()
    t4 = time.perf_counter()

    mesh_s = t1 - t0
    assemble_s = t2 - t1
    solve_s = t4 - t3
    total_s = t4 - t0

    print(
        (
            f"[PERF] nodes={len(nodes)} elements={len(elements)} dof={2 * len(nodes)} "
            f"mesh_s={mesh_s:.4f} assemble_s={assemble_s:.4f} "
            f"solve_s={solve_s:.4f} total_s={total_s:.4f}"
        )
    )

    assert len(elements) == nx * ny
    assert success, message
    assert np.max(np.abs(u)) > 0.0
    assert mesh_s <= max_mesh_s, f"mesh_s={mesh_s:.4f} > {max_mesh_s:.4f}"
    assert assemble_s <= max_assemble_s, f"assemble_s={assemble_s:.4f} > {max_assemble_s:.4f}"
    assert solve_s <= max_solve_s, f"solve_s={solve_s:.4f} > {max_solve_s:.4f}"
    assert total_s <= max_total_s, f"total_s={total_s:.4f} > {max_total_s:.4f}"
