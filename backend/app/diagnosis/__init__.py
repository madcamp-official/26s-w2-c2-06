"""기능 2 — AX 성숙도 진단 및 목표 설정 (SPEC 4.2).

온보딩 결과 → 성숙도 진단(레이더 5축) + 목표 정의서.
"""

from app.diagnosis.service import DiagnosisResult, diagnose_and_set_goal

__all__ = ["diagnose_and_set_goal", "DiagnosisResult"]
