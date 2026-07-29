"""개인 브리핑 생성 파이프라인.

1. RSS/Atom 후보 수집
2. 최근 아카이브와 중복되는 URL 제외
3. OpenAI가 오늘의 항목 선별·요약
4. GitHub Pages용 정적 페이지와 날짜별 아카이브 생성
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import settings
from collect import collect_articles, normalize_link
from page import build_page
from select_news import select_fallback, select_top

KST = timezone(timedelta(hours=9))
ARCHIVE_DIR = Path("docs/archive")


def recent_archive_links(days: int | None = None) -> set[str]:
    """최근 브리핑의 URL을 읽어 같은 콘텐츠가 반복 선택되지 않게 합니다.

    오늘 날짜의 JSON은 제외합니다. 따라서 UI를 수정한 뒤 같은 날 수동 재실행해도
    오늘 기사 전체가 강제로 다른 기사로 교체되지 않습니다.
    """
    keep_days = days or settings.RECENT_DUPLICATE_DAYS
    today = datetime.now(KST).date()
    cutoff = today - timedelta(days=keep_days)
    links: set[str] = set()

    if not ARCHIVE_DIR.exists():
        return links

    for path in ARCHIVE_DIR.glob("????-??-??.json"):
        try:
            archive_day = datetime.strptime(path.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if archive_day == today or archive_day < cutoff:
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[경고] 아카이브 읽기 실패: {path} ({exc})")
            continue

        for pick in data.get("picks", []):
            link = str(pick.get("link", "")).strip()
            if link:
                links.add(normalize_link(link))
    return links


def main() -> int:
    print(f"[시작] {settings.SITE_KOREAN_NAME} 생성")

    articles = collect_articles()
    if not articles:
        print("[종료] 수집된 후보가 없어 기존 페이지를 유지합니다.")
        return 0

    excluded_links = recent_archive_links()
    print(f"[중복 방지] 최근 {settings.RECENT_DUPLICATE_DAYS}일 URL {len(excluded_links)}개 제외")

    try:
        picks = select_top(articles, excluded_links=excluded_links)
    except Exception as exc:
        print(f"[경고] OpenAI 선별 실패 → 공개 RSS 폴백으로 계속 진행: {exc}", file=sys.stderr)
        picks = select_fallback(articles, excluded_links=excluded_links)

    if len(picks) < settings.MIN_PICKS:
        print(
            f"[종료] 최종 항목이 {len(picks)}개로 최소 {settings.MIN_PICKS}개에 미달해 "
            "기존 페이지를 유지합니다.",
            file=sys.stderr,
        )
        return 0

    for index, pick in enumerate(picks, 1):
        print(
            f"  {index:02d}. [{pick.get('section', '')} / {pick.get('source', '')}] "
            f"{pick.get('title', '')}"
        )

    build_page(picks)
    print(f"[완료] {settings.SITE_KOREAN_NAME} 갱신")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
