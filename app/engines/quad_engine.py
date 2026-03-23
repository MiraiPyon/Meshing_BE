import numpy as np
from typing import Tuple, List
from app.engines.base import MeshEngine


class QuadMeshEngine(MeshEngine):
    """
    Engine tạo lưới tứ giác có cấu trúc (structured grid).
    Chỉ hỗ trợ hình chữ nhật.
    """

    def generate(
        self,
        points: List[Tuple[float, float]],
        resolution: int = 10,
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate quad mesh cho rectangle.

        Args:
            points: Boundary points [x_min, y_min, x_max, y_max]
            resolution: Số phần tử theo mỗi chiều (nx = ny = resolution)

        Returns:
            nodes: List of [x, y] coordinates
            elements: List of [n1, n2, n3, n4] node indices (1-based)
        """
        # points = [x_min, y_min, x_max, y_max]
        x_min, y_min = points[0]
        x_max, y_max = points[1]

        # Tạo grid
        nx = resolution
        ny = resolution

        # Tạo node coordinates
        x = np.linspace(x_min, x_max, nx + 1)
        y = np.linspace(y_min, y_max, ny + 1)

        # Tạo mesh grid
        xv, yv = np.meshgrid(x, y, indexing='ij')

        # Flatten to get node coordinates
        nodes = np.column_stack([xv.flatten(), yv.flatten()])

        # Create elements (quads)
        elements = []
        for i in range(nx):
            for j in range(ny):
                # Node indices (1-based)
                n1 = i * (ny + 1) + j + 1
                n2 = n1 + 1
                n3 = n1 + (ny + 1) + 1
                n4 = n2 + (ny + 1) + 1
                elements.append([n1, n2, n3, n4])

        return nodes.tolist(), elements


class QuadMeshEngineFlexible(QuadMeshEngine):
    """
    Quad mesh engine với độ phân giải khác nhau theo x và y.
    """

    def generate_flexible(
        self,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        nx: int = 10,
        ny: int = 10,
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate quad mesh với resolution khác nhau cho x và y.

        Args:
            x_min, y_min: Tọa độ góc dưới trái
            x_max, y_max: Tọa độ góc trên phải
            nx: Số phần tử theo x
            ny: Số phần tử theo y

        Returns:
            nodes: List of [x, y] coordinates
            elements: List of [n1, n2, n3, n4] node indices (1-based)
        """
        # Tạo node coordinates
        x = np.linspace(x_min, x_max, nx + 1)
        y = np.linspace(y_min, y_max, ny + 1)

        # Tạo mesh grid
        xv, yv = np.meshgrid(x, y, indexing='ij')

        # Flatten to get node coordinates
        nodes = np.column_stack([xv.flatten(), yv.flatten()])

        # Create elements (quads)
        elements = []
        for i in range(nx):
            for j in range(ny):
                # Node indices (1-based)
                n1 = i * (ny + 1) + j + 1
                n2 = n1 + 1
                n3 = n1 + (ny + 1) + 1
                n4 = n2 + (ny + 1) + 1
                elements.append([n1, n2, n3, n4])

        return nodes.tolist(), elements
