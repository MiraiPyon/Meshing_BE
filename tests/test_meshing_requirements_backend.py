import math
from pathlib import Path

import pytest

from app.database.models import MeshType as MeshTypeEnum
from app.engines.build_delaunay import BuildDelaunay
from app.engines.delaunay_engine import DelaunayMeshEngine
from app.engines.fea.cantilever_benchmark import (
    CantileverBenchmarkCase,
    CantileverBenchmarkConfig,
    exact_neutral_axis_deflection,
    run_cantilever_benchmark,
    run_cantilever_case,
    write_cantilever_benchmark_artifacts,
)
from app.engines.pslg import build_pslg, parse_shape_dat, parse_shape_dat_components
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


def test_shape_dat_parser_supports_multiple_components():
    shape_dat = """
    OUTER
    0 0
    1 0
    1 1
    0 1
    END
    OUTER
    3 0
    4 0
    4 1
    3 1
    END
    """

    components = parse_shape_dat_components(shape_dat)
    assert len(components) == 2
    assert len(components[0][0]) == 4
    assert len(components[1][0]) == 4


def test_build_delaunay_native_deterministic_empty_circumcircle():
    points = [
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
        [0.5, 0.45],
    ]

    tris_a = BuildDelaunay.triangulate(points)
    tris_b = BuildDelaunay.triangulate(points)

    assert tris_a == tris_b
    assert len(tris_a) > 0
    assert BuildDelaunay.validate_empty_circumcircle(points, tris_a)


def test_build_delaunay_structured_grid_empty_circumcircle():
    points = [[float(x), float(y)] for y in range(4) for x in range(5)]
    triangles = BuildDelaunay.triangulate(points)

    assert len(triangles) > 0
    assert BuildDelaunay.validate_empty_circumcircle(points, triangles)


def test_delaunay_engine_no_scipy_delaunay_import():
    source = Path("app/engines/delaunay_engine.py").read_text(encoding="utf-8")
    assert "from scipy.spatial import Delaunay" not in source
    assert "Delaunay(" not in source


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


def test_delaunay_adaptive_size_field_and_smoothing_keep_valid_mesh():
    engine = DelaunayMeshEngine()
    outer = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]

    pslg = build_pslg(outer_boundary=outer, holes=[])
    nodes, elements = engine.generate_from_pslg(
        pslg=pslg,
        resolution=10,
        min_angle=20.7,
        max_edge_length=0.5,
        max_refine_iterations=4,
        smoothing_iterations=1,
        adaptive_size_field=True,
        adaptive_min_edge_factor=0.45,
        adaptive_influence_radius_factor=0.2,
    )

    assert len(nodes) > 0
    assert len(elements) > 0
    one_based = [[idx + 1 for idx in tri] for tri in elements]
    assert DelaunayMeshEngine.check_empty_circumcircle(nodes, one_based)

    analysis = mesh_service._build_mesh_analysis(nodes, elements, MeshTypeEnum.DELAUNAY)
    quality = analysis["dashboard"]["mesh_quality"]
    assert quality["min_angle_deg"] is not None
    assert quality["skinny_triangle_count"] < len(elements)


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
    assert all(len(edge) == 10 for edge in conn["edges_matrix"])


def test_fea_service_index_normalization_supports_zero_and_one_based():
    zero_based = [[0, 1, 2], [1, 3, 2]]
    one_based = [[1, 2, 3], [2, 4, 3]]

    normalized_zero = FEAService._normalize_elements_to_one_based(zero_based, 4)
    normalized_one = FEAService._normalize_elements_to_one_based(one_based, 4)

    assert normalized_zero == one_based
    assert normalized_one == one_based


def test_fea_service_prepares_degenerate_and_cw_triangles_for_solver():
    nodes = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.5, 0.0]]
    elements = [[0, 2, 1], [0, 1, 3]]

    prepared = FEAService._prepare_elements_for_solver(elements, nodes)

    assert prepared == [[1, 2, 3]]


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


def test_cantilever_exact_solution_matches_section_iv_parameters():
    cfg = CantileverBenchmarkConfig()

    assert exact_neutral_axis_deflection(0.0, cfg) == 0.0
    assert cfg.exact_tip_deflection == pytest.approx(-2.0e-4)


def test_cantilever_benchmark_report_documents_section_iv_mapping(tmp_path):
    report_path = tmp_path / "cantilever.md"
    csv_path = tmp_path / "cantilever.csv"

    results = write_cantilever_benchmark_artifacts(report_path=report_path, csv_path=csv_path)
    report = report_path.read_text(encoding="utf-8")

    assert len(results) == 4
    assert csv_path.exists()
    assert "Section IV uses LST/T6 triangular elements" in report
    assert "supports T3 and Q4 only" in report
    assert "clamp at `x=0`" in report
    assert "Exact tip deflection: `-2.000000e-04 m`" in report


def test_q4_cantilever_benchmark_converges_against_exact_solution():
    results = run_cantilever_benchmark(
        cases=[
            CantileverBenchmarkCase("Q4-4x2", "Q4", {"nx": 4, "ny": 2}),
            CantileverBenchmarkCase("Q4-10x2", "Q4", {"nx": 10, "ny": 2}),
            CantileverBenchmarkCase("Q4-20x4", "Q4", {"nx": 20, "ny": 4}),
        ]
    )

    rel_errors = [result["tip_rel_error"] for result in results]
    assert all(result["status"] == "PASS" for result in results)
    assert rel_errors[0] > rel_errors[1] > rel_errors[2]
    assert rel_errors[-1] <= 0.12


def test_t3_delaunay_cantilever_mesh_is_valid_for_fea():
    result = run_cantilever_case(
        CantileverBenchmarkCase(
            "T3-Delaunay-smoke",
            "T3",
            {
                "max_edge_length": 0.75,
                "min_angle": 20.7,
                "max_circumradius_ratio": math.sqrt(2.0),
                "max_refine_iterations": 1,
            },
        )
    )

    assert result["status"] == "PASS"
    assert result["element_count"] > 0
    assert result["tip_uy"] < 0.0
    assert result["mesh_s"] < 2.0


def test_delaunay_engine_returns_ccw_non_degenerate_triangles_for_slender_beam():
    engine = DelaunayMeshEngine()
    pslg = build_pslg(
        outer_boundary=[(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)],
        holes=[],
    )

    nodes, elements = engine.generate_from_pslg(
        pslg=pslg,
        max_edge_length=0.75,
        min_angle=20.7,
        max_circumradius_ratio=math.sqrt(2.0),
        max_refine_iterations=1,
    )

    assert len(elements) > 0
    for a, b, c in elements:
        p0, p1, p2 = nodes[a], nodes[b], nodes[c]
        signed_area2 = (
            (p1[0] - p0[0]) * (p2[1] - p0[1])
            - (p2[0] - p0[0]) * (p1[1] - p0[1])
        )
        assert signed_area2 > 1e-12


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
            max_circumradius_ratio=math.sqrt(2.0),
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
            max_circumradius_ratio=math.sqrt(2.0),
            nx=4,
            ny=3,
        )
