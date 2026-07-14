"""
onboarding/prompts.py

기능 1의 유일한 LLM 사용처: 하루 업무 자유서술(day_narrative)에서 **반복 업무 후보**를 뽑는 프롬프트.
값을 확정하지 않고 초안만 만든다 — 빈도/정형성/소요시간/민감정보는 사용자가 후속 질문으로
확인·수정하는 흐름을 전제로 한 best-guess다 (SPEC 4.1 "언급된 업무마다 추가 확인").
"""

_EXTRACT_POLICY = """
- 하루 일과 서술에서 '반복적으로 돌아오는 업무'만 뽑는다. 일회성 사건(예: 오늘 있었던 회식)은 제외.
- 하나의 업무를 통째로 뭉치지 말고, 성격이 다르면 (예: 데이터 취합 vs 해석 코멘트) 나눠서 뽑는다.
- 각 후보의 빈도/정형성/소요시간/민감정보는 서술에 단서가 있으면 반영하고, 없으면 합리적으로
  추정하되 needs_confirmation=true로 표시한다 (사용자 확인 대상임).
- 민감정보(매출·단가·개인정보 등)가 관련될 여지가 있으면 contains_sensitive_info=true로 보수적으로 잡는다.
"""


def build_extract_tasks_prompt(day_narrative: str, work_categories: list[str]) -> str:
    categories = ", ".join(work_categories) or "(미지정)"
    return f"""당신은 중간관리자의 하루 업무 서술에서 반복 업무를 정리해주는 조수다.
{_EXTRACT_POLICY}

## 팀 담당 업무 카테고리
{categories}

## 하루 업무 서술
{day_narrative}

## 출력 지시
tasks 배열로 반복 업무 후보를 뽑는다. 각 후보는:
- title: 업무 이름 (짧고 명확하게)
- frequency: 매일 / 주 1회 이상 / 월 1~3회 / 월 1회 이하 중 추정값
- is_standardized: 매번 비슷한 방식이면 true, 그때그때 판단이 필요하면 false
- avg_time_minutes: 1회 소요시간 추정(분)
- contains_sensitive_info: 민감정보 관련 여지가 있으면 true
- current_method: 서술에 나온 현재 처리 방식 (없으면 추정)
- needs_confirmation: 위 값이 서술의 직접 근거 없이 추정된 것이면 true
"""
