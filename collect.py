"""RSS/Atom 기반 콘텐츠 수집 모듈.

도메인별 수집원과 키워드는 settings.py에서 관리합니다.
"""

from __future__ import annotations

import calendar
import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

import settings

KST = timezone(timedelta(hours=9))
TRACKING_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref")
MAX_PER_SOURCE = 18


def strip_html(value: str) -> str:
    value = html_lib.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_link(url: str) -> str:
    """중복 판별용 URL 정규화."""
    try:
        parts = urlsplit(url.strip())
        query = sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not any(key.lower().startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES)
        )
        path = parts.path.rstrip("/") or "/"
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))
    except Exception:
        return url.strip()


def _entry_datetime(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc).astimezone(KST)
    except (TypeError, ValueError, OverflowError):
        return None


def _entry_summary(entry: dict) -> str:
    direct = entry.get("summary") or entry.get("description")
    if direct:
        return str(direct)
    content = entry.get("content") or []
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return str(first.get("value", ""))
    return ""


def _title_key(title: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", title.lower())


def _is_low_value_title(title: str) -> bool:
    return any(re.search(pattern, title, flags=re.I) for pattern in settings.LOW_VALUE_TITLE_PATTERNS)


def is_relevant(title: str, summary: str, source: str, source_group: str) -> bool:
    if _is_low_value_title(title):
        return False
    if source in settings.PROFESSIONAL_SOURCES or source_group in {"official", "analysis", "market"}:
        return True
    text = f"{title} {summary}".lower()
    return any(keyword.lower() in text for keyword in settings.RELEVANCE_KEYWORDS)


def guess_content_type(title: str, link: str, source_group: str) -> str:
    text = title.lower()
    host = urlsplit(link).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "video"
    if source_group == "official":
        return "official"
    if source_group == "analysis" or any(
        term in text for term in ("분석", "리포트", "해설", "interview", "analysis", "report")
    ):
        return "analysis"
    return "news"


def _youtube_video_id(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        host = parts.netloc.lower().split(":")[0]
        path_parts = [part for part in parts.path.split("/") if part]
        if host in {"youtu.be", "www.youtu.be"} and path_parts:
            return path_parts[0]
        if host.endswith("youtube.com"):
            if parts.path == "/watch":
                return (parse_qs(parts.query).get("v") or [None])[0]
            if path_parts and path_parts[0] in {"shorts", "embed", "live"}:
                return path_parts[1] if len(path_parts) > 1 else None
    except Exception:
        return None
    return None


def _entry_thumbnail(entry: dict, link: str) -> str:
    for key in ("media_thumbnail", "media_content"):
        values = entry.get(key) or []
        if isinstance(values, dict):
            values = [values]
        if isinstance(values, list):
            for value in values:
                if not isinstance(value, dict):
                    continue
                url = str(value.get("url", "")).strip()
                medium = str(value.get("medium", "")).lower()
                content_type = str(value.get("type", "")).lower()
                if url.startswith(("http://", "https://")) and (
                    key == "media_thumbnail" or medium == "image" or content_type.startswith("image/")
                ):
                    return url

    image = entry.get("image")
    if isinstance(image, dict):
        url = str(image.get("href") or image.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            return url

    video_id = _youtube_video_id(link)
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return ""


def collect_articles(hours: int | None = None) -> list[dict]:
    """settings.FEEDS에서 최신 후보를 모읍니다."""
    now = datetime.now(KST)
    default_hours = hours or settings.DEFAULT_LOOKBACK_HOURS
    articles: list[dict] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()

    for config in settings.FEEDS:
        source = config["source"]
        url = config["url"]
        source_group = config.get("source_group", "news")
        section = config.get("section", settings.SECTION_VALUES[0])
        lookback_hours = int(config.get("lookback_hours", default_hours))
        cutoff = now - timedelta(hours=lookback_hours)

        try:
            feed = feedparser.parse(
                url,
                request_headers={
                    "User-Agent": f"Mozilla/5.0 (compatible; {settings.DOMAIN_ID.title()}BriefingBot/1.0)"
                },
            )
        except Exception as exc:
            print(f"[경고] {source} 피드 수집 실패: {exc}")
            continue

        entries = list(getattr(feed, "entries", []) or [])
        if getattr(feed, "bozo", False):
            print(f"[경고] {source} 피드 파싱 경고: {getattr(feed, 'bozo_exception', '')}")
        if not entries:
            continue

        source_count = 0
        for entry in entries:
            if source_count >= MAX_PER_SOURCE:
                break

            published_at = _entry_datetime(entry)
            if published_at and published_at < cutoff:
                continue

            title = strip_html(entry.get("title", ""))
            link = str(entry.get("link") or "").strip()
            summary = strip_html(_entry_summary(entry))[:700]
            author = strip_html(str(entry.get("author", "")))[:100]

            if not title or not link.startswith(("http://", "https://")):
                continue
            if not is_relevant(title, summary, source, source_group):
                continue

            link_key = normalize_link(link)
            title_key = _title_key(title)
            if link_key in seen_links or (title_key and title_key in seen_titles):
                continue

            seen_links.add(link_key)
            if title_key:
                seen_titles.add(title_key)

            articles.append(
                {
                    "source": source,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published_at.isoformat() if published_at else "unknown",
                    "author": author,
                    "source_group": source_group,
                    "section": section,
                    "content_type": guess_content_type(title, link, source_group),
                    "thumbnail": _entry_thumbnail(entry, link),
                    "lookback_hours": lookback_hours,
                }
            )
            source_count += 1

    def sort_key(article: dict) -> tuple[int, str]:
        published = article.get("published", "unknown")
        return (published != "unknown", published)

    articles.sort(key=sort_key, reverse=True)
    print(f"[수집 완료] 총 {len(articles)}건 / {settings.SITE_KOREAN_NAME}")
    return articles


if __name__ == "__main__":
    for item in collect_articles():
        print(f"- [{item['section']} / {item['source']}] {item['title']}")
