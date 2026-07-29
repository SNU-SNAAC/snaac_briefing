"""OpenAI Responses API로 오늘의 브리핑 콘텐츠를 선별하고 요약합니다.

- RSS/Atom 후보와 공개 웹 검색을 함께 사용
- 로그인·구독·결제가 필요한 원문 제외
- Structured Outputs로 결과 형식 고정
- 429/5xx 오류에 지수 백오프 재시도
- 도메인별 섹션 비율은 settings.py의 SECTION_TARGETS로 강제
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

import settings
from collect import normalize_link, strip_html

KST = timezone(timedelta(hours=9))
OPENAI_API_URL = "https://api.openai.com/v1/responses"
MODEL = (os.environ.get("OPENAI_MODEL") or "gpt-5.6-luna").strip()
ENABLE_WEB_DISCOVERY = os.environ.get("ENABLE_WEB_DISCOVERY", "1").lower() not in {
    "0", "false", "no", "off"
}

PAYWALL_PATTERNS = [
    r'"isAccessibleForFree"\s*:\s*false',
    r"구독자\s*전용",
    r"유료\s*(회원|구독|콘텐츠)",
    r"멤버십\s*(전용|회원만)",
    r"프리미엄\s*콘텐츠",
    r"전체\s*(기사|내용).{0,40}(구독|결제)",
    r"남은\s*내용.{0,40}(구독|결제)",
    r"구독\s*후\s*(이용|열람|확인)",
    r"subscribe\s+to\s+(continue|read|unlock)",
    r"subscriber[- ]only",
    r"members?[-\s]+only",
    r"unlock\s+(this|the)\s+(article|story)",
    r"continue\s+reading\s+with\s+a\s+subscription",
    r"로그인\s*(후|해야).{0,50}(전체|본문|콘텐츠|기사)",
    r"(전체|본문|콘텐츠|기사).{0,50}로그인\s*(후|해야)",
    r"sign\s+in\s+to\s+(continue|read|view)",
    r"log\s+in\s+to\s+(continue|read|view)",
    r"create\s+an\s+account\s+to\s+(continue|read|view)",
]

CONTENT_TYPE_MAP = {
    "news": "기사",
    "official": "공식 발표",
    "analysis": "분석·리포트",
    "interview": "인터뷰",
    "video": "영상",
}


class OpenAIQuotaError(RuntimeError):
    """크레딧/결제 한도로 재시도가 의미 없는 429 오류."""


class OpenAIResponseError(RuntimeError):
    """API 응답 형식 또는 최종 결과가 유효하지 않을 때 발생."""


def _output_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "picks": {
                "type": "array",
                "minItems": settings.MIN_PICKS,
                "maxItems": settings.PICK_COUNT,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "link": {"type": "string"},
                        "source": {"type": "string"},
                        "published": {"type": "string"},
                        "section": {"type": "string", "enum": settings.SECTION_VALUES},
                        "category": {"type": "string", "enum": settings.CATEGORY_VALUES},
                        "content_type": {"type": "string", "enum": settings.CONTENT_TYPE_VALUES},
                        "summary": {"type": "string"},
                        "takeaway": {"type": "string"},
                    },
                    "required": [
                        "title", "link", "source", "published", "section", "category",
                        "content_type", "summary", "takeaway",
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
    score = 0.0
    group = article.get("source_group", "news")
    score += {"market": 4.0, "official": 3.5, "analysis": 3.5, "news": 3.0}.get(group, 2.0)

    summary = strip_html(article.get("summary", ""))
    score += min(2.0, len(summary) / 260)

    published = _parse_iso(article.get("published", "unknown"))
    if published:
        age_hours = max(0.0, (datetime.now(KST) - published).total_seconds() / 3600)
        if age_hours <= 18:
            score += 4.0
        elif age_hours <= 36:
            score += 3.0
        elif age_hours <= 72:
            score += 2.0
        elif age_hours <= 168:
            score += 1.0

    text = f"{article.get('title', '')} {summary}".lower()
    for category, keywords in settings.CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            score += 0.7
    return score


def _prepare_candidates(articles: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {section: [] for section in settings.SECTION_VALUES}
    for article in articles:
        buckets.setdefault(article.get("section", settings.SECTION_VALUES[0]), []).append(article)
    for section in buckets:
        buckets[section].sort(key=_candidate_score, reverse=True)

    selected: list[dict] = []
    selected_links: set[str] = set()
    source_counts: dict[str, int] = {}
    per_section_soft_cap = max(14, settings.MAX_CANDIDATES // max(1, len(settings.SECTION_VALUES)))

    def add(article: dict) -> bool:
        source = article.get("source", "기타")
        link = article.get("link", "")
        normalized = normalize_link(link)
        if not link or normalized in selected_links:
            return False
        if _is_blocked_paywall_domain(link):
            return False
        if source_counts.get(source, 0) >= 12:
            return False
        selected.append(
            {
                "title": article.get("title", "")[:240],
                "link": link,
                "source": source,
                "summary": strip_html(article.get("summary", ""))[:520],
                "published": article.get("published", "unknown"),
                "author": article.get("author", "")[:100],
                "source_group": article.get("source_group", "news"),
                "section": article.get("section", settings.SECTION_VALUES[0]),
                "content_type": article.get("content_type", "news"),
                "thumbnail": article.get("thumbnail", ""),
            }
        )
        selected_links.add(normalized)
        source_counts[source] = source_counts.get(source, 0) + 1
        return True

    for section in settings.SECTION_VALUES:
        count = 0
        for article in buckets.get(section, []):
            if add(article):
                count += 1
            if count >= per_section_soft_cap or len(selected) >= settings.MAX_CANDIDATES:
                break

    if len(selected) < settings.MAX_CANDIDATES:
        remainder = sorted(articles, key=_candidate_score, reverse=True)
        for article in remainder:
            add(article)
            if len(selected) >= settings.MAX_CANDIDATES:
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
        raise OpenAIResponseError("OpenAI 응답에서 output_text를 찾지 못했습니다.")
    return "\n".join(texts)


def _extract_web_source_urls(data: dict) -> set[str]:
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
        host = parts.netloc.lower().split(":", 1)[0]
        return host not in {"google.com", "www.google.com", "bing.com", "www.bing.com", "search.naver.com"}
    except Exception:
        return False


def _host_matches(host: str, domains: set[str]) -> bool:
    host = host.lower().split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _is_blocked_paywall_domain(url: str) -> bool:
    try:
        return _host_matches(urlsplit(url).netloc, settings.PAYWALL_BLOCKED_DOMAINS)
    except Exception:
        return True


def _looks_paywalled(page_html: str) -> bool:
    sample = page_html[:500_000]
    return any(re.search(pattern, sample, flags=re.I | re.S) for pattern in PAYWALL_PATTERNS)


_FREE_ACCESS_CACHE: dict[str, bool] = {}


def _is_free_to_read(url: str) -> bool:
    normalized = normalize_link(url)
    if normalized in _FREE_ACCESS_CACHE:
        return _FREE_ACCESS_CACHE[normalized]
    if not _is_safe_http_url(url) or _is_blocked_paywall_domain(url):
        _FREE_ACCESS_CACHE[normalized] = False
        return False

    try:
        host = urlsplit(url).netloc
        if _host_matches(host, settings.KNOWN_FREE_DOMAINS):
            _FREE_ACCESS_CACHE[normalized] = True
            return True

        response = requests.get(
            url,
            timeout=14,
            allow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                    "AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            },
        )
        if _is_blocked_paywall_domain(response.url) or response.status_code in {401, 402, 451}:
            _FREE_ACCESS_CACHE[normalized] = False
            return False
        if response.status_code >= 400:
            _FREE_ACCESS_CACHE[normalized] = False
            return False

        content_type = response.headers.get("Content-Type", "").lower()
        result = "html" not in content_type or not _looks_paywalled(response.text)
        _FREE_ACCESS_CACHE[normalized] = result
        return result
    except requests.RequestException as exc:
        print(f"[무료 원문 확인 실패 → 제외] {url}: {exc}")
        _FREE_ACCESS_CACHE[normalized] = False
        return False


def _clean_pick(pick: dict) -> dict:
    return {
        "title": strip_html(str(pick.get("title", "")))[:240],
        "link": str(pick.get("link", "")).strip(),
        "source": strip_html(str(pick.get("source", "")))[:80],
        "published": strip_html(str(pick.get("published", "unknown")))[:50] or "unknown",
        "section": str(pick.get("section", settings.SECTION_VALUES[0])),
        "category": str(pick.get("category", settings.CATEGORY_VALUES[0])),
        "content_type": str(pick.get("content_type", "기사")),
        "summary": strip_html(str(pick.get("summary", "")))[:220],
        "takeaway": strip_html(str(pick.get("takeaway", "")))[:140],
        "thumbnail": str(pick.get("thumbnail", "")).strip(),
    }


def _infer_category(candidate: dict) -> str:
    text = f"{candidate.get('title', '')} {candidate.get('summary', '')}".lower()
    for category, keywords in settings.CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return category
    return settings.CATEGORY_VALUES[0]


def _as_fallback_pick(candidate: dict) -> dict:
    summary = strip_html(candidate.get("summary", ""))
    if not summary:
        summary = "오늘의 주요 변화와 관련 당사자의 발표를 다룬 공개 콘텐츠입니다."
    return {
        "title": candidate["title"],
        "link": candidate["link"],
        "source": candidate["source"],
        "published": candidate.get("published", "unknown"),
        "section": candidate.get("section", settings.SECTION_VALUES[0]),
        "category": _infer_category(candidate),
        "content_type": CONTENT_TYPE_MAP.get(candidate.get("content_type", "news"), "기사"),
        "summary": summary[:190],
        "takeaway": "원문에서 핵심 근거와 다음 관전 포인트를 확인해보세요.",
        "thumbnail": candidate.get("thumbnail", ""),
    }


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
        link = pick["link"]
        if not _is_safe_http_url(link):
            continue
        link_key = normalize_link(link)
        if link_key in seen_links or link_key in excluded_links:
            continue
        if not _is_free_to_read(link):
            print(f"[무료 원문 제외] {link}")
            continue

        original = candidate_map.get(link_key)
        if original:
            pick["title"] = original["title"]
            pick["source"] = original["source"]
            pick["published"] = original.get("published", "unknown")
            pick["section"] = original.get("section", pick["section"])
            pick["thumbnail"] = original.get("thumbnail", "")
        elif not web_enabled:
            continue
        elif not web_source_urls or link_key not in web_source_urls:
            print(f"[제외] 웹 검색 출처로 확인되지 않은 URL: {link}")
            continue

        if not pick["title"] or not pick["summary"]:
            continue
        if pick["section"] not in settings.SECTION_VALUES:
            continue
        if pick["category"] not in settings.CATEGORY_VALUES:
            pick["category"] = _infer_category(pick)
        if pick["content_type"] not in settings.CONTENT_TYPE_VALUES:
            pick["content_type"] = "기타"
        if not pick["takeaway"]:
            pick["takeaway"] = "원문에서 핵심 근거와 다음 관전 포인트를 확인해보세요."

        seen_links.add(link_key)
        validated.append(pick)
    return validated


def _balanced_select(validated: list[dict], candidates: list[dict], excluded_links: set[str]) -> list[dict]:
    selected: list[dict] = []
    seen: set[str] = set()
    source_counts: dict[str, int] = {}

    def can_add(item: dict, relax_source: bool = False) -> bool:
        key = normalize_link(item.get("link", ""))
        source = item.get("source", "기타")
        section = item.get("section", settings.SECTION_VALUES[0])
        if not key or key in seen or key in excluded_links:
            return False
        if not relax_source and source_counts.get(source, 0) >= settings.MAX_PER_SOURCE_FINAL:
            return False
        section_maximums = getattr(settings, "SECTION_MAXIMUMS", {})
        section_max = section_maximums.get(section)
        if section_max is not None:
            section_count = sum(1 for selected_item in selected if selected_item.get("section") == section)
            if section_count >= section_max:
                return False
        return True

    def add(item: dict, relax_source: bool = False) -> bool:
        if not can_add(item, relax_source=relax_source):
            return False
        key = normalize_link(item["link"])
        selected.append(item)
        seen.add(key)
        source = item.get("source", "기타")
        source_counts[source] = source_counts.get(source, 0) + 1
        return True

    # 모델 순서를 유지하면서 섹션별 목표 수를 먼저 채웁니다.
    for section in settings.SECTION_VALUES:
        target = settings.SECTION_TARGETS.get(section, 0)
        count = 0
        for item in validated:
            if item.get("section") == section and add(item):
                count += 1
            if count >= target:
                break

    # 부족한 섹션은 RSS 후보로 보충합니다.
    section_counts = {section: sum(1 for item in selected if item.get("section") == section) for section in settings.SECTION_VALUES}
    for section in settings.SECTION_VALUES:
        target = settings.SECTION_TARGETS.get(section, 0)
        if section_counts.get(section, 0) >= target:
            continue
        for candidate in candidates:
            if candidate.get("section") != section:
                continue
            if normalize_link(candidate.get("link", "")) in excluded_links:
                continue
            if not _is_free_to_read(candidate["link"]):
                continue
            if add(_as_fallback_pick(candidate)):
                section_counts[section] = section_counts.get(section, 0) + 1
            if section_counts[section] >= target:
                break

    # 모델의 나머지 결과로 전체 기사 수를 채웁니다.
    for item in validated:
        add(item)
        if len(selected) >= settings.PICK_COUNT:
            break

    # 그래도 부족하면 RSS 후보를 사용합니다.
    if len(selected) < settings.PICK_COUNT:
        for candidate in candidates:
            if normalize_link(candidate.get("link", "")) in excluded_links:
                continue
            if not _is_free_to_read(candidate["link"]):
                continue
            add(_as_fallback_pick(candidate))
            if len(selected) >= settings.PICK_COUNT:
                break

    # 경제 브리핑은 시장 관련 항목을 최소 2개 확보합니다.
    if settings.DOMAIN_ID == "economy":
        market_categories = {"주식·시장", "환율·원자재"}
        market_count = sum(1 for item in selected if item.get("category") in market_categories)
        if market_count < 2:
            for candidate in candidates:
                fallback = _as_fallback_pick(candidate)
                if fallback["category"] not in market_categories or not can_add(fallback):
                    continue
                # 마지막 비시장 항목을 교체하되 섹션 최소치가 깨지지 않게 합니다.
                for index in range(len(selected) - 1, -1, -1):
                    old = selected[index]
                    if old.get("category") in market_categories:
                        continue
                    old_section = old.get("section")
                    old_section_count = sum(1 for item in selected if item.get("section") == old_section)
                    if old_section_count <= settings.SECTION_MINIMUMS.get(old_section, 0):
                        continue
                    old_key = normalize_link(old["link"])
                    old_source = old.get("source", "기타")
                    seen.discard(old_key)
                    source_counts[old_source] = max(0, source_counts.get(old_source, 1) - 1)
                    selected.pop(index)
                    add(fallback)
                    market_count += 1
                    break
                if market_count >= 2:
                    break

    return selected[: settings.PICK_COUNT]


def _error_code(response: requests.Response) -> tuple[str, str]:
    try:
        error = (response.json() or {}).get("error") or {}
        return str(error.get("code") or ""), str(error.get("message") or "")
    except Exception:
        return "", response.text[:500]


def _post_with_backoff(payload: dict) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 없습니다.")

    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = requests.post(
                OPENAI_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=240,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 3:
                raise
            wait = 8 * (2 ** attempt) + random.uniform(0, 3)
            print(f"[OpenAI 재시도] 네트워크 오류, {wait:.1f}초 후 재시도: {exc}")
            time.sleep(wait)
            continue

        if 200 <= response.status_code < 300:
            return response.json()

        code, message = _error_code(response)
        quota_words = ("insufficient quota", "credit", "billing", "hard limit", "spend limit")
        quota_problem = code in {
            "insufficient_quota", "billing_hard_limit_reached", "billing_not_active",
        } or any(word in message.lower() for word in quota_words)
        if response.status_code == 429 and quota_problem:
            raise OpenAIQuotaError(
                "OpenAI API 크레딧 또는 결제 한도가 부족합니다. "
                f"대시보드의 Usage/Credits를 확인하세요. ({code or '429'}: {message})"
            )

        retryable = response.status_code == 429 or response.status_code >= 500
        error = requests.HTTPError(
            f"{response.status_code} {response.reason}: {message or response.text[:300]}",
            response=response,
        )
        last_error = error
        if not retryable or attempt == 3:
            raise error

        retry_after = response.headers.get("Retry-After", "")
        try:
            wait = float(retry_after)
        except ValueError:
            wait = 12 * (2 ** attempt) + random.uniform(0, 4)
        wait = min(wait, 90)
        print(f"[OpenAI 재시도] HTTP {response.status_code}, {wait:.1f}초 후 {attempt + 2}/4회 시도")
        time.sleep(wait)

    if last_error:
        raise last_error
    raise OpenAIResponseError("OpenAI 요청이 실패했습니다.")


def _request_openai(candidates: list[dict], web_enabled: bool, excluded_links: set[str]) -> tuple[dict, set[str]]:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    user_prompt = f"""오늘은 한국시간 {today}입니다.
아래 RSS/Atom 후보를 먼저 검토하고, 웹 검색이 활성화되어 있으면 공개 웹을 보완 탐색하세요.
{settings.WEB_DISCOVERY_PROMPT}

최근 소개 URL은 다시 선택하지 마세요.
최근 소개 URL JSON:
{json.dumps(sorted(excluded_links), ensure_ascii=False)}

후보 JSON:
{json.dumps(candidates, ensure_ascii=False)}
"""

    payload: dict = {
        "model": MODEL,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 5600 if settings.PICK_COUNT > 5 else 3600,
        "input": [
            {"role": "system", "content": settings.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": settings.OUTPUT_SCHEMA_NAME,
                "strict": True,
                "schema": _output_schema(),
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
                                settings.PAYWALL_BLOCKED_DOMAINS
                                | {"wikipedia.org", "namu.wiki", "reddit.com", "quora.com"}
                            )
                        },
                    }
                ],
                "tool_choice": "required",
                "include": ["web_search_call.action.sources"],
            }
        )

    data = _post_with_backoff(payload)
    return data, _extract_web_source_urls(data)


def select_articles(articles: list[dict], excluded_links: set[str] | None = None) -> list[dict]:
    excluded = {normalize_link(link) for link in (excluded_links or set()) if link}
    candidates = _prepare_candidates(articles)
    if not candidates:
        return []

    web_enabled = ENABLE_WEB_DISCOVERY
    try:
        data, web_source_urls = _request_openai(candidates, web_enabled=True, excluded_links=excluded) if web_enabled else _request_openai(candidates, web_enabled=False, excluded_links=excluded)
    except OpenAIQuotaError:
        raise
    except (requests.RequestException, OpenAIResponseError, ValueError, json.JSONDecodeError) as exc:
        if not web_enabled:
            raise
        print(f"[경고] 웹 탐색 포함 선별 실패 → RSS 전용으로 재시도: {exc}")
        data, web_source_urls = _request_openai(candidates, web_enabled=False, excluded_links=excluded)
        web_enabled = False

    parsed = json.loads(_extract_output_text(data))
    raw_picks = parsed.get("picks", [])
    if not isinstance(raw_picks, list):
        raise OpenAIResponseError("picks가 배열이 아닙니다.")

    validated = _validate_picks(raw_picks, candidates, web_source_urls, web_enabled, excluded)
    final = _balanced_select(validated, candidates, excluded)

    section_counts = {section: sum(1 for item in final if item.get("section") == section) for section in settings.SECTION_VALUES}
    for section, minimum in settings.SECTION_MINIMUMS.items():
        if section_counts.get(section, 0) < minimum:
            raise OpenAIResponseError(
                f"{section} 콘텐츠가 최소 {minimum}개에 미달했습니다: {section_counts.get(section, 0)}개"
            )
    if len(final) < settings.MIN_PICKS:
        raise OpenAIResponseError(f"최종 선별 결과가 {len(final)}개로 최소 {settings.MIN_PICKS}개에 미달했습니다.")

    print(
        f"[선별 완료] {len(final)}건 (모델: {MODEL}, 웹 탐색: {'사용' if web_enabled else '미사용'}, "
        + ", ".join(f"{section} {count}" for section, count in section_counts.items())
        + ")"
    )
    return final


# 기존 프로젝트의 함수명과 비슷하게 유지합니다.
def select_top(articles: list[dict], excluded_links: set[str] | None = None) -> list[dict]:
    return select_articles(articles, excluded_links=excluded_links)

def select_fallback(articles: list[dict], excluded_links: set[str] | None = None) -> list[dict]:
    """OpenAI가 중단되어도 공개 RSS 후보만으로 균형 잡힌 브리핑을 만듭니다.

    요약은 피드가 제공한 설명을 사용하므로 AI 요약보다 거칠 수 있지만,
    GitHub Actions 전체가 실패해 사이트가 멈추는 것보다는 안전합니다.
    """
    excluded = {normalize_link(link) for link in (excluded_links or set()) if link}
    candidates = _prepare_candidates(articles)
    final = _balanced_select([], candidates, excluded)
    if len(final) < settings.MIN_PICKS and excluded:
        print("[RSS 폴백] 최근 중복 제한으로 후보가 부족해 중복 제한을 완화합니다.")
        final = _balanced_select([], candidates, set())
    section_counts = {
        section: sum(1 for item in final if item.get("section") == section)
        for section in settings.SECTION_VALUES
    }
    print(
        "[RSS 폴백 완료] "
        + f"{len(final)}건 / "
        + ", ".join(f"{section} {count}" for section, count in section_counts.items())
    )
    return final[: settings.PICK_COUNT]

