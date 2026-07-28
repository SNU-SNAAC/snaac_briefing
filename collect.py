"""스타트업 생태계 뉴스 수집 모듈.

주요 스타트업 매체의 RSS 피드에서 지난 24시간 내 기사를 수집합니다.
"""

import time
from datetime import datetime, timedelta, timezone

import feedparser

KST = timezone(timedelta(hours=9))

# 스타트업 생태계 주요 매체 RSS 피드
# 피드가 죽거나 매체가 바뀌면 여기만 수정하면 됩니다.
FEEDS = {
    "플래텀": "https://platum.kr/feed",
    "벤처스퀘어": "https://www.venturesquare.net/feed",
    "스타트업레시피": "https://startuprecipe.co.kr/feed",
    "바이라인네트워크": "https://byline.network/feed/",
    "블로터": "https://www.bloter.net/rss/allArticle.xml",
    "지디넷 스타트업": "https://zdnet.co.kr/Include/rss.xml",
}

# 스타트업 관련성 필터 키워드 (종합지 피드에서 잡음 제거용)
KEYWORDS = [
    "스타트업", "투자", "유치", "시리즈", "시드", "프리A", "VC", "벤처",
    "액셀러레이터", "창업", "유니콘", "M&A", "인수", "IPO", "상장",
    "펀드", "테크", "AI", "사스", "SaaS", "플랫폼", "핀테크", "데모데이",
]


def is_relevant(title: str, summary: str, source: str) -> bool:
    """종합 매체 기사의 스타트업 관련성 판단. 전문 매체는 통과."""
    if source in ("플래텀", "벤처스퀘어", "스타트업레시피"):
        return True
    text = f"{title} {summary}"
    return any(k.lower() in text.lower() for k in KEYWORDS)


def collect_articles(hours: int = 24) -> list[dict]:
    """지난 `hours`시간 내 기사를 수집해 리스트로 반환."""
    cutoff = datetime.now(KST) - timedelta(hours=hours)
    articles = []
    seen_titles = set()

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[경고] {source} 피드 수집 실패: {e}")
            continue

        for entry in feed.entries:
            # 발행 시각 파싱
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                pub_dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc).astimezone(KST)
                if pub_dt < cutoff:
                    continue
            else:
                pub_dt = None  # 시각 정보 없으면 일단 포함 (선별 단계에서 걸러짐)

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "")[:300]

            if not title or not link:
                continue
            # 제목 기반 중복 제거 (여러 매체가 같은 뉴스를 다루는 경우는 남김)
            key = title.lower()
            if key in seen_titles:
                continue
            if not is_relevant(title, summary, source):
                continue

            seen_titles.add(key)
            articles.append({
                "source": source,
                "title": title,
                "link": link,
                "summary": summary,
                "published": pub_dt.isoformat() if pub_dt else "unknown",
            })

    print(f"[수집 완료] 총 {len(articles)}건")
    return articles


if __name__ == "__main__":
    for a in collect_articles():
        print(f"- [{a['source']}] {a['title']}")
