"""스타트업 생태계 콘텐츠 수집 모듈.

뉴스 기사뿐 아니라 인터뷰, 창업가/VC 관점 글, 실무 인사이트,
유튜브 영상까지 함께 후보군으로 수집합니다.

수집 전략
- 속보성 뉴스: 최근 36시간 안팎
- 인터뷰/인사이트/영상: 발행 주기가 느리므로 최근 7~14일
- 실제 최종 선별은 select_news.py에서 다양성·품질 기준으로 수행
"""

from __future__ import annotations

import calendar
import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

KST = timezone(timedelta(hours=9))

# source_group:
# - news: 생태계 업데이트 중심의 속보/기사
# - insight: 인터뷰, 칼럼, 분석, 실무 노하우
# - video: 창업가/VC 인터뷰 및 강연 영상
#
# lookback_hours를 소스별로 다르게 둔 이유:
# 뉴스는 신선도가 중요하지만, 깊이 있는 인터뷰·영상은 매일 발행되지 않기 때문입니다.
FEEDS = [
    {
        "source": "플래텀",
        "url": "https://platum.kr/feed",
        "source_group": "news",
        "lookback_hours": 36,
    },
    {
        "source": "벤처스퀘어",
        "url": "https://www.venturesquare.net/feed",
        "source_group": "news",
        "lookback_hours": 36,
    },
    {
        "source": "스타트업레시피",
        "url": "https://startuprecipe.co.kr/feed",
        "source_group": "news",
        "lookback_hours": 36,
    },
    {
        "source": "바이라인네트워크",
        "url": "https://byline.network/feed/",
        "source_group": "news",
        "lookback_hours": 48,
    },
    {
        "source": "블로터",
        "url": "https://www.bloter.net/rss/allArticle.xml",
        "source_group": "news",
        "lookback_hours": 48,
    },
    {
        "source": "지디넷",
        "url": "https://zdnet.co.kr/Include/rss.xml",
        "source_group": "news",
        "lookback_hours": 48,
    },
    # 유료 구독이 필요한 매체는 후보군에 넣지 않습니다.
    # 심층 콘텐츠는 무료 공개 웹 검색과 a16z·EO Korea 등 공개 소스로 보완합니다.
    # 해외 VC/창업 실무 인사이트. 하루 5개 중 해외 콘텐츠는 최대 2개만 뽑습니다.
    {
        "source": "a16z",
        "url": "https://www.a16z.news/feed",
        "source_group": "insight",
        "lookback_hours": 168,
    },
    # EO Korea 공식 유튜브 채널 RSS
    {
        "source": "EO Korea",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCQ2DWm5Md16Dc3xRwwhVE7Q",
        "source_group": "video",
        "lookback_hours": 168,
    },
]

# 전문 스타트업 매체/큐레이션 소스는 기본 통과시키되, 종합 매체는 아래 키워드로
# 관련성을 확인합니다. 투자 용어뿐 아니라 제품·조직·시장·창업가 관점을 넓게 포함합니다.
RELEVANCE_KEYWORDS = [
    "스타트업", "창업", "창업가", "창업자", "대표", "기업가", "벤처", "vc",
    "심사역", "액셀러레이터", "유니콘", "투자", "시리즈", "시드", "m&a", "ipo",
    "제품", "프로덕트", "pmf", "고객", "사용자", "그로스", "성장", "리텐션",
    "가격", "수익화", "비즈니스 모델", "사업 전략", "gtm", "go-to-market",
    "조직", "리더십", "채용", "팀빌딩", "커리어", "인터뷰", "인사이트", "칼럼",
    "saas", "ai", "인공지능", "플랫폼", "핀테크", "커머스", "딥테크", "로봇",
    "시장", "산업", "트렌드", "정책", "규제", "지원사업", "데모데이",
    "founder", "startup", "venture capital", "product", "growth", "retention",
    "leadership", "strategy", "market", "pricing", "customer", "interview",
]

# 제목만 봐도 단순 모집/홍보에 가까운 콘텐츠는 후보 단계에서 약하게 거릅니다.
# 다만 정책·지원사업 자체가 실질적으로 유용한 경우는 제외하지 않습니다.
LOW_VALUE_TITLE_PATTERNS = [
    r"기자단\s*모집",
    r"서포터즈\s*모집",
    r"체험단\s*모집",
    r"이벤트\s*(진행|오픈)",
    r"할인\s*(행사|이벤트)",
    r"경품",
]

PROFESSIONAL_SOURCES = {
    "플래텀",
    "벤처스퀘어",
    "스타트업레시피",
    "a16z",
    "EO Korea",
}

TRACKING_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")
MAX_PER_SOURCE = 20


def strip_html(value: str) -> str:
    """피드 HTML을 짧고 읽을 수 있는 일반 텍스트로 정리합니다."""
    value = html_lib.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_link(url: str) -> str:
    """중복 판별용 URL 정규화. 추적 파라미터와 fragment를 제거합니다."""
    try:
        parts = urlsplit(url.strip())
        query = sorted([
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith(TRACKING_QUERY_PREFIXES)
        ])
        path = parts.path.rstrip("/") or "/"
        netloc = parts.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return urlunsplit(
            (parts.scheme.lower(), netloc, path, urlencode(query), "")
        )
    except Exception:
        return url.strip()


def _entry_datetime(entry: dict) -> datetime | None:
    """feedparser entry의 발행 시각을 KST datetime으로 변환합니다."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        timestamp = calendar.timegm(parsed)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(KST)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_low_value_title(title: str) -> bool:
    return any(re.search(pattern, title, flags=re.I) for pattern in LOW_VALUE_TITLE_PATTERNS)


def is_relevant(title: str, summary: str, source: str, source_group: str) -> bool:
    """종합 매체의 잡음을 줄이고, 전문/인사이트 소스는 폭넓게 통과시킵니다."""
    if _is_low_value_title(title):
        return False

    if source in PROFESSIONAL_SOURCES or source_group in {"insight", "video"}:
        return True

    text = f"{title} {summary}".lower()
    return any(keyword.lower() in text for keyword in RELEVANCE_KEYWORDS)


def guess_content_type(title: str, link: str, source_group: str) -> str:
    """모델이 후보 다양성을 판단할 때 쓸 1차 콘텐츠 유형 추정값입니다."""
    text = title.lower()
    host = urlsplit(link).netloc.lower()

    if source_group == "video" or "youtube.com" in host or "youtu.be" in host:
        return "video"
    if "linkedin.com" in host:
        return "linkedin"
    if any(keyword in text for keyword in ("인터뷰", "만나다", "대담", "interview", "q&a")):
        return "interview"
    if source_group == "insight" or any(
        keyword in text
        for keyword in (
            "인사이트", "칼럼", "분석", "리포트", "전략", "노하우", "how to",
            "guide", "playbook", "framework", "lessons", "why", "how",
        )
    ):
        return "insight"
    return "news"


def _title_key(title: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", title.lower())


def _entry_summary(entry: dict) -> str:
    """피드마다 다른 본문/요약 필드를 안전하게 하나의 문자열로 합칩니다."""
    direct = entry.get("summary") or entry.get("description")
    if direct:
        return str(direct)

    content = entry.get("content") or []
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return str(first.get("value", ""))
    return ""


def _youtube_video_id(url: str) -> str | None:
    """YouTube URL에서 영상 ID를 추출합니다."""
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
    """Atom/RSS의 media:thumbnail 등을 우선 사용하고 YouTube는 공식 썸네일 URL로 보완합니다."""
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
                    key == "media_thumbnail"
                    or medium == "image"
                    or content_type.startswith("image/")
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


def collect_articles(hours: int = 36) -> list[dict]:
    """여러 RSS/Atom 피드에서 뉴스·인터뷰·인사이트·영상을 수집합니다.

    `hours`는 일반 뉴스의 기본 범위입니다. 각 소스에 `lookback_hours`가 있으면
    해당 값을 우선 사용합니다.
    """
    now = datetime.now(KST)
    articles: list[dict] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()

    for config in FEEDS:
        source = config["source"]
        url = config["url"]
        source_group = config["source_group"]
        lookback_hours = int(config.get("lookback_hours", hours))
        cutoff = now - timedelta(hours=lookback_hours)

        try:
            feed = feedparser.parse(
                url,
                request_headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SNAACBriefingBot/2.0)"
                },
            )
        except Exception as exc:
            print(f"[경고] {source} 피드 수집 실패: {exc}")
            continue

        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            print(f"[경고] {source} 피드 파싱 실패: {getattr(feed, 'bozo_exception', '')}")
            continue

        source_count = 0
        for entry in feed.entries:
            if source_count >= MAX_PER_SOURCE:
                break

            published_at = _entry_datetime(entry)
            if published_at and published_at < cutoff:
                continue

            title = strip_html(entry.get("title", ""))
            link = (entry.get("link") or "").strip()
            raw_summary = _entry_summary(entry)
            summary = strip_html(raw_summary)[:700]
            author = strip_html(entry.get("author", ""))[:100]
            thumbnail = _entry_thumbnail(entry, link)

            if not title or not link:
                continue
            if not link.startswith(("http://", "https://")):
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

            content_type = guess_content_type(title, link, source_group)
            articles.append(
                {
                    "source": source,
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published": published_at.isoformat() if published_at else "unknown",
                    "author": author,
                    "source_group": source_group,
                    "content_type": content_type,
                    "thumbnail": thumbnail,
                    "lookback_hours": lookback_hours,
                }
            )
            source_count += 1

    # 날짜가 없는 항목은 뒤로, 나머지는 최신순으로 정렬합니다.
    def sort_key(article: dict) -> tuple[int, str]:
        published = article.get("published", "unknown")
        return (published != "unknown", published)

    articles.sort(key=sort_key, reverse=True)
    print(f"[수집 완료] 총 {len(articles)}건 / 뉴스·인사이트·영상 통합")
    return articles


if __name__ == "__main__":
    for item in collect_articles():
        print(
            f"- [{item['source']}/{item['content_type']}] "
            f"{item['title']} ({item['published']})"
        )
