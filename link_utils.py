"""기사 URL 정리와 중복 판별에 공통으로 사용하는 도구."""

from __future__ import annotations

import html
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 클릭에 필요하지 않은 마케팅/추적 파라미터입니다.
# RSS가 잘못 인코딩한 utm_campaign 값은 매체 측 리디렉션 루프를 만들 수 있으므로,
# 중복 판별뿐 아니라 실제로 공개하는 링크에서도 제거합니다.
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "_hsenc",
    "_hsmi",
    "igshid",
    "mkt_tok",
    "vero_conv",
    "vero_id",
    "oly_anon_id",
    "oly_enc_id",
    "wickedid",
    "yclid",
    "ttclid",
    "twclid",
}


def _is_tracking_query_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    return normalized.startswith(TRACKING_QUERY_PREFIXES) or normalized in TRACKING_QUERY_KEYS


def clean_public_link(url: str) -> str:
    """사용자에게 공개할 URL에서 추적 파라미터와 fragment만 안전하게 제거합니다.

    기사 식별에 필요한 일반 파라미터(예: ``idxno`` 또는 YouTube의 ``v``)는
    그대로 보존합니다. 이 함수의 반환값을 실제 카드 링크로 사용해야 합니다.
    """
    raw = html.unescape(str(url or "").strip())
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"} or not parts.netloc:
            return raw
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking_query_key(key)
        ]
        return urlunsplit(
            (
                scheme,
                parts.netloc,
                parts.path or "/",
                urlencode(query, doseq=True),
                "",
            )
        )
    except (TypeError, ValueError):
        return raw


def normalize_link(url: str) -> str:
    """중복 판별용 URL 정규화. 공개용 링크 정리 후 호스트·경로를 통일합니다."""
    cleaned = clean_public_link(url)
    try:
        parts = urlsplit(cleaned)
        query = sorted(parse_qsl(parts.query, keep_blank_values=True))
        path = parts.path.rstrip("/") or "/"
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return urlunsplit(
            (parts.scheme.lower(), netloc, path, urlencode(query, doseq=True), "")
        )
    except (TypeError, ValueError):
        return cleaned
