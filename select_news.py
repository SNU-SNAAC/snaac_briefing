"""OpenAI API(GPT)를 이용해 수집된 기사 중 5개를 선별하고 1~2줄 요약을 생성합니다."""

import json
import os

import requests

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# 비용/품질 균형 기본값. 더 저렴하게는 "gpt-5-mini".
# 모델명 오류가 나면 https://platform.openai.com/docs/models 에서 최신 이름 확인.
MODEL = "gpt-5.4-mini"

SYSTEM_PROMPT = """당신은 스타트업 커뮤니티 'SNAAC'의 뉴스 큐레이터입니다.
대학생·초기 창업가·스타트업 취업 희망자 400명이 모인 커뮤니티에 매일 아침 공유할 뉴스를 고릅니다.

선별 기준 (우선순위 순):
1. 투자 유치, M&A, IPO 등 스타트업 생태계의 굵직한 소식
2. 새로운 트렌드·기술 (AI, SaaS 등) 관련 인사이트
3. 창업가에게 실질적으로 유용한 정보 (정부 지원사업, 정책 변화 등)
4. 화제성 있고 대화 소재가 될 만한 소식
- 단순 홍보성 보도자료, 관련성 낮은 대기업 일반 뉴스는 제외

요약 작성 기준:
- 각 기사당 한국어 1~2문장, 최대 90자
- 기사 원문을 베끼지 말고 핵심만 자신의 말로 재구성
- 커뮤니티 멤버가 "클릭하고 싶어지게" 하되 낚시성 과장은 금지

반드시 아래 JSON 형식으로만 응답하세요:
{"picks": [{"title": "기사 제목", "link": "원문 URL", "source": "매체명", "summary": "1~2줄 요약"}]}
정확히 5개를 고르세요. 후보가 5개 미만이면 있는 만큼만 반환하세요.
link는 반드시 입력에 주어진 URL을 그대로 사용하세요."""


def select_top5(articles: list[dict]) -> list[dict]:
    """기사 목록을 GPT에 전달해 5개 선별 + 요약 반환."""
    api_key = os.environ["OPENAI_API_KEY"]

    # 토큰 절약을 위해 필요한 필드만 전달
    candidates = [
        {"title": a["title"], "link": a["link"], "source": a["source"],
         "summary": a["summary"], "published": a["published"]}
        for a in articles
    ]

    resp = requests.post(
        OPENAI_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "max_completion_tokens": 2000,
            # JSON 모드: 응답이 항상 유효한 JSON으로 오도록 강제
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": "오늘의 후보 기사 목록입니다:\n" + json.dumps(candidates, ensure_ascii=False)},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    text = data["choices"][0]["message"]["content"]
    picks = json.loads(text)["picks"]

    # 안전장치: 모델이 만들어낸(입력에 없는) 링크는 제거
    valid_links = {a["link"] for a in articles}
    picks = [p for p in picks if p.get("link") in valid_links][:5]

    print(f"[선별 완료] {len(picks)}건 (모델: {MODEL})")
    return picks
