"""
FEAService – Business logic cho FEA analysis.
"""

import json
import uuid
from typing import List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
import numpy as np

from app.schemas.fea_request import FEASolveRequest
from app.schemas.fea_response import FEAResultResponse
from app.database.models import Mesh as MeshModel, Geometry as GeometryModel
from app.engines.fea.material import MaterialModel, AnalysisType
from app.engines.fea.assembly import (
    BoundaryCondition,
    NodalForce,
    LineLoad,
)
from app.engines.fea.solver import FEASolver, SolverConfig
from app.engines.fea.stress_recovery import StressRecovery
from app.engines.fea.cantilever_analytical import evaluate_cantilever_benchmark


class FEAService:
    """Service xử lý FEA analysis."""

    def solve(self, db: Session, req: FEASolveRequest, user_id: UUID) -> Tuple[FEAResultResponse, bool, str]:
        """
        Run full FEA analysis.

        Args:
            db:  SQLAlchemy session
            req: FEASolveRequest
            user_id: UUID of current user (for ownership check)

        Returns:
            (result, success, message)
        """
        # 1. Load mesh (chỉ mesh thuộc về user)
        mesh = db.query(MeshModel).join(GeometryModel).filter(
            MeshModel.id == req.mesh_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not mesh:
            raise ValueError(f"Mesh {req.mesh_id} not found")

        nodes_raw = json.loads(mesh.nodes)
        elements_raw = json.loads(mesh.elements)
        nodes = np.array(nodes_raw)
        # Normalize mesh connectivity to 1-based CCW indexing expected by FEA core.
        elements = self._prepare_elements_for_solver(elements_raw, nodes_raw)

        # 2. Material
        if req.material.preset:
            preset_map = {
                "steel": MaterialModel.steel,
                "aluminum": MaterialModel.aluminum,
                "titanium": MaterialModel.titanium,
                "concrete": MaterialModel.concrete,
            }
            mat_fn = preset_map.get(req.material.preset)
            if not mat_fn:
                raise ValueError(f"Unknown preset: {req.material.preset}")
            material = mat_fn(thickness=req.material.thickness)
        else:
            material = MaterialModel(
                E=req.material.E,
                nu=req.material.nu,
                thickness=req.material.thickness,
            )

        # Override thickness if explicitly provided
        material.thickness = req.material.thickness

        # 3. Analysis type
        if req.analysis_type == "plane_strain":
            analysis_type = AnalysisType.PLANE_STRAIN
        else:
            analysis_type = AnalysisType.PLANE_STRESS

        # 4. Config
        config = SolverConfig()
        if req.integration_order:
            config.integration_order = req.integration_order

        # 5. Solver
        solver = FEASolver(
            nodes=nodes,
            elements=elements,
            material=material,
            analysis_type=analysis_type,
            config=config,
        )

        # 6. Boundary conditions
        bc_list = [
            BoundaryCondition(node_id=bc.node_id, dof=bc.dof, value=bc.value)
            for bc in req.boundary_conditions
        ]

        nodal_forces = [
            NodalForce(node_id=f.node_id, dof=f.dof, value=f.value)
            for f in req.nodal_forces
        ]

        line_loads = None
        if req.line_loads:
            line_loads = [
                LineLoad(
                    start_node=ll.start_node,
                    end_node=ll.end_node,
                    dof=ll.dof,
                    value=ll.value,
                )
                for ll in req.line_loads
            ]

        # 7. Solve
        u_full, success, message = solver.run(
            bc_list=bc_list,
            nodal_forces=nodal_forces,
            line_loads=line_loads,
        )

        if not success:
            return None, False, message

        reactions_matrix = None
        sum_reaction_x = None
        sum_reaction_y = None
        if solver._K_full is not None and solver._F is not None and bc_list:
            reactions_full = solver.assembler.recover_reactions(
                solver._K_full,
                u_full,
                bc_list,
                F_external=solver._F,
            )
            reactions_matrix = reactions_full.reshape(-1, 2)
            sum_reaction_x = float(np.sum(reactions_matrix[:, 0]))
            sum_reaction_y = float(np.sum(reactions_matrix[:, 1]))

        cantilever_benchmark = evaluate_cantilever_benchmark(
            nodes=nodes,
            displacements=u_full,
            material=material,
            bc_list=bc_list,
            nodal_forces=nodal_forces,
            line_loads=line_loads,
            reactions=None if reactions_matrix is None else reactions_matrix.reshape(-1),
        )

        # 8. Stress recovery
        stress_rec = StressRecovery(material, analysis_type)

        all_stresses = []
        all_strains = []
        gp_stresses_list = []
        gp_coords_list = []

        for e_idx in range(len(elements)):
            coords = solver.assembler.get_element_coords(e_idx)
            elem = elements[e_idx]
            u_elem = np.zeros(2 * len(elem))
            for i, n in enumerate(elem):
                u_elem[2 * i]     = u_full[n - 1, 0]
                u_elem[2 * i + 1] = u_full[n - 1, 1]

            stresses_gp, strains_gp, gp_coords = stress_rec.compute_element_stress(
                coords, u_elem, order=config.integration_order
            )

            # Average stress/strain over Gauss points
            all_stresses.append(stresses_gp.mean(axis=0).tolist())
            all_strains.append(strains_gp.mean(axis=0).tolist())
            gp_stresses_list.append(stresses_gp)
            gp_coords_list.append(gp_coords)

        # Von Mises per element
        von_mises_elem = [MaterialModel.von_mises_stress(np.array(s)) for s in all_stresses]

        # Nodal stress averaging
        nodal_stresses, nodal_strains = stress_rec.average_to_nodes(
            nodes=nodes,
            elements=[[e - 1 for e in elem] for elem in elements],
            displacements=u_full,
            gp_stresses=gp_stresses_list,
            gp_gp_coords=gp_coords_list,
        )

        nodal_von_mises = [
            float(MaterialModel.von_mises_stress(nodal_stresses[n]))
            for n in range(len(nodes))
        ]

        # Stats
        displacements_flat = u_full.tolist()

        max_disp = float(np.max(np.sqrt(u_full[:, 0] ** 2 + u_full[:, 1] ** 2)))
        max_vm = float(max(von_mises_elem))
        max_sxx = float(max(s[0] for s in all_stresses))
        max_syy = float(max(s[1] for s in all_stresses))
        max_txy = float(max(s[2] for s in all_stresses))

        # Build response
        result = FEAResultResponse(
            id=uuid.uuid4(),
            mesh_id=req.mesh_id,
            name=mesh.name + "_fea",
            analysis_type=req.analysis_type,
            material={
                "E": material.E,
                "nu": material.nu,
                "thickness": material.thickness,
            },
            node_count=len(nodes),
            displacements=displacements_flat,
            element_count=len(elements),
            stresses=all_stresses,
            strains=all_strains,
            von_mises=von_mises_elem,
            max_displacement=max_disp,
            max_von_mises_stress=max_vm,
            max_stress_xx=max_sxx,
            max_stress_yy=max_syy,
            max_shear_xy=max_txy,
            nodal_stresses=nodal_stresses.tolist(),
            nodal_von_mises=nodal_von_mises,
            reactions=None if reactions_matrix is None else reactions_matrix.tolist(),
            sum_reaction_x=sum_reaction_x,
            sum_reaction_y=sum_reaction_y,
            cantilever_benchmark=cantilever_benchmark,
        )

        return result, True, "Solution converged successfully"

    @staticmethod
    def _normalize_elements_to_one_based(elements_raw: List[List[int]], node_count: int) -> List[List[int]]:
        if not elements_raw:
            return []

        elements = [[int(v) for v in elem] for elem in elements_raw]
        flat = [idx for elem in elements for idx in elem]
        min_idx = min(flat)
        max_idx = max(flat)

        if min_idx == 0 and max_idx <= node_count - 1:
            return [[idx + 1 for idx in elem] for elem in elements]
        if min_idx >= 1 and max_idx <= node_count:
            return elements
        raise ValueError("Mesh element indices are out of valid node range")

    @staticmethod
    def _prepare_elements_for_solver(elements_raw: List[List[int]], nodes_raw: List[List[float]]) -> List[List[int]]:
        """Normalize indexing and enforce valid CCW triangle orientation for FEA."""
        elements = FEAService._normalize_elements_to_one_based(elements_raw, len(nodes_raw))
        nodes = np.asarray(nodes_raw, dtype=float)
        if len(nodes) == 0:
            return elements

        bbox = nodes.max(axis=0) - nodes.min(axis=0)
        area_tol = max(1e-14, float(np.linalg.norm(bbox)) ** 2 * 1e-14)
        prepared: List[List[int]] = []

        for elem in elements:
            if len(set(elem)) != len(elem):
                continue
            if any(idx < 1 or idx > len(nodes_raw) for idx in elem):
                raise ValueError("Mesh element indices are out of valid node range")

            if len(elem) == 3:
                p0, p1, p2 = nodes[[idx - 1 for idx in elem]]
                signed_area2 = float(
                    (p1[0] - p0[0]) * (p2[1] - p0[1])
                    - (p2[0] - p0[0]) * (p1[1] - p0[1])
                )
                if abs(signed_area2) * 0.5 <= area_tol:
                    continue
                if signed_area2 < 0.0:
                    elem = [elem[0], elem[2], elem[1]]

            prepared.append(elem)

        if elements and not prepared:
            raise ValueError("Mesh has no non-degenerate elements for FEA")
        return prepared


# Singleton
fea_service = FEAService()
