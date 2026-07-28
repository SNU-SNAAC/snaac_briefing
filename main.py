"""SNAAC 모닝 브리핑 봇 - 메인 실행 스크립트.

파이프라인:
  1. 뉴스·인터뷰·인사이트·영상 수집
  2. 최근 브리핑과 중복 제거
  3. OpenAI가 다양성과 독자 가치를 기준으로 5개 선별·요약
  4. 오늘 페이지 + 날짜별 아카이브 + 아카이브 인덱스 생성
  5. (선택) 팀장 카톡으로 배포 완료 알림
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collect import collect_articles, normalize_link
from page import build_page
from select_news import select_top5

KST = timezone(timedelta(hours=9))
ARCHIVE_DIR = Path("docs/archive")
RECENT_DUPLICATE_DAYS = 21


def load_recent_links(days: int = RECENT_DUPLICATE_DAYS) -> set[str]:
    """최근 날짜별 JSON 아카이브에서 이미 소개한 링크를 불러옵니다."""
    if not ARCHIVE_DIR.exists():
        return set()

    cutoff = datetime.now(KST).date() - timedelta(days=days)
    links: set[str] = set()

    for path in ARCHIVE_DIR.glob("????-??-??.json"):
        try:
            file_date = datetime.strptime(path.stem, "%Y-%m-%d").date()
            if file_date < cutoff:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for pick in data.get("picks", []):
                link = pick.get("link")
                if link:
                    links.add(normalize_link(link))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[경고] 아카이브 읽기 실패 {path}: {exc}")

    return links


def remove_recent_duplicates(articles: list[dict], recent_links: set[str]) -> list[dict]:
    if not recent_links:
        return articles

    fresh = [
        article
        for article in articles
        if normalize_link(article.get("link", "")) not in recent_links
    ]

    # 너무 많이 걸러져 후보가 부족해질 때만 원본 목록을 사용합니다.
    if len(fresh) < 10:
        print(
            f"[안내] 최근 중복 제거 후 후보가 {len(fresh)}건이라 "
            "전체 후보를 사용하고 모델이 중복을 피하도록 합니다."
        )
        return articles

    print(f"[중복 제거] 최근 {RECENT_DUPLICATE_DAYS}일 소개 링크 제외 → {len(fresh)}건")
    return fresh


def main() -> None:
    # 일반 뉴스는 약 36시간, 인사이트/영상은 collect.py의 소스별 범위를 사용합니다.
    articles = collect_articles(hours=36)
    if not articles:
        print("[종료] 수집된 콘텐츠가 없어 페이지를 갱신하지 않습니다. (전날 브리핑 유지)")
        sys.exit(0)

    recent_links = load_recent_links()
    candidates = remove_recent_duplicates(articles, recent_links)

    # RSS 후보뿐 아니라 웹 검색에서 새로 찾은 링크도 최근 회차와 중복되지 않도록
    # 최근 소개 URL을 선별 단계에 함께 전달합니다.
    picks = select_top5(candidates, excluded_links=recent_links)
    if not picks:
        print("[종료] 선별된 콘텐츠가 없어 페이지를 갱신하지 않습니다.")
        sys.exit(0)

    for index, pick in enumerate(picks, 1):
        print(
            f"  {index}. [{pick.get('category', '기타')} / {pick['source']}] "
            f"{pick['title']}"
        )

    build_page(picks)

    # 선택사항: 팀장 카톡으로 배포 확인 알림
    if os.environ.get("KAKAO_REST_API_KEY") and os.environ.get("KAKAO_REFRESH_TOKEN"):
        try:
            from kakao import send_to_me

            summary = "\n".join(
                f"{index}. {pick['title'][:28]}"
                for index, pick in enumerate(picks, 1)
            )
            notice = f"✅ 오늘 브리핑 배포 완료!\n\n{summary}\n\n9시에 채팅방 알림이 나갑니다."
            send_to_me([notice[:200]])
        except Exception as exc:
            print(f"[경고] 카톡 알림 실패 (페이지 배포에는 영향 없음): {exc}")
    else:
        print("[안내] 카카오 시크릿 미설정 → 카톡 확인 알림은 건너뜁니다.")


if __name__ == "__main__":
    main()
