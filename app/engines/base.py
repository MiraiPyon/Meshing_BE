from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class MeshEngine(ABC):
    """
    Strategy Interface – định nghĩa hành vi chung cho tất cả các thuật toán tạo lưới.
    Mọi engine đều phải implement phương thức `generate`.
    """

    @abstractmethod
    def generate(
        self,
        points: List[Tuple[float, float]],
        holes: Optional[List[List[Tuple[float, float]]]] = None,
        resolution: int = 10,
        **kwargs
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate mesh from a list of 2D boundary points and optional holes.

        Args:
            points:     Boundary points as (x, y) tuples.
            holes:      Optional list of holes, where each hole is a list of points.
            resolution: Grid density hint.
            **kwargs:   Additional algorithm-specific parameters (nx, ny, max_area, etc.)

        Returns:
            nodes:    Full list of node coordinates.
            elements: List of elements (each is a list of node indices).
        """
        ...
