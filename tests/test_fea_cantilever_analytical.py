import numpy as np

from app.engines.fea.assembly import BoundaryCondition, GlobalAssembler, LineLoad, NodalForce
from app.engines.fea.cantilever_analytical import (
    euler_bernoulli_tip_deflection_point_load,
    evaluate_cantilever_benchmark,
    resultant_vertical_load,
    timoshenko_tip_deflection_point_load,
)
from app.engines.fea.material import AnalysisType, MaterialModel
from app.engines.fea.solver import FEASolver, SolverConfig


# Section IV benchmark data from editor_in_chief.pdf
SECTION_IV_LOAD_N = 10_000.0
SECTION_IV_HEIGHT_M = 1.0
SECTION_IV_LENGTH_M = 10.0
SECTION_IV_POISSON = 0.3
SECTION_IV_YOUNG_MODULUS_PA = 2.0e11
SECTION_IV_THICKNESS_M = 1.0


def _build_cantilever_mesh(nx: int, ny: int, length: float = 1.0, height: float = 0.2):
    x_nodes = np.linspace(0.0, length, nx + 1)
    y_nodes = np.linspace(0.0, height, ny + 1)

    nodes = np.array(
        [[x_nodes[i], y_nodes[j]] for i in range(nx + 1) for j in range(ny + 1)],
        dtype=float,
    )

    elements = []
    for i in range(nx):
        for j in range(ny):
            n1 = i * (ny + 1) + j + 1
            n2 = (i + 1) * (ny + 1) + j + 1
            n3 = (i + 1) * (ny + 1) + j + 2
            n4 = i * (ny + 1) + j + 2
            elements.append([n1, n2, n3, n4])

    return nodes, elements


def _cantilever_solver(
    nx: int = 10,
    ny: int = 2,
    length: float = 1.0,
    height: float = 0.2,
    young_modulus: float = 210e9,
    poisson: float = 0.3,
    thickness: float = 0.01,
):
    nodes, elements = _build_cantilever_mesh(nx=nx, ny=ny, length=length, height=height)
    solver = FEASolver(
        nodes=nodes,
        elements=elements,
        material=MaterialModel(E=young_modulus, nu=poisson, thickness=thickness),
        analysis_type=AnalysisType.PLANE_STRESS,
        config=SolverConfig(integration_order="2x2", bc_method="elimination"),
    )

    left_nodes = list(range(ny + 1))
    bc_list = []
    for n in left_nodes:
        bc_list.append(BoundaryCondition(node_id=n, dof="ux", value=0.0))
        bc_list.append(BoundaryCondition(node_id=n, dof="uy", value=0.0))

    right_nodes = [nx * (ny + 1) + j for j in range(ny + 1)]

    return nodes, solver, bc_list, right_nodes


def _solve_tip_point_load_case(
    nx: int,
    ny: int,
    length: float,
    height: float,
    young_modulus: float,
    poisson: float,
    thickness: float,
    point_load_y: float,
):
    nodes, solver, bc_list, right_nodes = _cantilever_solver(
        nx=nx,
        ny=ny,
        length=length,
        height=height,
        young_modulus=young_modulus,
        poisson=poisson,
        thickness=thickness,
    )

    tip_node = right_nodes[len(right_nodes) // 2]
    nodal_forces = [NodalForce(node_id=tip_node, dof="fy", value=point_load_y)]

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=nodal_forces)
    assert success, message

    reactions = solver.assembler.recover_reactions(
        solver._K_full,
        u_nodes,
        bc_list,
        F_external=solver._F,
    )

    benchmark = evaluate_cantilever_benchmark(
        nodes=nodes,
        displacements=u_nodes,
        material=solver.material,
        bc_list=bc_list,
        nodal_forces=nodal_forces,
        line_loads=None,
        reactions=reactions,
    )

    return float(u_nodes[tip_node, 1]), benchmark


def test_point_load_analytical_formulas_match_hand_calculation():
    E = 210e9
    nu = 0.3
    t = 0.01
    h = 0.2
    L = 1.0
    P = -1000.0

    inertia = t * h**3 / 12.0
    A = t * h
    G = E / (2.0 * (1.0 + nu))

    delta_euler = euler_bernoulli_tip_deflection_point_load(P, L, E, inertia)
    delta_timo = timoshenko_tip_deflection_point_load(P, L, E, inertia, G, A)

    expected_euler = P * L**3 / (3.0 * E * inertia)
    expected_timo = expected_euler + P * L / ((5.0 / 6.0) * G * A)

    assert np.isclose(delta_euler, expected_euler)
    assert np.isclose(delta_timo, expected_timo)
    assert abs(delta_timo) > abs(delta_euler)


def test_constant_edge_traction_and_equivalent_nodal_load_resultant_match():
    nodes = np.array([[1.0, 0.0], [1.0, 0.2]], dtype=float)
    line_loads = [LineLoad(start_node=0, end_node=1, dof="ty", value=-5000.0)]

    total_vertical = resultant_vertical_load(nodes, nodal_forces=None, line_loads=line_loads)
    assert np.isclose(total_vertical, -1000.0)

    assembler = GlobalAssembler(nodes=nodes, elements=[])
    F = np.zeros(4)
    F = assembler.add_line_load(F, line_loads)

    # Equivalent nodal loads for uniform traction on a 2-node edge: p*L/2 at each node.
    assert np.isclose(F[1], -500.0)
    assert np.isclose(F[3], -500.0)
    assert np.isclose(F[1] + F[3], -1000.0)


def test_cantilever_benchmark_reports_force_balance_and_expected_ratio():
    nodes, solver, bc_list, right_nodes = _cantilever_solver(nx=10, ny=2)

    total_load = 1000.0
    nodal_forces = [
        NodalForce(node_id=n, dof="fy", value=-total_load / len(right_nodes))
        for n in right_nodes
    ]

    u_nodes, success, message = solver.run(bc_list=bc_list, nodal_forces=nodal_forces)
    assert success, message

    reactions = solver.assembler.recover_reactions(
        solver._K_full,
        u_nodes,
        bc_list,
        F_external=solver._F,
    )

    benchmark = evaluate_cantilever_benchmark(
        nodes=nodes,
        displacements=u_nodes,
        material=solver.material,
        bc_list=bc_list,
        nodal_forces=nodal_forces,
        line_loads=None,
        reactions=reactions,
    )

    assert benchmark is not None
    assert benchmark["force_balance_error"] is not None
    assert benchmark["force_balance_error"] < 0.01

    # Benchmark uses average tip deflection on free edge.
    # For this setup, FE tip response should stay in the same order as beam theory.
    ratio = abs(float(benchmark["ratio_to_euler"]))
    assert 0.8 < ratio < 1.1


def test_distributed_end_traction_and_nodal_end_load_give_close_tip_response():
    nodes, solver_nodal, bc_list, right_nodes = _cantilever_solver(nx=10, ny=2)

    total_load = 1000.0

    nodal_forces = [
        NodalForce(node_id=n, dof="fy", value=-total_load / len(right_nodes))
        for n in right_nodes
    ]
    u_nodal, success_nodal, msg_nodal = solver_nodal.run(
        bc_list=bc_list,
        nodal_forces=nodal_forces,
    )
    assert success_nodal, msg_nodal

    # Build end-edge line loads on x = L with p = P / h from the notes.
    y_sorted_right = sorted(right_nodes, key=lambda n: nodes[n, 1])
    beam_height = float(nodes[y_sorted_right[-1], 1] - nodes[y_sorted_right[0], 1])
    traction = -total_load / beam_height
    line_loads = [
        LineLoad(start_node=y_sorted_right[i], end_node=y_sorted_right[i + 1], dof="ty", value=traction)
        for i in range(len(y_sorted_right) - 1)
    ]

    nodes2, solver_line, bc_list2, right_nodes2 = _cantilever_solver(nx=10, ny=2)
    u_line, success_line, msg_line = solver_line.run(
        bc_list=bc_list2,
        nodal_forces=[],
        line_loads=line_loads,
    )
    assert success_line, msg_line

    tip_avg_nodal = float(np.mean(u_nodal[right_nodes, 1]))
    tip_avg_line = float(np.mean(u_line[right_nodes2, 1]))

    assert tip_avg_nodal < 0.0
    assert tip_avg_line < 0.0

    # The two load representations should be close for the same resultant load.
    assert np.isclose(tip_avg_line, tip_avg_nodal, rtol=0.15)


def test_section_iv_benchmark_fine_mesh_is_more_accurate_than_coarse_mesh():
    coarse_tip, coarse_benchmark = _solve_tip_point_load_case(
        nx=4,
        ny=2,
        length=SECTION_IV_LENGTH_M,
        height=SECTION_IV_HEIGHT_M,
        young_modulus=SECTION_IV_YOUNG_MODULUS_PA,
        poisson=SECTION_IV_POISSON,
        thickness=SECTION_IV_THICKNESS_M,
        point_load_y=-SECTION_IV_LOAD_N,
    )
    fine_tip, fine_benchmark = _solve_tip_point_load_case(
        nx=10,
        ny=2,
        length=SECTION_IV_LENGTH_M,
        height=SECTION_IV_HEIGHT_M,
        young_modulus=SECTION_IV_YOUNG_MODULUS_PA,
        poisson=SECTION_IV_POISSON,
        thickness=SECTION_IV_THICKNESS_M,
        point_load_y=-SECTION_IV_LOAD_N,
    )

    assert coarse_benchmark is not None
    assert fine_benchmark is not None
    assert coarse_benchmark["force_balance_error"] < 1e-8
    assert fine_benchmark["force_balance_error"] < 1e-8

    inertia = SECTION_IV_THICKNESS_M * SECTION_IV_HEIGHT_M**3 / 12.0
    exact_tip = euler_bernoulli_tip_deflection_point_load(
        -SECTION_IV_LOAD_N,
        SECTION_IV_LENGTH_M,
        SECTION_IV_YOUNG_MODULUS_PA,
        inertia,
    )

    coarse_error = abs((coarse_tip - exact_tip) / exact_tip)
    fine_error = abs((fine_tip - exact_tip) / exact_tip)

    # Section V reports the finer discretization tracks analytical values better.
    assert fine_error < coarse_error
    assert fine_error < 0.35
