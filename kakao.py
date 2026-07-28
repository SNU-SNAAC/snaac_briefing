"""카카오 메시지 포맷팅 + '나에게 보내기' API 발송 모듈.

카카오는 오픈채팅방 봇 API를 공식 지원하지 않으므로,
완성된 메시지를 운영자 본인 카톡('나와의 채팅')으로 발송합니다.
운영자는 받은 메시지들을 길게 눌러 [전달 → 여러 개 선택]으로
오픈채팅방에 한 번에 전달하면 됩니다.

메시지 구성: 헤더 1개 + 기사당 1개 (총 6개)
→ 오픈채팅방에서 각 기사 링크마다 썸네일 미리보기가 자동 생성됩니다.
→ 본문/이미지를 직접 퍼오지 않고 원문 링크만 공유하므로 저작권 리스크가 없습니다.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
TEXT_LIMIT = 200  # 카카오 텍스트 템플릿 최대 길이


def build_messages(picks: list[dict]) -> list[str]:
    """헤더 1개 + 기사당 1개 메시지 목록 생성."""
    now = datetime.now(KST)
    header = (
        f"🌅 SNAAC 모닝 브리핑\n"
        f"{now.month}/{now.day}({WEEKDAYS[now.weekday()]}) | "
        f"어제 스타트업 생태계 주요 소식 {len(picks)}가지 ⬇️"
    )
    messages = [header]
    for i, p in enumerate(picks, 1):
        msg = f"{i}️⃣ {p['title']}\n\n{p['summary']}\n\n👉 {p['link']}"
        if len(msg) > TEXT_LIMIT:
            # 요약을 줄여서 제한 내로 맞춤 (링크는 절대 자르지 않음)
            overflow = len(msg) - TEXT_LIMIT
            short_summary = p["summary"][: max(0, len(p["summary"]) - overflow - 1)] + "…"
            msg = f"{i}️⃣ {p['title']}\n\n{short_summary}\n\n👉 {p['link']}"
        messages.append(msg)
    return messages


def refresh_access_token() -> str:
    """리프레시 토큰으로 액세스 토큰 갱신.

    카카오가 새 리프레시 토큰을 내려주면 (만료 1개월 전부터)
    파일로 남겨 GitHub Actions 워크플로가 시크릿을 자동 갱신하게 합니다.
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": os.environ["KAKAO_REST_API_KEY"],
            "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    new_refresh = data.get("refresh_token")
    if new_refresh:
        with open("new_refresh_token.txt", "w") as f:
            f.write(new_refresh)
        print("[알림] 새 리프레시 토큰 발급됨 → 시크릿 자동 갱신 예정")

    return data["access_token"]


def send_to_me(messages: list[str]) -> None:
    """'나와의 채팅'으로 메시지들을 순서대로 발송."""
    access_token = refresh_access_token()

    for msg in messages:
        # 텍스트 안의 URL 추출해 링크 버튼에도 연결 (없으면 기본 링크)
        url = next((w for w in msg.split() if w.startswith("http")), "https://open.kakao.com")
        template = {
            "object_type": "text",
            "text": msg,
            "link": {"web_url": url, "mobile_web_url": url},
        }
        resp = requests.post(
            MEMO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=30,
        )
        resp.raise_for_status()

    print(f"[발송 완료] 나와의 채팅으로 {len(messages)}개 메시지 전송")
