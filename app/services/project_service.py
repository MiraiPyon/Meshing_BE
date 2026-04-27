"""Project snapshot service."""

import json
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.models import Geometry as GeometryModel
from app.database.models import Mesh as MeshModel
from app.database.models import ProjectSnapshot
from app.schemas.request import ProjectCreate, ProjectUpdate
from app.schemas.response import ProjectSnapshotResponse


class ProjectService:
    """CRUD service for project snapshots (ownership-safe)."""

    def create_project(self, db: Session, data: ProjectCreate, user_id: UUID) -> ProjectSnapshotResponse:
        geometry, mesh = self._validate_owned_refs(
            db=db,
            user_id=user_id,
            geometry_id=data.geometry_id,
            mesh_id=data.mesh_id,
        )

        snapshot = ProjectSnapshot(
            user_id=user_id,
            name=data.name,
            geometry_id=geometry.id if geometry else None,
            mesh_id=mesh.id if mesh else None,
            element_type=self._resolve_element_type(data.element_type, mesh),
            meshing_params=self._resolve_meshing_params(data.meshing_params, mesh),
            notes=data.notes,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return self._to_response(snapshot)

    def get_project(self, db: Session, project_id: UUID, user_id: UUID) -> Optional[ProjectSnapshotResponse]:
        project = db.query(ProjectSnapshot).filter(
            ProjectSnapshot.id == project_id,
            ProjectSnapshot.user_id == user_id,
        ).first()
        if not project:
            return None
        return self._to_response(project)

    def list_projects(self, db: Session, user_id: UUID) -> List[ProjectSnapshotResponse]:
        projects = db.query(ProjectSnapshot).filter(
            ProjectSnapshot.user_id == user_id,
        ).order_by(ProjectSnapshot.created_at.desc()).all()
        return [self._to_response(project) for project in projects]

    def update_project(
        self,
        db: Session,
        project_id: UUID,
        data: ProjectUpdate,
        user_id: UUID,
    ) -> Optional[ProjectSnapshotResponse]:
        project = db.query(ProjectSnapshot).filter(
            ProjectSnapshot.id == project_id,
            ProjectSnapshot.user_id == user_id,
        ).first()
        if not project:
            return None

        patch = data.model_dump(exclude_unset=True)
        geometry_id = patch.get("geometry_id", project.geometry_id)
        mesh_id = patch.get("mesh_id", project.mesh_id)
        geometry, mesh = self._validate_owned_refs(
            db=db,
            user_id=user_id,
            geometry_id=geometry_id,
            mesh_id=mesh_id,
        )

        if "name" in patch:
            project.name = patch["name"]
        project.geometry_id = geometry.id if geometry else None
        project.mesh_id = mesh.id if mesh else None

        if "element_type" in patch:
            project.element_type = self._resolve_element_type(patch.get("element_type"), mesh)
        elif project.element_type is None:
            project.element_type = self._resolve_element_type(None, mesh)

        if "meshing_params" in patch:
            project.meshing_params = self._resolve_meshing_params(patch.get("meshing_params"), mesh)
        elif project.meshing_params is None:
            project.meshing_params = self._resolve_meshing_params(None, mesh)

        if "notes" in patch:
            project.notes = patch["notes"]

        db.commit()
        db.refresh(project)
        return self._to_response(project)

    def delete_project(self, db: Session, project_id: UUID, user_id: UUID) -> bool:
        project = db.query(ProjectSnapshot).filter(
            ProjectSnapshot.id == project_id,
            ProjectSnapshot.user_id == user_id,
        ).first()
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True

    @staticmethod
    def _validate_owned_refs(
        db: Session,
        user_id: UUID,
        geometry_id: Optional[UUID],
        mesh_id: Optional[UUID],
    ) -> tuple[Optional[GeometryModel], Optional[MeshModel]]:
        geometry = None
        mesh = None

        if geometry_id is not None:
            geometry = db.query(GeometryModel).filter(
                GeometryModel.id == geometry_id,
                GeometryModel.user_id == user_id,
            ).first()
            if geometry is None:
                raise ValueError(f"Geometry {geometry_id} not found")

        if mesh_id is not None:
            mesh = db.query(MeshModel).join(GeometryModel).filter(
                MeshModel.id == mesh_id,
                GeometryModel.user_id == user_id,
            ).first()
            if mesh is None:
                raise ValueError(f"Mesh {mesh_id} not found")

            if geometry is None:
                geometry = db.query(GeometryModel).filter(GeometryModel.id == mesh.geometry_id).first()
            elif mesh.geometry_id != geometry.id:
                raise ValueError("mesh_id does not belong to geometry_id")

        return geometry, mesh

    @staticmethod
    def _resolve_element_type(element_type: Optional[str], mesh: Optional[MeshModel]) -> Optional[str]:
        if element_type is not None:
            return element_type.strip() or None

        if mesh is None:
            return None

        if mesh.mesh_type.value == "quad":
            return "Q4"
        return "T3"

    @staticmethod
    def _resolve_meshing_params(meshing_params: Optional[dict], mesh: Optional[MeshModel]) -> Optional[str]:
        if meshing_params is not None:
            return json.dumps(meshing_params)
        if mesh is not None and mesh.meshing_params:
            return mesh.meshing_params
        return None

    @staticmethod
    def _to_response(project: ProjectSnapshot) -> ProjectSnapshotResponse:
        return ProjectSnapshotResponse(
            id=project.id,
            name=project.name,
            geometry_id=project.geometry_id,
            mesh_id=project.mesh_id,
            element_type=project.element_type,
            meshing_params=json.loads(project.meshing_params) if project.meshing_params else None,
            notes=project.notes,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


project_service = ProjectService()
