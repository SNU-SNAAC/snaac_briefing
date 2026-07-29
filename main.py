"""SNAAC 모닝 브리핑 봇 - 메인 실행 스크립트.

파이프라인:
  1. 뉴스·인터뷰·인사이트·영상 수집
  2. 최근 브리핑과 중복 제거
  3. OpenAI가 품질 기준을 통과한 3~5개를 선별·요약
  4. 오늘 페이지 + 날짜별 아카이브 + 아카이브 인덱스 생성
  5. (선택) 팀장 카톡으로 배포 완료 알림

환경변수 BRIEFING_OUTPUT_DIR를 지정하면 실제 docs/ 대신 별도 폴더에 미리보기를
생성할 수 있습니다. 최근 링크 중복 검사는 항상 운영 아카이브인 docs/archive를
기준으로 하므로 미리보기 실행이 운영 기록을 오염시키지 않습니다.
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
PRODUCTION_ARCHIVE_DIR = Path("docs/archive")
OUTPUT_DIR = Path(os.environ.get("BRIEFING_OUTPUT_DIR", "docs")).resolve()
RECENT_DUPLICATE_DAYS = 21
MIN_PICKS_TO_PUBLISH = int(os.environ.get("MIN_PICKS_TO_PUBLISH", "3"))
QUALITY_HOLD_FILE = Path("briefing_quality_hold.txt")


def load_recent_links(days: int = RECENT_DUPLICATE_DAYS) -> set[str]:
    """운영 JSON 아카이브에서 최근에 소개한 링크를 불러옵니다."""
    if not PRODUCTION_ARCHIVE_DIR.exists():
        return set()

    cutoff = datetime.now(KST).date() - timedelta(days=days)
    links: set[str] = set()

    for path in PRODUCTION_ARCHIVE_DIR.glob("????-??-??.json"):
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

    if len(fresh) < 10:
        print(
            f"[안내] 최근 중복 제거 후 후보가 {len(fresh)}건이라 "
            "전체 후보를 사용하고 모델이 중복을 피하도록 합니다."
        )
        return articles

    print(f"[중복 제거] 최근 {RECENT_DUPLICATE_DAYS}일 소개 링크 제외 → {len(fresh)}건")
    return fresh


def write_quality_hold(reason: str) -> None:
    """기술 오류는 아니지만 오늘 회차를 발행하지 않은 이유를 워크플로에 전달합니다."""
    QUALITY_HOLD_FILE.write_text(reason.strip() + "\n", encoding="utf-8")
    print(f"[품질 보류 기록] {QUALITY_HOLD_FILE}: {reason}")


def main() -> None:
    QUALITY_HOLD_FILE.unlink(missing_ok=True)
    mode = "운영 배포" if OUTPUT_DIR.name == "docs" else f"미리보기 ({OUTPUT_DIR})"
    print(f"[실행 모드] {mode}")

    articles = collect_articles(hours=36)
    if not articles:
        reason = "수집된 공개 콘텐츠가 없어 기존 브리핑을 유지했습니다."
        print(f"[종료] {reason}")
        write_quality_hold(reason)
        sys.exit(0)

    recent_links = load_recent_links()
    candidates = remove_recent_duplicates(articles, recent_links)

    try:
        picks = select_top5(candidates, excluded_links=recent_links)
    except Exception as exc:
        # 오류를 숨기지 않고 Action을 실패시켜 운영자 알림 단계가 동작하게 합니다.
        print(f"[치명적 오류] 기사 선별 실패: {exc}")
        raise

    if len(picks) < MIN_PICKS_TO_PUBLISH:
        reason = (
            f"품질 기준을 통과한 콘텐츠가 {len(picks)}건으로 최소 "
            f"{MIN_PICKS_TO_PUBLISH}건보다 적어 기존 브리핑을 유지했습니다."
        )
        print(f"[품질 보류] {reason}")
        write_quality_hold(reason)
        sys.exit(0)

    for index, pick in enumerate(picks, 1):
        print(
            f"  {index}. [{pick.get('category', '기타')} / {pick['source']} / "
            f"{pick.get('quality_score', '?')}점] {pick['title']}"
        )

    build_page(picks, output_dir=OUTPUT_DIR)

    # 미리보기는 운영자 확인용이므로 카카오 알림을 보내지 않습니다.
    if OUTPUT_DIR.name != "docs":
        print("[안내] 미리보기 모드 → 카카오 배포 알림을 건너뜁니다.")
        return

    if os.environ.get("KAKAO_REST_API_KEY") and os.environ.get("KAKAO_REFRESH_TOKEN"):
        try:
            from kakao import send_to_me

            summary = "\n".join(
                f"{index}. {pick['title'][:28]}"
                for index, pick in enumerate(picks, 1)
            )
            notice = (
                f"✅ 오늘 브리핑 배포 파일 생성 완료! ({len(picks)}건)\n\n"
                f"{summary}\n\nGitHub Pages 반영 상태를 확인해 주세요."
            )
            send_to_me([notice[:200]])
        except Exception as exc:
            print(f"[경고] 카톡 알림 실패 (페이지 배포에는 영향 없음): {exc}")
    else:
        print("[안내] 카카오 시크릿 미설정 → 카톡 확인 알림은 건너뜁니다.")


if __name__ == "__main__":
    main()
