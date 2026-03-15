"""Plan 2 Validation Framework (MF-G).

Five validation blocks:
1. Face validity — golden set expectations
2. Distribution sanity — structural alerts per run
3. Sensitivity analysis — weight/threshold perturbation
4. Evidence-weight sanity — top ranks vs evidence quality
5. Regression fixtures — deterministic snapshot tests
"""

from q3_quant_engine.thesis.validation.face_validity import (
    GoldenCase,
    FaceValidityResult,
    check_face_validity,
)
from q3_quant_engine.thesis.validation.distribution import (
    DistributionAlert,
    check_distribution_sanity,
)
from q3_quant_engine.thesis.validation.sensitivity import (
    SensitivityResult,
    run_sensitivity_analysis,
)
from q3_quant_engine.thesis.validation.evidence_sanity import (
    EvidenceSanityResult,
    check_evidence_sanity,
)

__all__ = [
    "GoldenCase",
    "FaceValidityResult",
    "check_face_validity",
    "DistributionAlert",
    "check_distribution_sanity",
    "SensitivityResult",
    "run_sensitivity_analysis",
    "EvidenceSanityResult",
    "check_evidence_sanity",
]
