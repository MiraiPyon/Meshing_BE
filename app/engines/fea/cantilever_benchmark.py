"""Cantilever benchmark used to validate the FEA pipeline against beam theory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import math
import time
from typing import Any, Iterable

import numpy as np

from app.engines.delaunay_engine import DelaunayMeshEngine
from app.engines.factory import MeshEngineFactory
from app.engines.fea.assembly import BoundaryCondition, NodalForce
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig
from app.engines.pslg import build_pslg
from app.services.fea_service import FEAService


@dataclass(frozen=True)
class CantileverBenchmarkConfig:
    load_y: float = -10_000.0
    length: float = 10.0
    height: float = 1.0
    young_modulus: float = 2.0e11
    poisson_ratio: float = 0.3
    thickness: float = 1.0

    @property
    def inertia(self) -> float:
        return self.thickness * self.height**3 / 12.0

    @property
    def exact_tip_deflection(self) -> float:
        return exact_neutral_axis_deflection(self.length, self)


@dataclass(frozen=True)
class CantileverBenchmarkCase:
    name: str
    element_type: str
    params: dict[str, Any]


DEFAULT_CASES = [
    CantileverBenchmarkCase("Q4-4x2", "Q4", {"nx": 4, "ny": 2}),
    CantileverBenchmarkCase("Q4-10x2", "Q4", {"nx": 10, "ny": 2}),
    CantileverBenchmarkCase("Q4-20x4", "Q4", {"nx": 20, "ny": 4}),
    CantileverBenchmarkCase(
        "T3-Delaunay-0.75",
        "T3",
        {
            "max_edge_length": 0.75,
            "min_angle": 20.7,
            "max_circumradius_ratio": math.sqrt(2.0),
            "max_refine_iterations": 1,
        },
    ),
]


def exact_neutral_axis_deflection(x: float, config: CantileverBenchmarkConfig) -> float:
    """Euler-Bernoulli cantilever deflection for a free-end point load."""
    return (
        config.load_y
        * x**2
        * (3.0 * config.length - x)
        / (6.0 * config.young_modulus * config.inertia)
    )


def run_cantilever_case(
    case: CantileverBenchmarkCase,
    config: CantileverBenchmarkConfig | None = None,
) -> dict[str, Any]:
    cfg = config or CantileverBenchmarkConfig()
    started = time.perf_counter()
    nodes_raw, elements_raw = _generate_case_mesh(case, cfg)
    mesh_s = time.perf_counter() - started

    nodes = np.asarray(nodes_raw, dtype=float)
    elements = FEAService._prepare_elements_for_solver(elements_raw, nodes_raw)
    _assert_positive_area_triangles(nodes, elements)

    material = MaterialModel(E=cfg.young_modulus, nu=cfg.poisson_ratio, thickness=cfg.thickness)
    analysis_type = AnalysisType.PLANE_STRESS
    integration_order = "2x2" if case.element_type == "Q4" else "3pt"
    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=material,
        analysis_type=analysis_type,
        config=SolverConfig(integration_order=integration_order),
    )

    x_min = float(nodes[:, 0].min())
    x_max = float(nodes[:, 0].max())
    tol = max(1e-9, cfg.length * 1e-9)
    left_nodes = [idx for idx, (x, _y) in enumerate(nodes) if abs(float(x) - x_min) <= tol]
    right_nodes = [idx for idx, (x, _y) in enumerate(nodes) if abs(float(x) - x_max) <= tol]
    if not left_nodes or not right_nodes:
        raise ValueError(f"{case.name}: cannot detect cantilever support/load edges")

    target = min(right_nodes, key=lambda idx: abs(float(nodes[idx, 1]) - cfg.height / 2.0))
    bc_list = [
        bc
        for node_id in left_nodes
        for bc in (
            BoundaryCondition(node_id=node_id, dof="ux", value=0.0),
            BoundaryCondition(node_id=node_id, dof="uy", value=0.0),
        )
    ]
    nodal_forces = [NodalForce(node_id=target, dof="fy", value=cfg.load_y)]

    solve_started = time.perf_counter()
    displacements, success, message = solver.run(bc_list=bc_list, nodal_forces=nodal_forces)
    solve_s = time.perf_counter() - solve_started
    if not success:
        raise ValueError(f"{case.name}: FEA solve failed: {message}")

    reactions = solver.assembler.recover_reactions(
        solver._K_full,
        displacements,
        bc_list,
        F_external=solver._F,
    ).reshape(-1, 2)
    support_reaction_y = float(np.sum([reactions[node_id, 1] for node_id in left_nodes]))
    force_balance_error = abs(support_reaction_y + cfg.load_y) / max(abs(cfg.load_y), 1e-12)

    tip_uy = float(displacements[target, 1])
    exact_tip = cfg.exact_tip_deflection
    tip_abs_error = tip_uy - exact_tip
    tip_rel_error = abs(tip_abs_error) / max(abs(exact_tip), 1e-18)

    samples = _neutral_axis_samples(nodes, displacements, cfg)

    return {
        "case": case.name,
        "element_type": case.element_type,
        "mesh_params": case.params,
        "node_count": len(nodes),
        "element_count": len(elements),
        "dof": 2 * len(nodes),
        "target_node": target,
        "target_xy": [float(nodes[target, 0]), float(nodes[target, 1])],
        "tip_uy": tip_uy,
        "exact_tip_uy": exact_tip,
        "tip_abs_error": tip_abs_error,
        "tip_rel_error": tip_rel_error,
        "support_reaction_y": support_reaction_y,
        "force_balance_error": force_balance_error,
        "mesh_s": mesh_s,
        "solve_s": solve_s,
        "status": "PASS" if force_balance_error <= 1e-6 and np.isfinite(tip_uy) else "FAIL",
        "samples": samples,
    }


def run_cantilever_benchmark(
    cases: Iterable[CantileverBenchmarkCase] | None = None,
    config: CantileverBenchmarkConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or CantileverBenchmarkConfig()
    return [run_cantilever_case(case, cfg) for case in (cases or DEFAULT_CASES)]


def write_cantilever_benchmark_artifacts(
    report_path: Path,
    csv_path: Path,
    results: list[dict[str, Any]] | None = None,
    config: CantileverBenchmarkConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or CantileverBenchmarkConfig()
    benchmark_results = results or run_cantilever_benchmark(config=cfg)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    csv_rows = []
    for result in benchmark_results:
        for sample in result["samples"]:
            csv_rows.append(
                {
                    "case": result["case"],
                    "x": sample["x"],
                    "fea_uy": sample["fea_uy"],
                    "exact_uy": sample["exact_uy"],
                    "error": sample["error"],
                    "relative_error": sample["relative_error"],
                }
            )

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["case", "x", "fea_uy", "exact_uy", "error", "relative_error"],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    report_path.write_text(_build_markdown_report(benchmark_results, cfg, csv_path.name), encoding="utf-8")
    return benchmark_results


def _generate_case_mesh(
    case: CantileverBenchmarkCase,
    config: CantileverBenchmarkConfig,
) -> tuple[list[list[float]], list[list[int]]]:
    outer = [
        (0.0, 0.0),
        (config.length, 0.0),
        (config.length, config.height),
        (0.0, config.height),
    ]
    if case.element_type == "Q4":
        return MeshEngineFactory.create("quad").generate(points=outer, **case.params)
    if case.element_type == "T3":
        pslg = build_pslg(outer_boundary=outer, holes=[])
        return DelaunayMeshEngine().generate_from_pslg(pslg=pslg, **case.params)
    raise ValueError(f"Unsupported benchmark element type: {case.element_type}")


def _assert_positive_area_triangles(nodes: np.ndarray, elements: list[list[int]]) -> None:
    for elem in elements:
        if len(elem) != 3:
            continue
        p0, p1, p2 = nodes[[idx - 1 for idx in elem]]
        signed_area2 = float(
            (p1[0] - p0[0]) * (p2[1] - p0[1])
            - (p2[0] - p0[0]) * (p1[1] - p0[1])
        )
        if signed_area2 <= 1e-14:
            raise ValueError(f"Triangle element is not valid CCW: {elem}")


def _neutral_axis_samples(
    nodes: np.ndarray,
    displacements: np.ndarray,
    config: CantileverBenchmarkConfig,
) -> list[dict[str, float]]:
    by_x: dict[float, list[int]] = {}
    for idx, (x, _y) in enumerate(nodes):
        rounded_x = round(float(x), 10)
        by_x.setdefault(rounded_x, []).append(idx)

    samples = []
    for x in sorted(by_x):
        node_id = min(by_x[x], key=lambda idx: abs(float(nodes[idx, 1]) - config.height / 2.0))
        fea_uy = float(displacements[node_id, 1])
        exact_uy = exact_neutral_axis_deflection(float(nodes[node_id, 0]), config)
        error = fea_uy - exact_uy
        relative_error = abs(error) / max(abs(exact_uy), 1e-18)
        samples.append(
            {
                "x": float(nodes[node_id, 0]),
                "fea_uy": fea_uy,
                "exact_uy": exact_uy,
                "error": error,
                "relative_error": relative_error,
            }
        )
    return samples


def _build_markdown_report(results: list[dict[str, Any]], config: CantileverBenchmarkConfig, csv_name: str) -> str:
    q4_results = [result for result in results if result["element_type"] == "Q4"]
    q4_converges = all(
        q4_results[idx]["tip_rel_error"] > q4_results[idx + 1]["tip_rel_error"]
        for idx in range(len(q4_results) - 1)
    )
    refined_q4 = q4_results[-1] if q4_results else None
    refined_q4_pass = bool(refined_q4 and refined_q4["tip_rel_error"] <= 0.12)
    overall = "PASS" if all(result["status"] == "PASS" for result in results) and q4_converges and refined_q4_pass else "FAIL"

    lines = [
        "# Cantilever Benchmark Report - 2026-04-28",
        "",
        f"Overall status: **{overall}**",
        "",
        "This benchmark reproduces the cantilever problem from Section IV of the reference paper using the project's supported T3/Q4 elements. The paper uses LST/T6 elements, so this report compares the same geometry, material, load, and analytical Euler-Bernoulli solution, not the same element family.",
        "",
        "## Input",
        "",
        f"- Load: `{abs(config.load_y):.0f} N` downward at the free-edge node closest to the neutral axis",
        f"- Length: `{config.length} m`",
        f"- Height: `{config.height} m`",
        f"- Thickness: `{config.thickness} m`",
        f"- Young modulus: `{config.young_modulus:.3e} Pa`",
        f"- Poisson ratio: `{config.poisson_ratio}`",
        "- Exact neutral-axis deflection: `v(x)=P*x^2*(3L-x)/(6EI)`, `I=t*h^3/12`",
        f"- Exact tip deflection: `{config.exact_tip_deflection:.6e} m`",
        "- Coordinate convention: paper load/support orientation is mirrored to clamp at `x=0` and apply the end load at `x=L`; the beam problem and analytical deflection are equivalent.",
        "",
        "## Reference Mapping",
        "",
        "- Section IV uses LST/T6 triangular elements with 4-element and 10-element meshes.",
        "- This project requirement supports T3 and Q4 only, so the benchmark keeps the same Section IV geometry, material, load, and analytical curve while validating supported T3/Q4 elements.",
        "- `Q4-4x2` and `Q4-10x2` mirror the paper's coarse/fine division controls; `Q4-20x4` is the refined accuracy gate; `T3-Delaunay-0.75` verifies the Delaunay/FEA path on the same beam.",
        "",
        f"CSV point-by-point evidence: `{csv_name}`",
        "",
        "## Summary",
        "",
        "| Case | Element | Nodes | Elements | DOF | Tip uy (m) | Exact tip (m) | Rel. error | Force balance | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for result in results:
        lines.append(
            "| {case} | {element_type} | {node_count} | {element_count} | {dof} | "
            "{tip_uy:.6e} | {exact_tip_uy:.6e} | {tip_rel_error:.2%} | "
            "{force_balance_error:.3e} | {status} |".format(**result)
        )

    lines.extend(
        [
            "",
            "## Accuracy Notes",
            "",
            f"- Q4 convergence gate: `{'PASS' if q4_converges else 'FAIL'}`. Tip relative error decreases as the mesh is refined.",
            f"- Refined Q4 gate (`<= 12%` tip relative error): `{'PASS' if refined_q4_pass else 'FAIL'}`.",
            "- T3 Delaunay gate checks solver validity, CCW triangle orientation, and force equilibrium. Its accuracy is reported as evidence but not forced to match the paper's LST/T6 curve.",
            "- A lower error is expected with denser meshes or a higher-order LST/T6 implementation, which is outside the current T3/Q4 project scope.",
            "",
        ]
    )
    return "\n".join(lines)
