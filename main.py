"""SNAAC 모닝 브리핑 봇 - 메인 실행 스크립트 (100% 자동화 버전).

파이프라인:
  1. 뉴스 수집 → 2. Claude 선별/요약 → 3. 브리핑 페이지 생성(GitHub Pages)
  → 4. (선택) 팀장 카톡으로 배포 완료 알림

매일 08:30 KST에 GitHub Actions가 실행하고,
09:00 KST에 카카오 오픈채팅봇 반복알림이 고정 링크를 발송합니다.
"""

import os
import sys

from collect import collect_articles
from select_news import select_top5
from page import build_page


def main():
    # 1단계: 지난 24시간 스타트업 기사 수집
    articles = collect_articles(hours=24)
    if not articles:
        print("[종료] 수집된 기사가 없어 페이지를 갱신하지 않습니다. (전날 브리핑 유지)")
        sys.exit(0)

    # 2단계: Claude가 5개 선별 + 1~2줄 요약
    picks = select_top5(articles)
    if not picks:
        print("[종료] 선별된 기사가 없어 페이지를 갱신하지 않습니다.")
        sys.exit(0)

    for i, p in enumerate(picks, 1):
        print(f"  {i}. [{p['source']}] {p['title']}")

    # 3단계: 브리핑 페이지 생성 (워크플로가 커밋 → GitHub Pages 자동 배포)
    build_page(picks)

    # 4단계(선택): 팀장 카톡으로 배포 확인 알림
    if os.environ.get("KAKAO_REST_API_KEY") and os.environ.get("KAKAO_REFRESH_TOKEN"):
        try:
            from kakao import build_messages, send_to_me
            summary = "\n".join(f"{i}. {p['title'][:30]}" for i, p in enumerate(picks, 1))
            notice = f"✅ 오늘 브리핑 배포 완료!\n\n{summary}\n\n9시에 채팅방 알림이 나갑니다."
            send_to_me([notice[:200]])
        except Exception as e:
            print(f"[경고] 카톡 알림 실패 (페이지 배포에는 영향 없음): {e}")
    else:
        print("[안내] 카카오 시크릿 미설정 → 카톡 확인 알림은 건너뜁니다.")


if __name__ == "__main__":
    main()
