"""OpenAI API로 오늘의 스타트업 콘텐츠 4~5개를 선별하고 요약합니다.

핵심 변경점
- 투자 유치 단신 우선이 아니라 '읽고 얻어갈 것이 있는가'를 최우선 평가
- 뉴스, 인터뷰, 창업가/VC 관점, 제품·성장 인사이트, 영상의 다양성 확보
- RSS 후보에 더해 OpenAI Responses API 웹 검색으로 공개 LinkedIn/YouTube/
  인터뷰/칼럼 후보를 보완
- Structured Outputs로 응답 형식을 고정
- 유료 구독·멤버십 전용 원문은 도메인/페이지 검사로 제외
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

from collect import clean_public_link, normalize_link, strip_html

KST = timezone(timedelta(hours=9))
OPENAI_API_URL = "https://api.openai.com/v1/responses"

# GitHub Actions에서 미등록 Variable은 빈 문자열로 전달될 수 있습니다.
# 빈 문자열을 모델명으로 보내면 Responses API가 400 Bad Request를 반환하므로,
# strip() 후 값이 없으면 검증된 기본 모델로 확실히 대체합니다.
MODEL = (os.environ.get("OPENAI_MODEL") or "").strip() or "gpt-5.4-mini"
ENABLE_WEB_DISCOVERY = (os.environ.get("ENABLE_WEB_DISCOVERY") or "1").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
MAX_CANDIDATES = 60
MAX_PER_SOURCE_IN_FINAL = 2
MIN_FINAL_PICKS = 4
MAX_FINAL_PICKS = 5
MAX_MODEL_PICKS = 8
MIN_QUALITY_SCORE = int((os.environ.get("MIN_QUALITY_SCORE") or "72").strip() or "72")
MIN_SUPPLEMENT_QUALITY_SCORE = int((os.environ.get("MIN_SUPPLEMENT_QUALITY_SCORE") or "60").strip() or "60")
OPENAI_MAX_ATTEMPTS = int((os.environ.get("OPENAI_MAX_ATTEMPTS") or "3").strip() or "3")

# 유료 구독을 요구하는 대표 도메인은 후보/웹 검색 단계부터 제외합니다.
# 유료 잠금 비중이 높은 플랫폼은 도메인 단계에서 막고, 그 밖의 신규 도메인은 페이지 문구를 검사합니다.
PAYWALL_BLOCKED_DOMAINS = {
    "outstanding.kr",
    "publy.co",
    "longblack.co",
    "folin.co",
    "contents.premium.naver.com",
    "theinformation.com",
    "wsj.com",
    "ft.com",
    "bloomberg.com",
    "economist.com",
    "hbr.org",
    "businessinsider.com",
    "techinasia.com",
    "dealstreetasia.com",
    "pitchbook.com",
    "fortune.com",
    "medium.com",
    "seekingalpha.com",
}

# 공개 매체 도메인도 리디렉션·상태코드는 확인하되, 자동화 차단 응답은 보수적으로 해석합니다.
KNOWN_FREE_DOMAINS = {
    "platum.kr",
    "venturesquare.net",
    "startuprecipe.co.kr",
    "byline.network",
    "bloter.net",
    "zdnet.co.kr",
    "a16z.com",
    "a16z.news",
    "youtube.com",
    "youtu.be",
    "eopla.net",
}

PAYWALL_PATTERNS = [
    r'"isAccessibleForFree"\s*:\s*false',
    r"구독자\s*전용",
    r"유료\s*(회원|구독|콘텐츠)",
    r"멤버십\s*(전용|회원만)",
    r"프리미엄\s*콘텐츠",
    r"전체\s*(기사|내용).{0,30}(구독|결제)",
    r"남은\s*내용.{0,30}(구독|결제)",
    r"구독\s*후\s*(이용|열람|확인)",
    r"subscribe\s+to\s+(continue|read|unlock)",
    r"subscriber[- ]only",
    r"members?[-\s]+only",
    r"this\s+(article|content)\s+is\s+for\s+subscribers",
    r"unlock\s+(this|the)\s+(article|story)",
    r"continue\s+reading\s+with\s+a\s+subscription",
    # 무료 회원가입·로그인을 해야만 본문을 볼 수 있는 경우도 공개 원문으로 보지 않습니다.
    r"로그인\s*(후|해야).{0,40}(전체|본문|콘텐츠|기사)",
    r"(전체|본문|콘텐츠|기사).{0,40}로그인\s*(후|해야)",
    r"계속.{0,25}(로그인|회원가입)",
    r"sign\s+in\s+to\s+(continue|read|view)",
    r"log\s+in\s+to\s+(continue|read|view)",
    r"create\s+an\s+account\s+to\s+(continue|read|view)",
    r"join\s+linkedin\s+to\s+(see|view|continue)",
    r"sign\s+up\s+to\s+(continue|read|unlock)",
]

CATEGORY_VALUES = [
    "생태계 업데이트",
    "창업가 인터뷰",
    "VC·창업가 관점",
    "제품·성장 인사이트",
    "기술·시장 트렌드",
    "정책·기회",
]
CONTENT_TYPE_VALUES = [
    "기사",
    "인터뷰",
    "영상",
    "칼럼·리포트",
    "링크드인",
    "뉴스레터",
    "기타",
]

FUNDING_TERMS = (
    "투자 유치",
    "투자를 유치",
    "시드 투자",
    "프리a",
    "프리 a",
    "시리즈a",
    "시리즈 a",
    "시리즈b",
    "시리즈 b",
    "시리즈c",
    "시리즈 c",
    "투자받",
    "투자 받",
    "억원 투자",
    "funding",
    "million in funding",
    "raises",
    "raised",
)
FUNDING_CONTEXT_TERMS = (
    "인터뷰",
    "전략",
    "시장",
    "제품",
    "고객",
    "성장",
    "사업 모델",
    "비즈니스 모델",
    "전환",
    "회고",
    "교훈",
    "분석",
    "왜",
    "how",
    "why",
    "strategy",
    "market",
    "product",
    "customer",
    "growth",
    "lessons",
)

SYSTEM_PROMPT = """당신은 대학생·초기 창업가·스타트업 취업 희망자 400명이 모인
SNAAC 커뮤니티의 편집장입니다. 목표는 '투자 소식 5개'가 아니라, 독자가 오늘
스타트업 생태계를 더 잘 이해하고 실무적 관점 하나를 얻어가게 만드는 것입니다.

평가 기준(중요도 순):
1. 인사이트 가치: 새로운 관점, 구체적 경험, 데이터, 실행 가능한 교훈이 있는가
2. 스타트업 관련성: 창업가·팀·제품·시장·VC·정책을 이해하는 데 도움이 되는가
3. 맥락성: 단순 사실 발표가 아니라 왜 일어났고 무엇이 달라지는지 설명하는가
4. 출처 신뢰도: 당사자 인터뷰, 평판 있는 매체/기관, 창업가·VC의 공개 발언인가
5. 신선도와 대화 가치: 지금 커뮤니티에서 이야기할 만한가

반드시 지킬 편집 규칙:
- 단순히 '어느 회사가 얼마를 투자받았다'로 끝나는 투자 유치 단신은 최대 1개.
- 투자 기사를 고르더라도 사업 모델, 시장 변화, 창업자 판단 등 배울 맥락이 있어야 함.
- 최종 발행 4~5개가 한 종류에 치우치지 않도록 가능한 한 서로 다른 카테고리를 섞을 것.
- 같은 매체/채널은 최대 2개. 사실상 같은 사건의 중복 보도는 1개만 선택.
- 한국 스타트업 생태계와 직접 연결된 콘텐츠를 최소 3개 포함.
- 해외 콘텐츠는 최대 2개이며, 국내 독자에게 옮겨 적용할 명확한 이유가 있어야 함.
- 단순 보도자료 재전송, 제품 홍보, 수상/협약/행사 개최 사실만 있는 글은 제외.
- 링크드인 글은 유명세만 보지 말고, 구체적 주장·경험·데이터가 있을 때만 선택.
- 영상은 제목만 자극적인 콘텐츠보다 인터뷰·강연·토론처럼 밀도가 높은 것을 선호.
- 최종 원문은 유료 구독, 멤버십, 결제, 무료 체험 등록 없이 핵심 내용을 읽거나 볼 수 있어야 함.
- 일부 문단만 공개하고 나머지를 구독으로 잠근 기사, 프리미엄 콘텐츠, 유료 뉴스레터는 제외.
- 공개 웹 검색 결과는 최근 7일 이내를 우선하되, 실행 가치가 매우 높은 심층 글은
  최근 14일까지 허용.
- 각 후보를 0~100점으로 평가할 것. 원칙적으로 72점 이상을 우선한다.
- 72점 이상 후보가 4개 미만이면, 공개 원문·관련성·신뢰도를 충족한 60점 이상 후보 중 가장 나은 항목을 보완 후보로 포함해 최소 4개를 만들 것.
- 60점 미만, 단순 홍보, 사실상 중복, 구독 장벽이 있는 콘텐츠는 보완용으로도 선택하지 말 것.
- 시스템이 최종 4~5개를 안정적으로 구성할 수 있도록 우선순위가 높은 후보 5~8개를 반환할 것.

작성 규칙:
- summary: '무슨 내용인지 + 핵심 맥락'을 한국어 1~2문장, 120자 이내로 작성.
- takeaway: 독자가 왜 읽어야 하는지 또는 무엇을 생각해볼지 70자 이내로 작성.
- quality_score: 위 평가 기준을 종합한 0~100 정수. 기본 후보는 72점 이상, 최소 수량 보완 후보는 60점 이상.
- quality_reason: 선택한 핵심 이유를 60자 이내로 작성.
- 원문의 주장을 과장하거나 원문에 없는 사실을 만들지 말 것.
- link는 입력 후보의 URL 또는 웹 검색에서 실제 확인한 원문 URL만 사용할 것.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "picks": {
            "type": "array",
            "minItems": 5,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "link": {"type": "string"},
                    "source": {"type": "string"},
                    "published": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORY_VALUES},
                    "content_type": {"type": "string", "enum": CONTENT_TYPE_VALUES},
                    "summary": {"type": "string"},
                    "takeaway": {"type": "string"},
                    "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "quality_reason": {"type": "string"},
                },
                "required": [
                    "title",
                    "link",
                    "source",
                    "published",
                    "category",
                    "content_type",
                    "summary",
                    "takeaway",
                    "quality_score",
                    "quality_reason",
                ],
            },
        }
    },
    "required": ["picks"],
}


def _parse_iso(value: str) -> datetime | None:
    if not value or value == "unknown":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        return parsed.astimezone(KST)
    except ValueError:
        return None


def _candidate_score(article: dict) -> float:
    """API에 보낼 후보 수를 줄이기 위한 가벼운 사전 점수입니다.

    최종 판단은 모델이 하며, 여기서는 오래된 단순 투자 단신이 후보 공간을
    독점하지 않도록 정리하는 역할만 합니다.
    """
    score = 0.0
    content_type = article.get("content_type", "news")
    source_group = article.get("source_group", "news")
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    score += {
        "interview": 5.0,
        "insight": 4.5,
        "video": 4.0,
        "linkedin": 4.0,
        "news": 2.5,
    }.get(content_type, 2.0)

    if source_group == "insight":
        score += 2.5
    elif source_group == "video":
        score += 2.0

    high_value_terms = (
        "인터뷰", "인사이트", "전략", "분석", "리포트", "회고", "실패", "교훈",
        "제품", "고객", "리텐션", "그로스", "가격", "조직", "리더십", "시장",
        "interview", "playbook", "lessons", "strategy", "product", "growth",
        "retention", "pricing", "leadership", "market",
    )
    score += min(4.0, sum(0.8 for term in high_value_terms if term in text))

    # 투자 키워드만 있고 맥락형 단어가 거의 없는 제목은 후보 우선도를 낮춥니다.
    funding_terms = ("투자 유치", "시리즈a", "시리즈 a", "시리즈b", "시드 투자")
    context_terms = ("전략", "시장", "제품", "고객", "인터뷰", "성장", "왜", "분석")
    if any(term in text for term in funding_terms) and not any(
        term in text for term in context_terms
    ):
        score -= 2.5

    published = _parse_iso(article.get("published", "unknown"))
    if published:
        age_hours = max(0.0, (datetime.now(KST) - published).total_seconds() / 3600)
        if age_hours <= 24:
            score += 3.0
        elif age_hours <= 72:
            score += 2.0
        elif age_hours <= 168:
            score += 1.0

    return score


def _prepare_candidates(articles: list[dict]) -> list[dict]:
    ranked = sorted(articles, key=_candidate_score, reverse=True)
    selected: list[dict] = []
    source_counts: dict[str, int] = {}

    for article in ranked:
        source = article.get("source", "기타")
        link = clean_public_link(article.get("link", ""))
        if not _is_safe_http_url(link):
            continue
        if _is_blocked_paywall_domain(link):
            print(f"[무료 원문 제외] 구독형 도메인: {link}")
            continue
        # 한 피드가 후보 전체를 독점하지 않도록 사전 단계에서 최대 12개만 허용합니다.
        if source_counts.get(source, 0) >= 12:
            continue
        selected.append(
            {
                "title": article.get("title", "")[:240],
                "link": link,
                "source": source,
                "summary": strip_html(article.get("summary", ""))[:500],
                "published": article.get("published", "unknown"),
                "author": article.get("author", "")[:100],
                "source_group": article.get("source_group", "news"),
                "content_type": article.get("content_type", "news"),
                "thumbnail": article.get("thumbnail", ""),
            }
        )
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) >= MAX_CANDIDATES:
            break

    return selected

def _extract_output_text(data: dict) -> str:
    texts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    if not texts:
        raise ValueError("OpenAI 응답에서 output_text를 찾지 못했습니다.")
    return "\n".join(texts)


def _extract_web_source_urls(data: dict) -> set[str]:
    """웹 검색 도구가 실제로 참고한 URL을 추출합니다."""
    urls: set[str] = set()
    for item in data.get("output", []):
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action") or {}
        for source in action.get("sources") or []:
            url = source.get("url") or source.get("link")
            if url:
                urls.add(normalize_link(url))
    return urls


def _is_safe_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return False
        host = parts.netloc.lower()
        blocked_hosts = {
            "google.com",
            "www.google.com",
            "bing.com",
            "www.bing.com",
            "search.naver.com",
        }
        return host not in blocked_hosts
    except Exception:
        return False


def _host_matches(host: str, domains: set[str]) -> bool:
    host = host.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _is_blocked_paywall_domain(url: str) -> bool:
    try:
        return _host_matches(urlsplit(url).netloc, PAYWALL_BLOCKED_DOMAINS)
    except Exception:
        return True


def _looks_paywalled(page_html: str) -> bool:
    sample = page_html[:500_000]
    return any(re.search(pattern, sample, flags=re.I | re.S) for pattern in PAYWALL_PATTERNS)


_PUBLIC_LINK_CACHE: dict[str, str | None] = {}
MAX_LINK_REDIRECTS = 8
LINK_CHECK_TIMEOUT = (6, 15)
LINK_CHECK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
}


def _resolve_public_url(url: str) -> str | None:
    """최종 공개 전에 링크를 정리하고 리디렉션·접근성·페이월을 확인합니다.

    반환값은 추적 파라미터가 제거된 최종 URL입니다. 리디렉션 루프, 명백한
    404/410, 인증·결제 장벽은 ``None``으로 처리해 다른 후보로 교체합니다.
    """
    cleaned = clean_public_link(url)
    normalized = normalize_link(cleaned)
    if normalized in _PUBLIC_LINK_CACHE:
        return _PUBLIC_LINK_CACHE[normalized]
    if not _is_safe_http_url(cleaned) or _is_blocked_paywall_domain(cleaned):
        _PUBLIC_LINK_CACHE[normalized] = None
        return None

    session = requests.Session()
    session.max_redirects = MAX_LINK_REDIRECTS
    try:
        response = session.get(
            cleaned,
            timeout=LINK_CHECK_TIMEOUT,
            allow_redirects=True,
            headers=LINK_CHECK_HEADERS,
        )
    except requests.TooManyRedirects:
        print(f"[링크 제외] 리디렉션이 {MAX_LINK_REDIRECTS}회를 초과했습니다: {cleaned}")
        _PUBLIC_LINK_CACHE[normalized] = None
        return None
    except requests.RequestException as exc:
        # 실제 접근 여부를 확인하지 못한 후보를 억지로 발행하지 않습니다.
        # 뒤의 RSS 보완 단계가 다른 정상 링크로 최소 4건을 채웁니다.
        print(f"[링크 확인 실패 → 제외] {cleaned}: {exc}")
        _PUBLIC_LINK_CACHE[normalized] = None
        return None

    final_url = clean_public_link(response.url or cleaned)
    final_key = normalize_link(final_url)
    if not _is_safe_http_url(final_url) or _is_blocked_paywall_domain(final_url):
        _PUBLIC_LINK_CACHE[normalized] = None
        return None

    if response.status_code in {401, 402, 404, 410, 451}:
        print(f"[링크 제외] HTTP {response.status_code}: {final_url}")
        _PUBLIC_LINK_CACHE[normalized] = None
        return None

    original_host = urlsplit(cleaned).netloc
    final_host = urlsplit(final_url).netloc
    known_free = _host_matches(original_host, KNOWN_FREE_DOMAINS) or _host_matches(
        final_host, KNOWN_FREE_DOMAINS
    )

    if response.status_code >= 400:
        # 일부 공개 매체는 자동화 요청에만 403/405/429 또는 일시적인 5xx를 돌려줍니다.
        # 이 경우 리디렉션 루프는 이미 통과했으므로 깨진 링크로 단정하지 않습니다.
        ambiguous_block = response.status_code in {403, 405, 429} or response.status_code >= 500
        if known_free and ambiguous_block:
            print(
                f"[링크 확인 경고] HTTP {response.status_code}, 브라우저 공개 링크로 유지: "
                f"{final_url}"
            )
        else:
            print(f"[링크 제외] HTTP {response.status_code}: {final_url}")
            _PUBLIC_LINK_CACHE[normalized] = None
            return None

    if not known_free:
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" in content_type and _looks_paywalled(response.text):
            print(f"[무료 원문 제외] 구독·로그인 장벽 감지: {final_url}")
            _PUBLIC_LINK_CACHE[normalized] = None
            return None

    if final_url != cleaned:
        print(f"[링크 최종 정리] {cleaned} -> {final_url}")
    _PUBLIC_LINK_CACHE[normalized] = final_url
    if final_key:
        _PUBLIC_LINK_CACHE[final_key] = final_url
    return final_url


def _is_free_to_read(url: str) -> bool:
    """기존 호출부 호환용: 공개 가능한 최종 URL이 존재하는지 반환합니다."""
    return _resolve_public_url(url) is not None

def _clean_pick(pick: dict) -> dict:
    return {
        "title": strip_html(str(pick.get("title", "")))[:240],
        "link": clean_public_link(str(pick.get("link", "")).strip()),
        "source": strip_html(str(pick.get("source", "")))[:80],
        "published": strip_html(str(pick.get("published", "unknown")))[:40] or "unknown",
        "category": str(pick.get("category", "생태계 업데이트")),
        "content_type": str(pick.get("content_type", "기사")),
        "summary": strip_html(str(pick.get("summary", "")))[:180],
        "takeaway": strip_html(str(pick.get("takeaway", "")))[:120],
        "quality_score": max(0, min(100, int(pick.get("quality_score", 0) or 0))),
        "quality_reason": strip_html(str(pick.get("quality_reason", "")))[:120],
        "thumbnail": str(pick.get("thumbnail", "")).strip(),
    }

def _is_funding_only(item: dict) -> bool:
    """맥락 없이 투자 사실만 전달하는 콘텐츠인지 보수적으로 추정합니다."""
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    has_funding = any(term in text for term in FUNDING_TERMS)
    has_context = any(term in text for term in FUNDING_CONTEXT_TERMS)
    return has_funding and not has_context


def _infer_category(candidate: dict) -> str:
    """모델 응답 보충 시 후보의 주제 카테고리를 가볍게 추정합니다."""
    text = f"{candidate.get('title', '')} {candidate.get('summary', '')}".lower()
    content_type = candidate.get("content_type", "news")

    if any(term in text for term in ("정책", "규제", "지원사업", "법안", "policy", "regulation")):
        return "정책·기회"
    if content_type in {"video", "interview"}:
        return "창업가 인터뷰"
    if any(term in text for term in ("vc", "심사역", "투자자", "founder", "창업가 관점")):
        return "VC·창업가 관점"
    if any(
        term in text
        for term in (
            "ai", "인공지능", "시장", "산업", "트렌드", "기술", "market", "technology",
        )
    ):
        return "기술·시장 트렌드"
    if any(
        term in text
        for term in (
            "제품", "고객", "그로스", "성장", "리텐션", "가격", "gtm",
            "product", "customer", "growth", "retention", "pricing",
        )
    ) or content_type == "insight":
        return "제품·성장 인사이트"
    return "생태계 업데이트"


def _enforce_editorial_limits(picks: list[dict]) -> list[dict]:
    """출처·투자 단신·카테고리 다양성 규칙을 코드에서도 강제합니다."""
    selected: list[dict] = []
    selected_links: set[str] = set()
    source_counts: dict[str, int] = {}
    selected_categories: set[str] = set()
    funding_only_count = 0

    def can_add(pick: dict) -> bool:
        nonlocal funding_only_count
        source = pick.get("source", "기타")
        if source_counts.get(source, 0) >= MAX_PER_SOURCE_IN_FINAL:
            return False
        if _is_funding_only(pick) and funding_only_count >= 1:
            return False
        return True

    def add_pick(pick: dict) -> None:
        nonlocal funding_only_count
        link_key = normalize_link(pick.get("link", ""))
        selected.append(pick)
        selected_links.add(link_key)
        source = pick.get("source", "기타")
        category = pick.get("category", "생태계 업데이트")
        source_counts[source] = source_counts.get(source, 0) + 1
        selected_categories.add(category)
        if _is_funding_only(pick):
            funding_only_count += 1

    # 1차: 서로 다른 카테고리를 우선해 최소 3개 관점을 확보합니다.
    for pick in picks:
        category = pick.get("category", "생태계 업데이트")
        if category in selected_categories or not can_add(pick):
            continue
        add_pick(pick)
        if len(selected_categories) >= 3:
            break

    # 2차: 나머지를 원래 품질 순서대로 채우되 출처·투자 단신 제한을 유지합니다.
    for pick in picks:
        if len(selected) >= MAX_FINAL_PICKS:
            break
        link_key = normalize_link(pick.get("link", ""))
        if link_key in selected_links:
            continue
        if not can_add(pick):
            reason = "같은 출처 2개 초과" if source_counts.get(pick.get("source", "기타"), 0) >= MAX_PER_SOURCE_IN_FINAL else "단순 투자 단신 1개 초과"
            print(f"[편집 제외] {reason}: {pick.get('title', '')}")
            continue
        add_pick(pick)

    if len(selected_categories) < 2:
        print(
            f"[편집 경고] 최종 후보의 카테고리가 {len(selected_categories)}개로 적지만 "
            "최소 4개 발행 원칙을 우선합니다."
        )

    return selected


def _ensure_minimum_picks(selected: list[dict], ranked_candidates: list[dict]) -> list[dict]:
    """엄격한 출처·투자 단신 제한으로 4개 미만이 되면 안전한 보완 후보를 추가합니다.

    여기 들어오는 후보는 URL·중복·구독 장벽 검사와 최소 60점 기준을 이미 통과했습니다.
    따라서 최종 수량만 보완하되 같은 링크는 절대 중복하지 않습니다.
    """
    if len(selected) >= MIN_FINAL_PICKS:
        return selected[:MAX_FINAL_PICKS]

    selected_links = {normalize_link(item.get("link", "")) for item in selected}
    for pick in ranked_candidates:
        if len(selected) >= MIN_FINAL_PICKS:
            break
        link_key = normalize_link(pick.get("link", ""))
        if not link_key or link_key in selected_links:
            continue
        selected.append(pick)
        selected_links.add(link_key)
        print(
            f"[최소 수량 보완] {pick.get('quality_score', 0)}점 / "
            f"{pick.get('source', '기타')}: {pick.get('title', '')}"
        )

    return selected[:MAX_FINAL_PICKS]


def _validate_picks(
    raw_picks: list[dict],
    candidates: list[dict],
    web_source_urls: set[str],
    web_enabled: bool,
    excluded_links: set[str],
) -> list[dict]:
    candidate_map = {normalize_link(item["link"]): item for item in candidates}
    validated: list[dict] = []
    seen_links: set[str] = set()

    for raw_pick in raw_picks:
        pick = _clean_pick(raw_pick)
        if pick["quality_score"] < MIN_SUPPLEMENT_QUALITY_SCORE:
            print(
                f"[품질 제외] {pick['quality_score']}점 < {MIN_SUPPLEMENT_QUALITY_SCORE}점: "
                f"{pick.get('title', '')}"
            )
            continue

        requested_link = pick["link"]
        if not _is_safe_http_url(requested_link):
            continue
        requested_key = normalize_link(requested_link)
        if requested_key in excluded_links:
            print(f"[제외] 최근 브리핑에서 이미 소개한 URL: {requested_link}")
            continue

        original = candidate_map.get(requested_key)
        if not original:
            if not web_enabled:
                continue
            # 웹에서 새로 찾은 항목은 검색 도구가 실제로 반환한 원문 URL만 허용합니다.
            if not web_source_urls or requested_key not in web_source_urls:
                print(f"[제외] 웹 검색 출처로 확인되지 않은 URL: {requested_link}")
                continue

        final_link = _resolve_public_url(requested_link)
        if not final_link:
            print(f"[원문 제외] 열 수 없는 링크 또는 구독·로그인 장벽: {requested_link}")
            continue
        final_key = normalize_link(final_link)
        if not final_key or final_key in seen_links:
            continue
        if final_key in excluded_links:
            print(f"[제외] 최근 브리핑에서 이미 소개한 최종 URL: {final_link}")
            continue
        pick["link"] = final_link

        if original:
            # 입력 후보를 골랐다면 제목·출처·날짜는 원본 데이터로 고정합니다.
            pick["title"] = original["title"]
            pick["source"] = original["source"]
            pick["published"] = original.get("published", "unknown")
            pick["thumbnail"] = original.get("thumbnail", "")

        if not pick["title"] or not pick["summary"]:
            continue
        if pick["category"] not in CATEGORY_VALUES:
            pick["category"] = "생태계 업데이트"
        if pick["content_type"] not in CONTENT_TYPE_VALUES:
            pick["content_type"] = "기타"
        if not pick["takeaway"]:
            pick["takeaway"] = "원문에서 이번 변화가 창업가와 팀에 주는 의미를 확인해보세요."

        seen_links.add(final_key)
        validated.append(pick)
        if len(validated) >= MAX_MODEL_PICKS:
            break

    return validated

def _supplement_from_ranked_candidates(
    validated: list[dict],
    candidates: list[dict],
    excluded_links: set[str],
) -> list[dict]:
    """모델 선별 후 4건이 남지 않으면 상위 RSS 후보로 안전하게 보완합니다.

    모델이 반환한 링크가 페이월·중복·리디렉션 검사에서 탈락해도 브리핑이
    3건으로 줄지 않도록 하는 마지막 안전장치입니다.
    """
    if len(validated) >= MIN_FINAL_PICKS:
        return validated

    seen_links = {normalize_link(item.get("link", "")) for item in validated}
    content_type_map = {
        "news": "기사",
        "interview": "인터뷰",
        "video": "영상",
        "linkedin": "링크드인",
        "insight": "칼럼·리포트",
    }
    for candidate in candidates:
        if len(validated) >= MAX_MODEL_PICKS:
            break
        requested_link = clean_public_link(str(candidate.get("link", "")).strip())
        requested_key = normalize_link(requested_link)
        if not requested_key or requested_key in seen_links or requested_key in excluded_links:
            continue
        if not _is_safe_http_url(requested_link):
            continue
        final_link = _resolve_public_url(requested_link)
        if not final_link:
            continue
        final_key = normalize_link(final_link)
        if not final_key or final_key in seen_links or final_key in excluded_links:
            continue

        title = strip_html(str(candidate.get("title", "")))[:240]
        summary = strip_html(str(candidate.get("summary", "")))[:180]
        if not title or len(summary) < 20:
            continue
        category = _infer_category(candidate)
        raw_type = str(candidate.get("content_type", "news")).lower()
        pick = {
            "title": title,
            "link": final_link,
            "source": strip_html(str(candidate.get("source", "기타")))[:80] or "기타",
            "published": strip_html(str(candidate.get("published", "unknown")))[:40] or "unknown",
            "category": category,
            "content_type": content_type_map.get(raw_type, "기타"),
            "summary": summary,
            "takeaway": "원문에서 이번 변화가 스타트업과 창업가에게 주는 의미를 확인해보세요.",
            "quality_score": MIN_SUPPLEMENT_QUALITY_SCORE,
            "quality_reason": "최소 4건 구성을 위한 상위 공개 RSS 후보",
            "thumbnail": str(candidate.get("thumbnail", "")).strip(),
        }
        validated.append(pick)
        seen_links.add(final_key)
        print(f"[RSS 보완 후보] {pick['source']}: {pick['title']}")
    return validated

def _request_openai(
    candidates: list[dict],
    web_enabled: bool,
    excluded_links: set[str],
) -> tuple[dict, set[str]]:
    api_key = os.environ["OPENAI_API_KEY"]
    today = datetime.now(KST)
    date_text = today.strftime("%Y-%m-%d")

    recent_links_text = json.dumps(sorted(excluded_links), ensure_ascii=False)

    user_prompt = f"""오늘은 한국시간 {date_text}입니다.
아래 RSS/Atom 후보를 우선 검토하세요. 웹 검색이 활성화되어 있다면 최근 7일의 공개 웹에서
다음 후보도 보완 탐색하세요: 한국 스타트업 대표·VC 심사역의 공개 LinkedIn 글,
창업가 인터뷰, 유튜브 인터뷰/강연, 제품·성장·조직·시장에 관한 깊이 있는 아티클.
단, 유료 구독이나 멤버십 결제 없이 핵심 원문 전체를 확인할 수 있는 공개 콘텐츠만 고르세요.

검색 시 특정 유명인만 반복하지 말고, 실제 내용의 밀도와 커뮤니티 유용성을 평가하세요.
최종 발행 4~5개를 만들 수 있도록 우선순위 후보 5~8개를 반환하세요.
72점 이상을 우선하되 부족하면 60점 이상 중 가장 나은 공개 콘텐츠를 보완 후보로 포함하세요.
아래 '최근 소개 URL'에 있는 링크는 웹 검색 결과에 나오더라도 다시 선택하지 마세요.

최근 소개 URL JSON:
{recent_links_text}

RSS/Atom 후보 JSON:
{json.dumps(candidates, ensure_ascii=False)}"""

    payload: dict = {
        "model": MODEL,
        "max_output_tokens": 4500,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "snaac_briefing_picks",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },
    }

    if web_enabled:
        payload.update(
            {
                "tools": [
                    {
                        "type": "web_search",
                        "external_web_access": True,
                        "user_location": {
                            "type": "approximate",
                            "country": "KR",
                            "city": "Seoul",
                            "region": "Seoul",
                        },
                        "filters": {
                            "blocked_domains": sorted(
                                PAYWALL_BLOCKED_DOMAINS
                                | {"wikipedia.org", "namu.wiki", "reddit.com", "quora.com"}
                            )
                        },
                    }
                ],
                "tool_choice": "required",
                "include": ["web_search_call.action.sources"],
            }
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: requests.RequestException | None = None
    for attempt in range(1, OPENAI_MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=180,
            )
            if response.status_code >= 400:
                # GitHub Actions 로그에서 다음 오류의 원인을 바로 확인할 수 있도록
                # OpenAI가 반환한 안전한 오류 본문을 출력합니다. API 키는 응답 본문에 없습니다.
                error_body = (response.text or "").strip()
                print(
                    f"[OpenAI API 오류] status={response.status_code} "
                    f"model={MODEL!r} web={web_enabled} "
                    f"body={error_body[:1800]}"
                )

            if response.status_code == 429:
                body = response.text.lower()
                # 잔액/결제 한도 문제는 기다려도 해결되지 않으므로 즉시 중단합니다.
                if any(token in body for token in (
                    "insufficient_quota", "billing", "quota", "credit balance",
                )):
                    response.raise_for_status()
            response.raise_for_status()
            data = response.json()
            return data, _extract_web_source_urls(data)
        except requests.RequestException as exc:
            last_error = exc
            response_obj = getattr(exc, "response", None)
            status = getattr(response_obj, "status_code", None)
            body = (getattr(response_obj, "text", "") or "").lower()
            quota_error = status == 429 and any(token in body for token in (
                "insufficient_quota", "billing", "quota", "credit balance",
            ))
            if quota_error:
                raise
            retryable = status in {408, 409, 429, 500, 502, 503, 504} or status is None
            if not retryable or attempt >= OPENAI_MAX_ATTEMPTS:
                raise
            delay = min(30.0, (2 ** (attempt - 1)) * 3.0 + random.uniform(0.0, 1.5))
            print(
                f"[OpenAI 재시도] {attempt}/{OPENAI_MAX_ATTEMPTS} 실패 "
                f"({status or 'network'}) → {delay:.1f}초 후 재시도"
            )
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI 요청에 실패했습니다.")


def select_top5(
    articles: list[dict],
    excluded_links: set[str] | None = None,
) -> list[dict]:
    """후보를 평가해 최종 4~5개 콘텐츠와 요약을 반환합니다."""
    excluded_links = {
        normalize_link(link) for link in (excluded_links or set()) if link
    }
    candidates = _prepare_candidates(articles)
    if not candidates:
        return []

    web_enabled = ENABLE_WEB_DISCOVERY
    try:
        data, web_source_urls = _request_openai(
            candidates,
            web_enabled=web_enabled,
            excluded_links=excluded_links,
        )
    except requests.HTTPError as exc:
        response = exc.response
        body = (response.text if response is not None else "").lower()
        status = response.status_code if response is not None else None
        quota_error = status == 429 and any(token in body for token in (
            "insufficient_quota", "billing", "quota", "credit balance",
        ))
        if not web_enabled or quota_error:
            raise
        # 웹 검색 도구 자체의 일시 오류일 때만 RSS 전용 요청을 한 번 시도합니다.
        print(f"[경고] 웹 탐색 포함 선별 실패 → RSS 전용으로 재시도: {exc}")
        data, web_source_urls = _request_openai(
            candidates,
            web_enabled=False,
            excluded_links=excluded_links,
        )
        web_enabled = False
    except requests.RequestException as exc:
        if not web_enabled:
            raise
        print(f"[경고] 웹 탐색 포함 선별 실패 → RSS 전용으로 재시도: {exc}")
        data, web_source_urls = _request_openai(
            candidates,
            web_enabled=False,
            excluded_links=excluded_links,
        )
        web_enabled = False

    text = _extract_output_text(data)
    parsed = json.loads(text)
    raw_picks = parsed.get("picks", [])
    validated = _validate_picks(
        raw_picks,
        candidates,
        web_source_urls,
        web_enabled,
        excluded_links,
    )
    validated = _supplement_from_ranked_candidates(
        validated,
        candidates,
        excluded_links,
    )
    validated.sort(
        key=lambda item: (
            item.get("quality_score", 0) >= MIN_QUALITY_SCORE,
            item.get("quality_score", 0),
        ),
        reverse=True,
    )
    picks = _enforce_editorial_limits(validated)[:MAX_FINAL_PICKS]
    picks = _ensure_minimum_picks(picks, validated)

    if len(picks) < MIN_FINAL_PICKS:
        print(
            f"[품질 보류] 기준을 통과한 콘텐츠가 {len(picks)}건뿐이라 "
            f"최소 {MIN_FINAL_PICKS}건을 충족하지 못했습니다."
        )
        return []

    supplement_count = sum(
        1 for pick in picks if pick.get("quality_score", 0) < MIN_QUALITY_SCORE
    )
    print(
        f"[선별 완료] {len(picks)}건 "
        f"(기본 기준: {MIN_QUALITY_SCORE}점, 보완 후보: {supplement_count}건, "
        f"모델: {MODEL}, 웹 탐색: {'사용' if web_enabled else '미사용'})"
    )
    return picks
