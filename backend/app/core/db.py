"""SQLAlchemy 엔진/세션. 지금은 Notion OAuth 연결 저장 용도로만 쓰인다.

DATABASE_URL이 비어있어도 import 시점에 에러가 나지 않도록 엔진 생성을 지연시킨다
(테스트 환경에서 .env 없이도 이 모듈을 import할 수 있어야 함).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_session_factory: sessionmaker | None = None


def get_session() -> Session:
    global _session_factory
    if _session_factory is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL이 설정되지 않았습니다 (.env 확인)")
        engine = create_engine(settings.database_url)
        _session_factory = sessionmaker(bind=engine)
    return _session_factory()
