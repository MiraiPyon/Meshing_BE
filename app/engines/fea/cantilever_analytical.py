"""
Analytical helpers for rectangular cantilever beams.

The formulas in this module are used as a verification benchmark for the FEA
pipeline (stiffness, load vector, BC reduction, and reaction recovery).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.engines.fea.assembly import BoundaryCondition, LineLoad, NodalForce
from app.engines.fea.material import MaterialModel


@dataclass(frozen=True)
class CantileverSection:
    """Rectangular cantilever section data for beam-theory checks."""

    length: float
    height: float
    thickness: float

    @property
    def area(self) -> float:
        return self.thickness * self.height

    @property
    def inertia(self) -> float:
        # I = t * h^3 / 12 for out-of-plane bending of a 2D strip.
        return self.thickness * self.height**3 / 12.0


def euler_bernoulli_tip_deflection_point_load(
    force_y: float,
    length: float,
    young_modulus: float,
    inertia: float,
) -> float:
    """Tip deflection for a cantilever under end point load P (vertical)."""
    denom = 3.0 * young_modulus * inertia
    if abs(denom) < 1e-30:
        raise ValueError("Invalid beam stiffness: E*I is zero")
    return force_y * length**3 / denom


def timoshenko_tip_deflection_point_load(
    force_y: float,
    length: float,
    young_modulus: float,
    inertia: float,
    shear_modulus: float,
    area: float,
    kappa: float = 5.0 / 6.0,
) -> float:
    """Tip deflection for Timoshenko cantilever under end point load P."""
    delta_bending = euler_bernoulli_tip_deflection_point_load(
        force_y,
        length,
        young_modulus,
        inertia,
    )
    shear_denom = kappa * shear_modulus * area
    if abs(shear_denom) < 1e-30:
        raise ValueError("Invalid shear stiffness: kappa*G*A is zero")
    delta_shear = force_y * length / shear_denom
    return delta_bending + delta_shear


def resultant_vertical_load(
    nodes: np.ndarray,
    nodal_forces: Optional[list[NodalForce]] = None,
    line_loads: Optional[list[LineLoad]] = None,
) -> float:
    """Compute total external vertical load from nodal + edge loads."""
    total = 0.0

    for force in nodal_forces or []:
        if force.dof in ("fy", "uy", "ty"):
            total += force.value

    for load in line_loads or []:
        if load.dof not in ("fy", "uy", "ty"):
            continue
        p1 = np.asarray(nodes[load.start_node], dtype=float)
        p2 = np.asarray(nodes[load.end_node], dtype=float)
        edge_length = float(np.linalg.norm(p2 - p1))
        total += load.value * edge_length

    return float(total)


def detect_rectangular_cantilever(
    nodes: np.ndarray,
    thickness: float,
) -> Optional[tuple[CantileverSection, list[int], list[int]]]:
    """Detect left/right boundaries and dimensions for a rectangular beam mesh."""
    if len(nodes) < 4:
        return None

    x = nodes[:, 0]
    y = nodes[:, 1]
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    y_min = float(np.min(y))
    y_max = float(np.max(y))

    length = x_max - x_min
    height = y_max - y_min
    if length <= 0.0 or height <= 0.0 or thickness <= 0.0:
        return None

    tol = max(1e-12, 1e-9 * max(length, height))
    left_nodes = np.where(np.abs(x - x_min) <= tol)[0].tolist()
    right_nodes = np.where(np.abs(x - x_max) <= tol)[0].tolist()

    if len(left_nodes) < 2 or len(right_nodes) < 2:
        return None

    left_nodes.sort(key=lambda n: float(nodes[n, 1]))
    right_nodes.sort(key=lambda n: float(nodes[n, 1]))

    section = CantileverSection(length=length, height=height, thickness=thickness)
    return section, left_nodes, right_nodes


def evaluate_cantilever_benchmark(
    nodes: np.ndarray,
    displacements: np.ndarray,
    material: MaterialModel,
    bc_list: list[BoundaryCondition],
    nodal_forces: Optional[list[NodalForce]] = None,
    line_loads: Optional[list[LineLoad]] = None,
    reactions: Optional[np.ndarray] = None,
) -> Optional[dict]:
    """Build a benchmark payload for cantilever checks.

    Returns None if the current setup does not look like a clamped-left
    rectangular cantilever with non-zero vertical loading.
    """
    detected = detect_rectangular_cantilever(nodes, material.thickness)
    if detected is None:
        return None

    section, left_nodes, right_nodes = detected

    constrained = {(bc.node_id, bc.dof): bc.value for bc in bc_list}
    if not all((n, "ux") in constrained and (n, "uy") in constrained for n in left_nodes):
        return None

    total_force_y = resultant_vertical_load(nodes, nodal_forces, line_loads)
    if abs(total_force_y) < 1e-12:
        return None

    tip_uy_avg = float(np.mean(displacements[right_nodes, 1]))
    tip_uy_min = float(np.min(displacements[right_nodes, 1]))
    tip_uy_max = float(np.max(displacements[right_nodes, 1]))

    G = material.E / (2.0 * (1.0 + material.nu))
    delta_euler = euler_bernoulli_tip_deflection_point_load(
        total_force_y,
        section.length,
        material.E,
        section.inertia,
    )
    delta_timoshenko = timoshenko_tip_deflection_point_load(
        total_force_y,
        section.length,
        material.E,
        section.inertia,
        G,
        section.area,
    )

    ratio_to_euler = None
    if abs(delta_euler) > 1e-18:
        ratio_to_euler = tip_uy_avg / delta_euler

    ratio_to_timoshenko = None
    if abs(delta_timoshenko) > 1e-18:
        ratio_to_timoshenko = tip_uy_avg / delta_timoshenko

    sum_reaction_y = None
    force_balance_error = None
    if reactions is not None:
        r = np.asarray(reactions).reshape(-1)
        sum_reaction_y = float(np.sum([r[2 * n + 1] for n in left_nodes]))
        force_balance_error = abs(sum_reaction_y + total_force_y) / max(abs(total_force_y), 1e-12)

    return {
        "length": float(section.length),
        "height": float(section.height),
        "thickness": float(section.thickness),
        "left_edge_nodes": left_nodes,
        "right_edge_nodes": right_nodes,
        "total_vertical_load": float(total_force_y),
        "tip_uy_avg": tip_uy_avg,
        "tip_uy_min": tip_uy_min,
        "tip_uy_max": tip_uy_max,
        "euler_tip_deflection": float(delta_euler),
        "timoshenko_tip_deflection": float(delta_timoshenko),
        "ratio_to_euler": None if ratio_to_euler is None else float(ratio_to_euler),
        "ratio_to_timoshenko": None if ratio_to_timoshenko is None else float(ratio_to_timoshenko),
        "sum_reaction_y": sum_reaction_y,
        "force_balance_error": force_balance_error,
    }
