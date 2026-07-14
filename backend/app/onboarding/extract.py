"""
onboarding/extract.py

하루 업무 자유서술 → 반복 업무 후보 추출 (Gemini). SPEC 4.1의 "하루를 시간순으로 나열하면
언급된 업무마다 추가 확인" 흐름에서 '언급된 업무를 뽑는' 단계를 담당한다.

여기서 뽑힌 후보는 **확정값이 아니다** — needs_confirmation으로 표시된 필드는 프론트가
후속 질문으로 확인받은 뒤 `InterviewAnswers.task_details`로 되돌려 보내는 것을 전제로 한다.
"""

from google import genai
from pydantic import BaseModel, Field

from app.core.gemini import generate_structured
from app.onboarding.prompts import build_extract_tasks_prompt


class TaskCandidate(BaseModel):
    title: str
    frequency: str
    is_standardized: bool
    # Gemini response_schema는 exclusiveMinimum(=pydantic gt)을 허용하지 않으므로 수치 제약을 걸지 않는다.
    # (이 값은 LLM 추정치이고, 사용자가 후속 질문으로 확정한다.)
    avg_time_minutes: float = Field(description="1회 소요시간 추정(분). 양수")
    contains_sensitive_info: bool = False
    current_method: str = ""
    needs_confirmation: bool = True


class TaskCandidates(BaseModel):
    tasks: list[TaskCandidate] = Field(default_factory=list)


def extract_task_candidates(
    client: genai.Client,
    day_narrative: str,
    work_categories: list[str] | None = None,
) -> list[TaskCandidate]:
    """자유서술에서 반복 업무 후보를 뽑는다. 서술이 비면 빈 리스트를 반환한다."""
    if not day_narrative.strip():
        return []
    prompt = build_extract_tasks_prompt(day_narrative, work_categories or [])
    result = generate_structured(client, prompt, TaskCandidates)
    return result.tasks
