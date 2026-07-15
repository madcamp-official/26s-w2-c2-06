"""기능 1(온보딩 인터뷰) 동작 검증. Gemini는 conftest의 FakeClient로 대체한다."""

import json
from pathlib import Path

from app.contracts.onboarding import AiAdoptionLevel, OnboardingData
from app.onboarding import InterviewAnswers, build_onboarding, get_interview_script
from app.onboarding.extract import TaskCandidate, TaskCandidates, extract_task_candidates
from app.onboarding.questions import QuestionType
from tests.conftest import FakeClient

FIXTURES_DIR = Path(__file__).parent.parent / "app" / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def test_interview_script_has_four_spec_parts():
    parts = get_interview_script()
    keys = [p.key for p in parts]
    # QA_amendments 1절 — 팀원 태깅은 더 이상 독립 파트가 아니라 "기본 정보" 안의 팀원 표로
    # 편입됐다(팀장 본인을 기본 행으로 포함, 행 추가 가능).
    assert keys == [
        "basic_info",
        "ai_adoption",
        "org_environment",
        "repetitive_tasks",
    ]
    # 반복 업무 파트는 추상적 질문이 아니라 '하루를 시간순으로' 자유서술로 유도한다 (SPEC 4.1)
    task_part = next(p for p in parts if p.key == "repetitive_tasks")
    assert task_part.questions[0].type == QuestionType.TASK_NARRATIVE

    basic_info = next(p for p in parts if p.key == "basic_info")
    basic_info_keys = [q.key for q in basic_info.questions]
    assert "member_tags" in basic_info_keys
    assert "ai_usage_variance" in basic_info_keys

    org_environment = next(p for p in parts if p.key == "org_environment")
    assert "erp_data_integrated" in [q.key for q in org_environment.questions]


def test_build_onboarding_from_confirmed_answers_maps_org_environment():
    answers = InterviewAnswers.model_validate(_load("interview_answers_marketing.json"))
    onboarding = build_onboarding(answers)

    assert isinstance(onboarding, OnboardingData)
    assert onboarding.team_size == 8
    assert onboarding.ai_adoption_level == AiAdoptionLevel.OCCASIONAL
    # 지정 도구 "없음" 선택지는 실제 도구가 아니므로 걸러진다
    assert onboarding.org_environment.designated_ai_tools == []
    assert onboarding.org_environment.has_ai_guideline is False
    assert onboarding.org_environment.external_ai_allowed is True
    # 확정된 반복 업무가 그대로 넘어온다 (민감정보 플래그 포함)
    assert len(onboarding.repetitive_tasks) == 7
    budget = next(t for t in onboarding.repetitive_tasks if "예산" in t.title)
    assert budget.contains_sensitive_info is True


def test_build_onboarding_extracts_tasks_from_narrative_when_not_itemized():
    fake = FakeClient(
        TaskCandidates(
            tasks=[
                TaskCandidate(
                    title="주간 보고서 작성",
                    frequency="주 1회 이상",
                    is_standardized=True,
                    avg_time_minutes=120,
                    contains_sensitive_info=True,
                    current_method="엑셀 수기",
                    needs_confirmation=True,
                )
            ]
        )
    )
    answers = InterviewAnswers(
        team_size=5,
        day_narrative="오전에 데이터를 모아 주간 보고서를 쓰고 오후에 회의를 한다",
    )
    onboarding = build_onboarding(answers, client=fake)
    assert len(onboarding.repetitive_tasks) == 1
    assert onboarding.repetitive_tasks[0].title == "주간 보고서 작성"


def test_extract_task_candidates_returns_empty_for_blank_narrative():
    fake = FakeClient(TaskCandidates(tasks=[]))
    assert extract_task_candidates(fake, "   ") == []
    # 빈 서술이면 LLM을 아예 호출하지 않는다
    assert fake.models.calls == []


def test_confirmed_task_details_take_priority_over_narrative():
    fake = FakeClient(TaskCandidates(tasks=[TaskCandidate(
        title="LLM이 뽑은 것", frequency="매일", is_standardized=False, avg_time_minutes=10
    )]))
    answers = InterviewAnswers.model_validate(_load("interview_answers_marketing.json"))
    answers.day_narrative = "이 서술은 무시돼야 한다"
    onboarding = build_onboarding(answers, client=fake)
    # task_details가 있으므로 LLM 추출을 하지 않는다
    assert fake.models.calls == []
    assert len(onboarding.repetitive_tasks) == 7
