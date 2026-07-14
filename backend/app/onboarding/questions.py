"""
onboarding/questions.py

기능 1(온보딩 인터뷰)의 질문 대본. SPEC 4.1 "질문 설계 원칙"을 코드로 고정한다:
추상적으로 묻지 않고("자동화할 업무를 입력하세요" ❌) 구체적으로 답하기 쉽게 묻는다
("하루 업무를 시간순으로 알려주세요" ✅).

이 대본은 프론트가 인터뷰 화면을 렌더링하는 데 쓰는 **정적 데이터**다 (LLM 미사용).
반복 업무 파트의 자유서술은 이후 `extract.py`가 후보 업무로 구조화한다.
"""

from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    # 반복 업무 파트: 자유서술(시간순 나열) 후 언급된 업무마다 후속 질문을 반복 수집
    TASK_NARRATIVE = "task_narrative"


class Question(BaseModel):
    key: str
    prompt: str
    type: QuestionType
    choices: list[str] = Field(default_factory=list)
    help_text: str = ""
    optional: bool = False


class InterviewPart(BaseModel):
    key: str
    title: str
    questions: list[Question]


# SPEC 4.1 "AI 활용 수준" 4단계 — contracts.onboarding.AiAdoptionLevel과 문구 일치
_AI_LEVELS = ["안 씀", "궁금해서 써봄", "가끔 필요할 때 씀", "업무에 적극 활용"]

# 반복 업무 파트에서 자유서술로 나온 업무마다 반복해서 묻는 후속 질문 (SPEC 4.1 "반복 업무 상세")
TASK_FOLLOWUP_QUESTIONS: list[Question] = [
    Question(
        key="frequency",
        prompt="이 업무는 얼마나 자주 하시나요?",
        type=QuestionType.SINGLE_CHOICE,
        choices=["매일", "주 1회 이상", "월 1~3회", "월 1회 이하"],
    ),
    Question(
        key="is_standardized",
        prompt="이 업무는 매번 비슷한 방식·형식으로 처리되나요?",
        type=QuestionType.BOOLEAN,
        help_text="'네'면 정형 업무, '아니오'면 그때그때 판단이 필요한 비정형 업무예요.",
    ),
    Question(
        key="avg_time_minutes",
        prompt="한 번 할 때 평균 몇 분 정도 걸리나요?",
        type=QuestionType.NUMBER,
    ),
    Question(
        key="contains_sensitive_info",
        prompt="이 업무에 매출·단가·개인정보 같은 민감한 정보가 들어가나요?",
        type=QuestionType.BOOLEAN,
        help_text="민감정보가 있으면 외부 AI 도구 사용을 보류하고 경고해드려요 (SPEC 2.6·4.4).",
    ),
    Question(
        key="current_method",
        prompt="지금은 이 업무를 어떤 방식으로 처리하고 계신가요?",
        type=QuestionType.TEXT,
        help_text="예: '엑셀 수기 취합 후 워드로 작성'",
    ),
]

INTERVIEW_SCRIPT: list[InterviewPart] = [
    InterviewPart(
        key="basic_info",
        title="기본 정보",
        questions=[
            Question(key="industry", prompt="어떤 업종에서 일하시나요?", type=QuestionType.TEXT),
            Question(
                key="team_size",
                prompt="팀장님을 포함해 팀원은 몇 명인가요?",
                type=QuestionType.NUMBER,
            ),
            Question(
                key="work_categories",
                prompt="팀이 주로 담당하는 업무를 골라주세요.",
                type=QuestionType.MULTI_CHOICE,
                choices=[
                    "마케팅/콘텐츠",
                    "영업/고객대응",
                    "기획/전략",
                    "데이터/분석",
                    "구매/총무",
                    "개발/기술",
                    "인사/교육",
                    "기타",
                ],
            ),
        ],
    ),
    InterviewPart(
        key="ai_adoption",
        title="AI 활용 수준",
        questions=[
            Question(
                key="ai_adoption_level",
                prompt="팀장님은 평소 업무에 AI를 어느 정도 쓰시나요?",
                type=QuestionType.SINGLE_CHOICE,
                choices=_AI_LEVELS,
            ),
        ],
    ),
    InterviewPart(
        key="org_environment",
        title="조직 환경",
        questions=[
            Question(
                key="has_ai_guideline",
                prompt="회사에 AI 사용 가이드라인이 있나요?",
                type=QuestionType.BOOLEAN,
            ),
            Question(
                key="designated_ai_tools",
                prompt="사내에서 공식으로 지정한 AI 도구가 있나요? 있다면 적어주세요.",
                type=QuestionType.MULTI_CHOICE,
                choices=["Copilot", "ChatGPT Enterprise", "Gemini", "사내 자체 도구", "없음"],
                optional=True,
            ),
            Question(
                key="external_ai_allowed",
                prompt="개인 ChatGPT 같은 외부 AI 도구를 업무에 써도 되나요?",
                type=QuestionType.BOOLEAN,
            ),
            Question(
                key="ai_usage_variance",
                prompt="팀원들 사이에 AI를 쓰는 정도 차이가 큰가요?",
                type=QuestionType.TEXT,
                help_text="예: '2명은 이미 잘 쓰고, 3명은 안 씀' 처럼 편차를 적어주세요.",
                optional=True,
            ),
        ],
    ),
    InterviewPart(
        key="repetitive_tasks",
        title="반복 업무 상세",
        questions=[
            Question(
                key="day_narrative",
                prompt="어제 하루를 떠올려서, 아침부터 퇴근까지 어떤 일을 하셨는지 시간순으로 알려주세요.",
                type=QuestionType.TASK_NARRATIVE,
                help_text=(
                    "'자동화할 업무'를 바로 떠올리기는 어려우니, 그냥 하루 일과를 이야기해주시면 "
                    "저희가 반복되는 업무를 뽑아 하나씩 여쭤볼게요."
                ),
            ),
        ],
    ),
    InterviewPart(
        key="member_tags",
        title="팀원 태깅 (선택)",
        questions=[
            Question(
                key="member_tags",
                prompt=(
                    "팀원별로 강점 영역, AI를 편하게 쓰는 정도, 지금 업무 부담을 간단히 태깅해주세요. "
                    "이름 대신 익명 식별자(예: M1, M2)로 적어주세요."
                ),
                type=QuestionType.TEXT,
                help_text="역할 재분배 제안(4.4)에만 쓰이고, 인사평가에는 절대 쓰지 않아요 (SPEC 2.6).",
                optional=True,
            ),
        ],
    ),
]


def get_interview_script() -> list[InterviewPart]:
    """프론트가 인터뷰 화면을 그릴 때 쓰는 질문 대본 전체를 반환한다."""
    return INTERVIEW_SCRIPT
