"""
contracts/assets.py

5번(로드맵 실행 트래킹 / 자산화 저장소) 소관 스키마 — 스프린트1에서는 사용하지 않는다
(generate_roadmap()의 assets 인자는 항상 None). 5번 구현 시점에 실제 필드로 채워질 자리만 잡아둔다.
"""

from pydantic import BaseModel


class AssetStore(BaseModel):
    pass
