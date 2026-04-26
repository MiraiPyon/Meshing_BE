"""Factory for selecting meshing engines at runtime."""

from app.engines.base import MeshEngine
from app.engines.delaunay_engine import DelaunayMeshEngine
from app.engines.quad_engine import QuadMeshEngine


class MeshEngineFactory:
    """Factory Pattern: instantiate meshing strategy by name."""

    @staticmethod
    def create(strategy: str) -> MeshEngine:
        key = strategy.strip().lower()
        if key in {"quad", "mapped", "uniform", "q4"}:
            return QuadMeshEngine()
        if key in {"delaunay", "triangle", "tri", "t3"}:
            return DelaunayMeshEngine()
        raise ValueError(f"Unsupported meshing strategy: {strategy}")
