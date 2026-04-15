import numpy as np
import scipy.sparse as sp

from app.engines.fea.assembly import BoundaryCondition, GlobalAssembler


def _dof_to_bc(dof: int, value: float) -> BoundaryCondition:
    return BoundaryCondition(node_id=dof // 2, dof="ux" if dof % 2 == 0 else "uy", value=float(value))


def _reference_elimination(K: np.ndarray, F: np.ndarray, fixed: np.ndarray, u_fixed: np.ndarray):
    n = K.shape[0]
    fixed_set = set(int(i) for i in fixed)
    free = np.array([i for i in range(n) if i not in fixed_set], dtype=int)
    K_ff = K[np.ix_(free, free)]
    F_f = (F - K[:, fixed] @ u_fixed)[free]
    return K_ff, F_f, free


def test_randomized_elimination_matches_reference_many_cases():
    rng = np.random.default_rng(20260415)

    for _ in range(40):
        n_nodes = int(rng.integers(2, 6))
        n_dof = 2 * n_nodes

        A = rng.normal(size=(n_dof, n_dof))
        K = A.T @ A + np.eye(n_dof) * (1.0 + rng.random())
        F = rng.normal(size=n_dof)

        n_fixed = int(rng.integers(1, n_dof))
        fixed = np.array(sorted(rng.choice(n_dof, size=n_fixed, replace=False)), dtype=int)
        u_fixed = rng.normal(scale=1e-3, size=n_fixed)

        nodes = np.column_stack([np.arange(n_nodes, dtype=float), np.zeros(n_nodes)])
        assembler = GlobalAssembler(nodes, elements=[])

        bc_list = [_dof_to_bc(int(d), float(v)) for d, v in zip(fixed, u_fixed, strict=True)]
        K_red, F_red, free_dofs, fixed_dofs = assembler.apply_dirichlet_bc(
            sp.csr_matrix(K),
            F,
            bc_list,
            method="elimination",
        )

        K_ref, F_ref, free_ref = _reference_elimination(K, F, fixed, u_fixed)

        np.testing.assert_allclose(K_red.toarray(), K_ref, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(F_red, F_ref, rtol=1e-12, atol=1e-12)
        assert free_dofs == list(free_ref)
        assert fixed_dofs == set(fixed.tolist())


def test_randomized_penalty_solution_tracks_elimination_solution():
    rng = np.random.default_rng(20260416)

    for _ in range(25):
        n_nodes = int(rng.integers(2, 5))
        n_dof = 2 * n_nodes

        A = rng.normal(size=(n_dof, n_dof))
        K = A.T @ A + np.eye(n_dof) * (5.0 + rng.random())
        F = rng.normal(size=n_dof)

        n_fixed = int(rng.integers(1, n_dof))
        fixed = np.array(sorted(rng.choice(n_dof, size=n_fixed, replace=False)), dtype=int)
        u_fixed = rng.normal(scale=1e-4, size=n_fixed)

        nodes = np.column_stack([np.arange(n_nodes, dtype=float), np.zeros(n_nodes)])
        assembler = GlobalAssembler(nodes, elements=[])
        bc_list = [_dof_to_bc(int(d), float(v)) for d, v in zip(fixed, u_fixed, strict=True)]

        # Elimination reference full displacement
        K_red, F_red, free_dofs, _ = assembler.apply_dirichlet_bc(
            sp.csr_matrix(K),
            F,
            bc_list,
            method="elimination",
        )
        u_elim = np.zeros(n_dof)
        if len(free_dofs) > 0:
            u_elim[np.array(free_dofs)] = np.linalg.solve(K_red.toarray(), F_red)
        for d, v in zip(fixed, u_fixed, strict=True):
            u_elim[d] = v

        # Penalty solution
        K_pen, F_pen = assembler.apply_dirichlet_bc(
            sp.csr_matrix(K),
            F,
            bc_list,
            method="penalty",
            penalty=1e14,
        )
        u_pen = np.linalg.solve(K_pen.toarray(), F_pen)

        np.testing.assert_allclose(u_pen, u_elim, rtol=2e-6, atol=1e-9)
