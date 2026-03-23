"""
Quick test: Verify FEA core modules compile and run.
Tests a simple cantilever beam (plane stress).
"""

import sys
sys.path.insert(0, "e:/Code/Meshing_BE")

import numpy as np

from app.engines.fea.shape_functions import ShapeFunctions
from app.engines.fea.gaussian_quadrature import GaussianQuadrature
from app.engines.fea.material import MaterialModel, AnalysisType
from app.engines.fea.stiffness import ElementStiffness
from app.engines.fea.assembly import GlobalAssembler, BoundaryCondition, NodalForce
from app.engines.fea.solver import FEASolver, SolverConfig


def test_cantilever_beam():
    """
    Cantilever beam: 1m x 0.2m, E=210 GPa, nu=0.3, t=0.01m.
    Fixed at left (x=0), load F=1000N downward at right end (x=1, y=0).
    """
    # Mesh: 10x2 quad
    nx, ny = 10, 2
    x_nodes = np.linspace(0, 1, nx + 1)
    y_nodes = np.linspace(0, 0.2, ny + 1)

    # Build nodes
    nodes = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            nodes.append([x_nodes[i], y_nodes[j]])
    nodes = np.array(nodes)
    n_nodes = len(nodes)

    # Build quad elements (CCW)
    elements = []
    for i in range(nx):
        for j in range(ny):
            # meshgrid indexing='ij': flatten = i*(ny+1)+j
            # CCW for bilinear quad: BL, BR, TR, TL
            n1 = i * (ny + 1) + j + 1        # bottom-left
            n2 = (i + 1) * (ny + 1) + j + 1  # top-left (goes up column first)
            n3 = (i + 1) * (ny + 1) + j + 2  # top-right
            n4 = i * (ny + 1) + j + 2        # bottom-right
            elements.append([n1, n2, n3, n4])  # 1-based CCW

    # Material: steel, plane stress
    material = MaterialModel(E=210e9, nu=0.3, thickness=0.01)

    # Solver
    config = SolverConfig(integration_order="2x2", bc_method="elimination")
    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=material,
        analysis_type=AnalysisType.PLANE_STRESS,
        config=config,
    )

    # BCs: fixed at left edge (all nodes at x=0)
    bc_list = []
    for n in range(ny + 1):
        bc_list.append(BoundaryCondition(node_id=n, dof="ux", value=0.0))
        bc_list.append(BoundaryCondition(node_id=n, dof="uy", value=0.0))

    # Force: distributed load at right edge (y=0) downward
    nodal_forces = []
    right_edge_nodes = [i * (ny + 1) for i in range(nx + 1)]
    # Each node carries equal share of total load
    force_per_node = 1000.0 / len(right_edge_nodes)
    for n in right_edge_nodes:
        nodal_forces.append(NodalForce(node_id=n, dof="fy", value=-force_per_node))

    # Solve
    u_full, success, message = solver.run(bc_list, nodal_forces)

    assert success, f"Solver failed: {message}"
    print(f"Solver: {message}")

    # Check max displacement at right-bottom node
    max_disp = np.max(np.abs(u_full))
    print(f"Max displacement: {max_disp:.6e} m")

    # Expected: cantilever beam tip deflection ≈ FL³/3EI
    # L=1, F=1000, E=210e9, I = t*h³/12 = 0.01*(0.2)³/12 = 6.67e-6
    # δ ≈ 1000 * 1³ / (3 * 210e9 * 6.67e-6) ≈ 2.39e-4 m
    I = 0.01 * (0.2 ** 3) / 12
    expected = force_per_node * len(right_edge_nodes) * 1 ** 3 / (3 * 210e9 * I)
    print(f"Expected (analytic): ~{expected:.6e} m")
    print(f"Max displacement ratio: {max_disp / expected:.2f} (should be ~1.0)")

    # Sanity checks
    assert max_disp > 1e-6, "Displacement too small"
    assert max_disp < 1e-1, "Displacement too large (singular matrix?)"
    print("All checks passed!")

    return u_full, nodes, elements


def test_shape_functions():
    """Test shape functions and Jacobian."""
    sf = ShapeFunctions()

    # Triangle
    N = sf.triangle_linear(0.3, 0.2)
    assert abs(N.sum() - 1.0) < 1e-10, "Triangle N sum != 1"

    dN_dxi, dN_deta = sf.triangle_linear_derivatives()
    assert len(dN_dxi) == 3

    # Quad
    Nq = sf.quad_bilinear(0.5, -0.5)
    assert abs(Nq.sum() - 1.0) < 1e-10, "Quad N sum != 1"

    dN_dxi_fn, dN_deta_fn = sf.quad_bilinear_derivatives()
    dN_dxi = dN_dxi_fn(0.5, -0.5)
    dN_deta = dN_deta_fn(0.5, -0.5)
    assert len(dN_dxi) == 4

    print("Shape functions: OK")


def test_material():
    """Test Hooke 2D."""
    m = MaterialModel(E=200e9, nu=0.25)

    D_ps = m.D_matrix(AnalysisType.PLANE_STRESS)
    D_pe = m.D_matrix(AnalysisType.PLANE_STRAIN)

    assert D_ps.shape == (3, 3)
    assert D_pe.shape == (3, 3)

    # Symmetry check
    assert np.allclose(D_ps, D_ps.T)
    assert np.allclose(D_pe, D_pe.T)

    # Strain → stress
    strain = np.array([0.001, -0.0003, 0.0])
    stress = m.stress_from_strain(strain, AnalysisType.PLANE_STRESS)
    assert stress.shape == (3,)

    # Von Mises
    vm = MaterialModel.von_mises_stress(np.array([100e6, 50e6, 20e6]))
    assert vm > 0

    print("Material model: OK")


def test_element_stiffness():
    """Test element stiffness matrix."""
    m = MaterialModel(E=210e9, nu=0.3, thickness=0.01)
    K_builder = ElementStiffness(m, AnalysisType.PLANE_STRESS)

    # Quad element: unit square
    coords_quad = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [1.0, 1.0],
        [0.0, 1.0],
    ])
    K_e = K_builder.quad(coords_quad, order="2x2")
    assert K_e.shape == (8, 8)
    assert np.allclose(K_e, K_e.T), "K_e not symmetric"

    # Triangle
    coords_tri = np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
    ])
    K_e_tri = K_builder.triangle(coords_tri, order="3pt")
    assert K_e_tri.shape == (6, 6)
    assert np.allclose(K_e_tri, K_e_tri.T), "K_e_tri not symmetric"

    print("Element stiffness: OK")


def test_assembly():
    """Test global assembly."""
    nodes = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    elements = [[1, 2, 3, 4]]  # 1-based

    assembler = GlobalAssembler(nodes, elements)
    assert assembler.n_dof == 8

    # DOFs
    dofs = assembler.get_element_dofs(0)
    assert len(dofs) == 8
    assert list(dofs) == [0, 1, 2, 3, 4, 5, 6, 7]

    # Force vector
    F = assembler.build_force_vector([NodalForce(node_id=1, dof="fx", value=100.0)])
    assert F[2] == 100.0

    print("Assembly: OK")


if __name__ == "__main__":
    print("=" * 50)
    print("FEA Core Module Tests")
    print("=" * 50)

    test_shape_functions()
    test_material()
    test_element_stiffness()
    test_assembly()
    print()
    test_cantilever_beam()

    print()
    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)
