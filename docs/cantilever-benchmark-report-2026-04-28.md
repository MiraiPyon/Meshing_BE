# Cantilever Benchmark Report - 2026-04-28

Overall status: **PASS**

This benchmark reproduces the cantilever problem from Section IV of the reference paper using the project's supported T3/Q4 elements. The paper uses LST/T6 elements, so this report compares the same geometry, material, load, and analytical Euler-Bernoulli solution, not the same element family.

## Input

- Load: `10000 N` downward at the free-edge node closest to the neutral axis
- Length: `10.0 m`
- Height: `1.0 m`
- Thickness: `1.0 m`
- Young modulus: `2.000e+11 Pa`
- Poisson ratio: `0.3`
- Exact neutral-axis deflection: `v(x)=P*x^2*(3L-x)/(6EI)`, `I=t*h^3/12`
- Exact tip deflection: `-2.000000e-04 m`
- Coordinate convention: paper load/support orientation is mirrored to clamp at `x=0` and apply the end load at `x=L`; the beam problem and analytical deflection are equivalent.

## Reference Mapping

- Section IV uses LST/T6 triangular elements with 4-element and 10-element meshes.
- This project requirement supports T3 and Q4 only, so the benchmark keeps the same Section IV geometry, material, load, and analytical curve while validating supported T3/Q4 elements.
- `Q4-4x2` and `Q4-10x2` mirror the paper's coarse/fine division controls; `Q4-20x4` is the refined accuracy gate; `T3-Delaunay-0.75` verifies the Delaunay/FEA path on the same beam.

CSV point-by-point evidence: `cantilever-benchmark-2026-04-28.csv`

## Summary

| Case | Element | Nodes | Elements | DOF | Tip uy (m) | Exact tip (m) | Rel. error | Force balance | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Q4-4x2 | Q4 | 15 | 8 | 30 | -5.847051e-05 | -2.000000e-04 | 70.76% | 3.143e-12 | PASS |
| Q4-10x2 | Q4 | 33 | 20 | 66 | -1.422238e-04 | -2.000000e-04 | 28.89% | 6.490e-13 | PASS |
| Q4-20x4 | Q4 | 105 | 80 | 210 | -1.820700e-04 | -2.000000e-04 | 8.97% | 3.463e-12 | PASS |
| T3-Delaunay-0.75 | T3 | 50 | 66 | 100 | -1.256307e-04 | -2.000000e-04 | 37.18% | 1.089e-12 | PASS |

## Accuracy Notes

- Q4 convergence gate: `PASS`. Tip relative error decreases as the mesh is refined.
- Refined Q4 gate (`<= 12%` tip relative error): `PASS`.
- T3 Delaunay gate checks solver validity, CCW triangle orientation, and force equilibrium. Its accuracy is reported as evidence but not forced to match the paper's LST/T6 curve.
- A lower error is expected with denser meshes or a higher-order LST/T6 implementation, which is outside the current T3/Q4 project scope.
