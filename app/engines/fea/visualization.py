"""
FEA Visualization – Vẽ kết quả FEA: mesh, deformed shape, stress contours.
"""

import io
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as tri
from matplotlib import cm
from typing import List, Optional
from sqlalchemy.orm import Session

from app.database.models import Mesh as MeshModel


class FEAVisualizer:
    """
    Visualization cho kết quả FEA 2D.

    Hỗ trợ:
      - Vẽ mesh gốc (nodes + elements)
      - Deformed shape (overlay)
      - Stress contour (von Mises, Sxx, Syy, Sxy)
      - Displacement contour
    """

    def __init__(self, figsize: tuple = (10, 8), dpi: int = 150):
        self.figsize = figsize
        self.dpi = dpi

    # ---- Core plotting ----

    def plot_mesh(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        displacements: Optional[np.ndarray] = None,
        displacement_scale: float = 1.0,
        plot_type: str = "mesh",
        scalar_field: Optional[np.ndarray] = None,
        title: Optional[str] = None,
        show_nodes: bool = True,
        show_element_ids: bool = False,
        show_node_ids: bool = False,
        cmap: str = "viridis",
        colorbar_label: Optional[str] = None,
    ) -> bytes:
        """
        Vẽ mesh với optional scalar field.

        Args:
            nodes:           (n, 2) tọa độ node
            elements:        list of (n_elem_nodes,) node indices (0-based)
            displacements:   (n, 2) displacements (optional)
            displacement_scale: scale factor cho displacement
            plot_type:      "mesh", "von_mises", "displacement", "stress_xx", "stress_yy", "shear_xy"
            scalar_field:   (n,) hoặc (n_elem,) giá trị để contour
            title:           tiêu đề figure
            show_nodes:     hiển thị đỉnh node
            cmap:           colormap

        Returns:
            PNG bytes
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        ax.set_aspect("equal")
        ax.axis("off")

        # Original positions
        x = nodes[:, 0]
        y = nodes[:, 1]

        # Deformed shape
        if displacements is not None and displacement_scale != 0:
            x_def = x + displacements[:, 0] * displacement_scale
            y_def = y + displacements[:, 1] * displacement_scale
        else:
            x_def, y_def = x, y

        # ---- Draw elements ----
        if len(elements[0]) == 3:
            self._plot_triangles(ax, nodes, elements, x_def, y_def, scalar_field, cmap, plot_type)
        else:
            self._plot_quads(ax, nodes, elements, x_def, y_def, scalar_field, cmap, plot_type)

        # ---- Node markers ----
        if show_nodes:
            ax.plot(x_def, y_def, "k.", markersize=3, zorder=5)

        # ---- Node IDs ----
        if show_node_ids:
            for i, (xi, yi) in enumerate(zip(x_def, y_def, strict=True)):
                ax.text(xi, yi, str(i), fontsize=5, ha="center", va="bottom", zorder=6)

        # ---- Colorbar ----
        if scalar_field is not None:
            sm = cm.ScalarMappable(cmap=cmap)
            sm.set_array(scalar_field)
            cbar = fig.colorbar(sm, ax=ax, shrink=0.8)
            if colorbar_label:
                cbar.set_label(colorbar_label, fontsize=10)

        # ---- Deformed overlay ----
        if displacements is not None and displacement_scale != 0 and plot_type == "mesh":
            ax.plot(x, y, "b-", linewidth=0.5, alpha=0.3, label="Original")
            ax.legend(fontsize=8, loc="best")

        # ---- Title ----
        if title:
            ax.set_title(title, fontsize=12)
        else:
            ax.set_title(f"FEA Result – {plot_type}", fontsize=12)

        ax.set_xlabel("x (m)", fontsize=9)
        ax.set_ylabel("y (m)", fontsize=9)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=self.dpi)
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _plot_triangles(
        self, ax, nodes, elements, x_def, y_def, scalar_field, cmap, plot_type
    ):
        """Vẽ tam giác."""
        n_elem = len(elements)

        if scalar_field is not None:
            # Element centroid values for contour
            if len(scalar_field) == n_elem:
                values = scalar_field
            else:
                values = scalar_field  # nodal values

            if not elements:
                tc = tri.Triangulation(nodes[:, 0], nodes[:, 1], elements)
                ax.tripcolor(tc, values, cmap=cmap, shading="flat")
                return

            # Use triangulation for smooth-ish contour
            tc = tri.Triangulation(nodes[:, 0], nodes[:, 1], elements)
            if len(scalar_field) == len(nodes):
                ax.tripcolor(tc, scalar_field, cmap=cmap, shading="gouraud")
            else:
                # Element-wise coloring
                elem_vals = [np.mean([scalar_field[n] for n in e]) for e in elements]
                colors = [plt.cm.ScalarMappable(cmap=cmap).to_rgba(v) for v in elem_vals]
                for i, elem in enumerate(elements):
                    xs = [x_def[n] for n in elem] + [x_def[elem[0]]]
                    ys = [y_def[n] for n in elem] + [y_def[elem[0]]]
                    ax.fill(xs, ys, color=colors[i], edgecolor="none")
                    ax.plot(xs, ys, "k-", linewidth=0.3)
        else:
            # Wireframe mesh
            for elem in elements:
                xs = [x_def[n] for n in elem] + [x_def[elem[0]]]
                ys = [y_def[n] for n in elem] + [y_def[elem[0]]]
                ax.plot(xs, ys, "b-", linewidth=0.8)

    def _plot_quads(
        self, ax, nodes, elements, x_def, y_def, scalar_field, cmap, plot_type
    ):
        """Vẽ tứ giác."""
        from matplotlib.collections import PolyCollection

        n_elem = len(elements)

        if scalar_field is not None and len(scalar_field) == n_elem:
            # Element-wise coloring
            quads = []
            colors = []
            for elem in elements:
                xs = [x_def[n] for n in elem]
                ys = [y_def[n] for n in elem]
                quads.append(list(zip(xs, ys, strict=True)))
                # Average scalar value for this element
                val = np.mean([scalar_field[n] for n in elem])
                colors.append(val)

            coll = PolyCollection(quads, array=np.array(colors), cmap=cmap, edgecolor="none")
            ax.add_collection(coll)
            ax.autoscale_view()
        else:
            # Wireframe
            for elem in elements:
                xs = [x_def[n] for n in elem] + [x_def[elem[0]]]
                ys = [y_def[n] for n in elem] + [y_def[elem[0]]]
                ax.plot(xs, ys, "b-", linewidth=0.8)

            if scalar_field is not None and len(scalar_field) == len(nodes):
                # Nodal coloring for quads via tricontourf hack
                tc = tri.Triangulation(nodes[:, 0], nodes[:, 1])
                ax.tricontourf(tc, scalar_field, cmap=cmap, alpha=0.3)

    # ---- Quick plots ----

    def plot_von_mises(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        von_mises: np.ndarray,
        displacements: Optional[np.ndarray] = None,
        displacement_scale: float = 1.0,
    ) -> bytes:
        """Vẽ contour von Mises stress."""
        is_nodal = len(von_mises) == len(nodes)
        label = "Von Mises Stress (Pa)" if is_nodal else "Von Mises (element avg, Pa)"
        return self.plot_mesh(
            nodes=nodes,
            elements=elements,
            displacements=displacements,
            displacement_scale=displacement_scale,
            plot_type="von_mises",
            scalar_field=von_mises,
            title="Von Mises Stress",
            colorbar_label=label,
            cmap="hot_r",
        )

    def plot_displacement(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        displacements: np.ndarray,
        displacement_scale: float = 1.0,
    ) -> bytes:
        """Vẽ contour displacement magnitude."""
        disp_mag = np.sqrt(displacements[:, 0] ** 2 + displacements[:, 1] ** 2)
        return self.plot_mesh(
            nodes=nodes,
            elements=elements,
            displacements=displacements,
            displacement_scale=displacement_scale,
            plot_type="displacement",
            scalar_field=disp_mag,
            title="Displacement Magnitude",
            colorbar_label="Displacement (m)",
            cmap="plasma",
        )

    def plot_deformed_mesh(
        self,
        nodes: np.ndarray,
        elements: List[List[int]],
        displacements: np.ndarray,
        displacement_scale: float = 1.0,
    ) -> bytes:
        """Vẽ mesh gốc + deformed mesh overlay."""
        return self.plot_mesh(
            nodes=nodes,
            elements=elements,
            displacements=displacements,
            displacement_scale=displacement_scale,
            plot_type="mesh",
            title=f"Deformed Mesh (scale={displacement_scale:.1f})",
        )

    # ---- Database integration ----

    def plot_mesh_from_db(
        self,
        db: Session,
        mesh_id: str,
        displacement_scale: float = 0.0,
        plot_type: str = "mesh",
        displacements: Optional[np.ndarray] = None,
        scalar_field: Optional[np.ndarray] = None,
        scalar_label: Optional[str] = None,
    ) -> bytes:
        """Load mesh from DB and plot."""
        import uuid

        mesh_uuid = uuid.UUID(str(mesh_id)) if isinstance(mesh_id, str) else mesh_id
        mesh = db.query(MeshModel).filter(MeshModel.id == mesh_uuid).first()
        if not mesh:
            raise ValueError(f"Mesh {mesh_id} not found")

        nodes = np.array(json.loads(mesh.nodes))
        elements_raw = json.loads(mesh.elements)

        return self.plot_mesh(
            nodes=nodes,
            elements=elements_raw,
            displacements=displacements,
            displacement_scale=displacement_scale,
            plot_type=plot_type,
            scalar_field=scalar_field,
            colorbar_label=scalar_label,
        )
