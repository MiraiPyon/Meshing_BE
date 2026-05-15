"""
Material Models – Định luật Hooke 2D.
Hỗ trợ: plane stress và plane strain.
"""

import numpy as np
from enum import Enum


class AnalysisType(str, Enum):
    PLANE_STRESS = "plane_stress"
    PLANE_STRAIN = "plane_strain"


class MaterialModel:
    """
    Material model với định luật Hooke 2D.

    Stress: σ = D · ε

    PLANE STRESS (thickness nhỏ):
        D = E/(1-ν²) · | 1   ν    0    |
                          | ν   1    0    |
                          | 0   0  (1-ν)/2 |

    PLANE STRAIN (thickness lớn, ε_z = 0):
        D = E/((1+ν)(1-2ν)) · | 1-ν   ν    0    |
                               |  ν   1-ν   0    |
                               |  0    0  1-2ν/2 |
    """

    def __init__(self, E: float, nu: float, thickness: float = 1.0):
        """
        Args:
            E:         Young's modulus (Pa)
            nu:        Poisson's ratio [0, 0.5)
            thickness: Độ dày cho plane stress (m)
        """
        if not (0 <= nu < 0.5):
            raise ValueError(f"Poisson's ratio must be in [0, 0.5), got {nu}")
        if E <= 0:
            raise ValueError(f"Young's modulus must be positive, got {E}")

        self.E = E
        self.nu = nu
        self.thickness = thickness

    def D_matrix(self, analysis_type: AnalysisType = AnalysisType.PLANE_STRESS) -> np.ndarray:
        """
        Xây dựng ma trận độ cứng vật liệu D (3×3).

        Args:
            analysis_type: "plane_stress" hoặc "plane_strain"

        Returns:
            D: (3, 3) constitutive matrix
        """
        E = self.E
        nu = self.nu

        if analysis_type == AnalysisType.PLANE_STRESS:
            factor = E / (1.0 - nu ** 2)
            D = np.array([
                [1.0,   nu,   0.0          ],
                [nu,   1.0,   0.0          ],
                [0.0,  0.0,   (1.0 - nu) / 2.0],
            ]) * factor

        else:  # plane strain
            factor = E / ((1.0 + nu) * (1.0 - 2.0 * nu))
            D = np.array([
                [1.0 - nu,   nu,       0.0      ],
                [nu,       1.0 - nu,    0.0      ],
                [0.0,       0.0,   (1.0 - 2.0 * nu) / 2.0],
            ]) * factor

        return D

    def stress_from_strain(self, strain: np.ndarray, analysis_type: AnalysisType = AnalysisType.PLANE_STRESS) -> np.ndarray:
        """
        Tính stress từ strain: σ = D · ε

        Args:
            strain: (3,) – [exx, eyy, gxy]
            analysis_type: "plane_stress" hoặc "plane_strain"

        Returns:
            stress: (3,) – [sxx, syy, txy]
        """
        D = self.D_matrix(analysis_type)
        return D @ np.asarray(strain)

    def strain_from_stress(self, stress: np.ndarray, analysis_type: AnalysisType = AnalysisType.PLANE_STRESS) -> np.ndarray:
        """
        Tính strain từ stress: ε = D^{-1} · σ

        Args:
            stress: (3,) – [sxx, syy, txy]
            analysis_type: "plane_stress" hoặc "plane_strain"

        Returns:
            strain: (3,) – [exx, eyy, gxy]
        """
        D = self.D_matrix(analysis_type)
        return np.linalg.solve(D, np.asarray(stress))

    # ---- Von Mises stress ----

    @staticmethod
    def von_mises_stress(stress: np.ndarray) -> float:
        """
        Tính Von Mises equivalent stress.

        σ_vm = sqrt( σ₁² + σ₂² - σ₁·σ₂ + 3·τ_xy² )

        Cho 2D: σ₁, σ₂ là principal stresses.

        Args:
            stress: (3,) – [sxx, syy, txy]

        Returns:
            σ_vm: scalar
        """
        sxx, syy, txy = stress[0], stress[1], stress[2]

        # Tính trực tiếp từ ứng suất Cartesian
        sigma_vm = np.sqrt(sxx ** 2 + syy ** 2 - sxx * syy + 3.0 * txy ** 2)
        return float(sigma_vm)

    # ---- Common materials factory ----

    @staticmethod
    def steel(thickness: float = 1.0) -> "MaterialModel":
        """Thép: E = 210 GPa, ν = 0.3"""
        return MaterialModel(E=210e9, nu=0.3, thickness=thickness)

    @staticmethod
    def aluminum(thickness: float = 1.0) -> "MaterialModel":
        """Nhôm: E = 70 GPa, ν = 0.33"""
        return MaterialModel(E=70e9, nu=0.33, thickness=thickness)

    @staticmethod
    def titanium(thickness: float = 1.0) -> "MaterialModel":
        """Titanium: E = 110 GPa, ν = 0.34"""
        return MaterialModel(E=110e9, nu=0.34, thickness=thickness)

    @staticmethod
    def concrete(thickness: float = 1.0) -> "MaterialModel":
        """Bê tông: E = 30 GPa, ν = 0.2"""
        return MaterialModel(E=30e9, nu=0.2, thickness=thickness)
