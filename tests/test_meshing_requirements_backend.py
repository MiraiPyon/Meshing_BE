import math

import pytest

from app.database.models import MeshType as MeshTypeEnum
from app.engines.delaunay_engine import DelaunayMeshEngine
from app.engines.pslg import build_pslg, parse_shape_dat
from app.services.fea_service import FEAService
from app.services.mesh_service import mesh_service


def test_pslg_normalization_enforces_outer_ccw_and_hole_cw():
    # Outer loop intentionally CW and includes duplicate closing point.
    outer_cw = [(0.0, 0.0), (0.0, 4.0), (6.0, 4.0), (6.0, 0.0), (0.0, 0.0)]
    # Hole intentionally CCW (should be flipped to CW).
    hole_ccw = [(2.0, 1.0), (4.0, 1.0), (4.0, 3.0), (2.0, 3.0)]

    pslg = build_pslg(outer_boundary=outer_cw, holes=[hole_ccw])

    assert pslg["loops"][0]["type"] == "outer"
    assert pslg["loops"][0]["orientation"] == "CCW"
    assert pslg["loops"][1]["type"] == "hole"
    assert pslg["loops"][1]["orientation"] == "CW"

    # Outer has 4 segments and one hole with 4 segments.
    assert len(pslg["segments"]) == 8


def test_pslg_rejects_self_intersection():
    bowtie = [(0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)]
    with pytest.raises(ValueError, match="self-intersection"):
        build_pslg(outer_boundary=bowtie, holes=[])


def test_shape_dat_parser_outer_and_hole_sections():
    shape_dat = """
    # outer boundary
    OUTER
    0 0
    5 0
    5 3
    0 3
    END

    HOLE
    1 1
    2 1
    2 2
    1 2
    END
    """

    outer, holes = parse_shape_dat(shape_dat)
    assert len(outer) == 4
    assert len(holes) == 1
    assert len(holes[0]) == 4


def test_delaunay_refinement_produces_quality_metrics_and_circumcircle_check():
    engine = DelaunayMeshEngine()
    outer = [(0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (0.0, 2.0)]

    nodes, elements = engine.generate(
        points=outer,
        resolution=20,
        min_angle=20.7,
        max_edge_length=0.45,
        max_refine_iterations=20,
    )

    assert len(nodes) > 0
    assert len(elements) > 0

    analysis = mesh_service._build_mesh_analysis(nodes, elements, MeshTypeEnum.DELAUNAY)
    quality = analysis["dashboard"]["mesh_quality"]

    # Refinement should strongly reduce very poor triangles.
    assert quality["min_angle_deg"] is not None
    assert quality["min_angle_deg"] >= 19.5
    assert quality["max_circumradius_edge_ratio"] <= math.sqrt(2.0) + 0.2

    one_based = [[idx + 1 for idx in tri] for tri in elements]
    assert DelaunayMeshEngine.check_empty_circumcircle(nodes, one_based)


def test_mesh_analysis_builds_nodes_edges_tris_matrices_and_dof():
    nodes = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    elements = [[0, 1, 2]]

    analysis = mesh_service._build_mesh_analysis(nodes, elements, MeshTypeEnum.DELAUNAY)
    conn = analysis["connectivity_matrices"]

    assert analysis["element_type"] == "T3"
    assert analysis["dof_total"] == 6

    assert len(conn["nodes_matrix"]) == 3
    assert len(conn["edges_matrix"]) == 3
    assert len(conn["tris_matrix"]) == 1


def test_fea_service_index_normalization_supports_zero_and_one_based():
    zero_based = [[0, 1, 2], [1, 3, 2]]
    one_based = [[1, 2, 3], [2, 4, 3]]

    normalized_zero = FEAService._normalize_elements_to_one_based(zero_based, 4)
    normalized_one = FEAService._normalize_elements_to_one_based(one_based, 4)

    assert normalized_zero == one_based
    assert normalized_one == one_based


def test_quad_mesh_generates_ccw_elements():
    from app.engines.factory import MeshEngineFactory
    engine = MeshEngineFactory.create("quad")
    outer = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    nodes, elements = engine.generate(points=outer, nx=2, ny=2)
    assert len(nodes) == 9
    assert len(elements) == 4

    # Get first element nodes
    elem1 = elements[0]
    p1 = nodes[elem1[0] - 1]
    p2 = nodes[elem1[1] - 1]
    p3 = nodes[elem1[2] - 1]
    p4 = nodes[elem1[3] - 1]

    # Check CCW orientation: Cross product of diagonals should be positive
    def cross2d(u, v):
        return u[0] * v[1] - u[1] * v[0]

    v1 = [p3[0] - p1[0], p3[1] - p1[1]]
    v2 = [p4[0] - p2[0], p4[1] - p2[1]]
    assert cross2d(v1, v2) > 0, "Quad element is not CCW oriented (bowtie or CW)"


def test_strategy_pattern_uniform_generation():
    from app.engines.factory import MeshEngineFactory

    quad_engine = MeshEngineFactory.create("quad")
    delaunay_engine = MeshEngineFactory.create("delaunay")

    outer = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    # Both should accept the exact same signature
    nodes_q, elements_q = quad_engine.generate(points=outer, holes=[], nx=2, ny=2)
    nodes_d, elements_d = delaunay_engine.generate(points=outer, holes=[], max_area=0.5)

    assert len(nodes_q) > 0 and len(elements_q) > 0
    assert len(nodes_d) > 0 and len(elements_d) > 0


def test_delaunay_stability_for_wrench_like_polygon_with_holes():
    engine = DelaunayMeshEngine()
    outer = [
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 5.0),
        (5.0, 5.0),
        (5.0, 2.5),
        (3.0, 2.5),
        (3.0, 5.0),
        (0.0, 5.0),
    ]
    holes = [
        [(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)],
        [(6.0, 2.0), (7.0, 2.0), (7.0, 4.0), (6.0, 4.0)],
    ]

    pslg = build_pslg(outer_boundary=outer, holes=holes)
    nodes, elements = engine.generate_from_pslg(
        pslg=pslg,
        resolution=25,
        min_angle=20.7,
        max_edge_length=0.6,
        max_refine_iterations=30,
    )

    assert len(nodes) > 0
    assert len(elements) > 0
    one_based = [[idx + 1 for idx in tri] for tri in elements]
    assert engine.check_empty_circumcircle(nodes=nodes, elements=one_based)


def test_quad_sketch_guardrail_rejects_holes_and_non_rectangles():
    with pytest.raises(ValueError, match="no holes"):
        mesh_service._create_mesh_from_loops(
            db=None,  # not used because validation fails before DB operations
            user_id=None,
            name="invalid_quad_hole",
            outer=[(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
            holes=[[(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)]],
            element_type="quad",
            max_area=None,
            min_angle=20.7,
            max_edge_length=None,
            nx=4,
            ny=3,
        )

    with pytest.raises(ValueError, match="axis-aligned rectangular"):
        mesh_service._create_mesh_from_loops(
            db=None,  # not used because validation fails before DB operations
            user_id=None,
            name="invalid_quad_shape",
            outer=[(0.0, 0.0), (4.0, 0.0), (3.0, 2.0), (0.0, 3.0)],
            holes=[],
            element_type="quad",
            max_area=None,
            min_angle=20.7,
            max_edge_length=None,
            nx=4,
            ny=3,
        )
