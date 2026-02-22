from abc import ABC, abstractmethod
from typing import List, Tuple


class MeshEngine(ABC):
    """
    Strategy Interface – định nghĩa hành vi chung cho tất cả các thuật toán tạo lưới.
    Mọi engine đều phải implement phương thức `generate`.
    """

    @abstractmethod
    def generate(
        self,
        points: List[Tuple[float, float]],
        resolution: int = 10,
    ) -> Tuple[List[Tuple[float, float]], List[List[int]]]:
        """
        Generate mesh from a list of 2D boundary points.

        Args:
            points:     Boundary points as (x, y) tuples.
            resolution: Grid density hint.

        Returns:
            nodes:    Full list of node coordinates.
            elements: List of elements (each is a list of node indices).
        """
        ...
