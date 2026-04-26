"""Tests for the Boolean Geometry Engine (CSG operations)."""

import pytest
from app.engines.boolean_engine import boolean_operation


# --- Test fixtures ---

SQUARE_A = [[0, 0], [4, 0], [4, 4], [0, 4]]          # 4×4 square at origin
SQUARE_B = [[2, 2], [6, 2], [6, 6], [2, 6]]          # 4×4 square offset by (2,2)
SQUARE_INSIDE = [[1, 1], [3, 1], [3, 3], [1, 3]]     # 2×2 inside A
SQUARE_OUTSIDE = [[10, 10], [14, 10], [14, 14], [10, 14]]  # non-overlapping


class TestBooleanUnion:
    def test_union_overlapping(self):
        result = boolean_operation(SQUARE_A, SQUARE_B, "union")
        assert result["is_valid"]
        # Union of two 4×4 squares overlapping in a 2×2 area: 16+16-4 = 28
        assert abs(result["area"] - 28.0) < 0.01
        assert len(result["outer_boundary"]) >= 4
        assert result["holes"] == []

    def test_union_non_overlapping(self):
        result = boolean_operation(SQUARE_A, SQUARE_OUTSIDE, "union")
        assert result["is_valid"]
        # MultiPolygon → takes the larger one (both are 16, takes first)
        assert result["area"] > 0

    def test_union_contained(self):
        result = boolean_operation(SQUARE_A, SQUARE_INSIDE, "union")
        assert result["is_valid"]
        assert abs(result["area"] - 16.0) < 0.01  # A contains B → union = A


class TestBooleanSubtract:
    def test_subtract_overlapping(self):
        result = boolean_operation(SQUARE_A, SQUARE_B, "subtract")
        assert result["is_valid"]
        # A - B: 16 - 4 (overlap) = 12
        assert abs(result["area"] - 12.0) < 0.01

    def test_subtract_contained_creates_hole(self):
        result = boolean_operation(SQUARE_A, SQUARE_INSIDE, "subtract")
        assert result["is_valid"]
        # Should create a hole
        assert abs(result["area"] - (16.0 - 4.0)) < 0.01
        assert len(result["holes"]) == 1

    def test_subtract_no_overlap_returns_original(self):
        result = boolean_operation(SQUARE_INSIDE, SQUARE_OUTSIDE, "subtract")
        assert result["is_valid"]
        # No overlap → A - B = A
        assert abs(result["area"] - 4.0) < 0.01


class TestBooleanIntersect:
    def test_intersect_overlapping(self):
        result = boolean_operation(SQUARE_A, SQUARE_B, "intersect")
        assert result["is_valid"]
        # Overlap is a 2×2 square: area = 4
        assert abs(result["area"] - 4.0) < 0.01
        assert result["num_vertices"] == 4

    def test_intersect_contained(self):
        result = boolean_operation(SQUARE_A, SQUARE_INSIDE, "intersect")
        assert result["is_valid"]
        assert abs(result["area"] - 4.0) < 0.01

    def test_intersect_no_overlap_raises(self):
        with pytest.raises(ValueError, match="empty"):
            boolean_operation(SQUARE_A, SQUARE_OUTSIDE, "intersect")


class TestBooleanEdgeCases:
    def test_invalid_operation(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            boolean_operation(SQUARE_A, SQUARE_B, "xor")

    def test_triangle_inputs(self):
        tri_a = [[0, 0], [4, 0], [2, 4]]
        tri_b = [[1, 0], [5, 0], [3, 4]]
        result = boolean_operation(tri_a, tri_b, "union")
        assert result["is_valid"]
        assert result["area"] > 0

    def test_result_has_all_fields(self):
        result = boolean_operation(SQUARE_A, SQUARE_B, "union")
        assert "outer_boundary" in result
        assert "holes" in result
        assert "area" in result
        assert "num_vertices" in result
        assert "is_valid" in result
