"""브리핑 웹페이지 생성 모듈.

선별된 기사 5개로 모바일 최적화 브리핑 페이지(docs/index.html)를 생성합니다.
GitHub Pages(main 브랜치 /docs 폴더)로 배포되어, 오픈채팅봇 반복알림의
고정 링크가 항상 '오늘의 브리핑'을 가리키게 됩니다.

저작권 참고:
- 썸네일은 각 기사의 OG 이미지를 '핫링크'(원본 서버 주소 그대로 표시)만 하고
  다운로드/저장하지 않습니다. 메신저 링크 미리보기와 같은 방식입니다.
- 부담스러우면 SHOW_THUMBNAILS = False 로 끄면 매체 이니셜 카드로 대체됩니다.
"""

import html
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

SHOW_THUMBNAILS = True   # 기사 OG 이미지 핫링크 표시 여부
DOCS_DIR = Path("docs")
ARCHIVE_KEEP = 14        # 하단에 노출할 지난 브리핑 개수

# 매체별 카드 색상 (썸네일 없을 때 폴백)
SOURCE_COLORS = {
    "플래텀": "#1B4DAB", "벤처스퀘어": "#0E7A5F", "스타트업레시피": "#B4560F",
    "바이라인네트워크": "#5B2D8F", "블로터": "#8F2D46", "지디넷 스타트업": "#2D6B8F",
}


def fetch_og_image(url: str) -> str | None:
    """기사 페이지에서 og:image URL만 추출 (이미지 자체는 저장하지 않음)."""
    try:
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SNAACBriefingBot/1.0)"},
        )
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text, re.IGNORECASE,
        ) or re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            resp.text, re.IGNORECASE,
        )
        if m:
            img = m.group(1)
            return img if img.startswith("http") else None
    except Exception as e:
        print(f"[썸네일 스킵] {url}: {e}")
    return None


def _card(i: int, p: dict) -> str:
    color = SOURCE_COLORS.get(p["source"], "#3A4A66")
    title = html.escape(p["title"])
    summary = html.escape(p["summary"])
    source = html.escape(p["source"])
    link = html.escape(p["link"], quote=True)

    img_url = fetch_og_image(p["link"]) if SHOW_THUMBNAILS else None
    if img_url:
        thumb = (
            f'<div class="thumb"><img src="{html.escape(img_url, quote=True)}" alt="" '
            f'loading="lazy" onerror="this.parentElement.classList.add(\'noimg\');'
            f'this.parentElement.style.setProperty(\'--c\',\'{color}\');'
            f'this.parentElement.dataset.initial=\'{source[0]}\';this.remove()"></div>'
        )
    else:
        thumb = (
            f'<div class="thumb noimg" style="--c:{color}" data-initial="{source[0]}"></div>'
        )

    return f"""
    <a class="card" href="{link}" target="_blank" rel="noopener">
      {thumb}
      <div class="body">
        <div class="meta"><span class="tag" style="--c:{color}">{source}</span><span class="idx">{i}/5</span></div>
        <h2>{title}</h2>
        <p>{summary}</p>
        <span class="go">원문 읽기 →</span>
      </div>
    </a>"""


def _archive_links(today_slug: str) -> str:
    """docs/archive 폴더를 스캔해 지난 브리핑 링크 목록 생성."""
    archive_dir = DOCS_DIR / "archive"
    if not archive_dir.exists():
        return ""
    slugs = sorted(
        (f.stem for f in archive_dir.glob("*.html") if f.stem != today_slug),
        reverse=True,
    )[:ARCHIVE_KEEP]
    if not slugs:
        return ""
    items = "".join(
        f'<a href="archive/{s}.html">{s[5:7].lstrip("0")}/{s[8:10].lstrip("0")}</a>'
        for s in slugs
    )
    return f'<section class="archive"><h3>지난 브리핑</h3><div class="chips">{items}</div></section>'


def build_page(picks: list[dict]) -> None:
    now = datetime.now(KST)
    date_big = f"{now.month}.{now.day}"
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    slug = now.strftime("%Y-%m-%d")

    cards = "".join(_card(i, p) for i, p in enumerate(picks, 1))

    page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SNAAC 모닝 브리핑 · {date_label}</title>
<meta property="og:title" content="SNAAC 모닝 브리핑">
<meta property="og:description" content="매일 아침 9시, 스타트업 생태계 주요 소식 5가지">
<meta name="description" content="SNAAC이 고른 오늘의 스타트업 뉴스 5가지">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff" rel="preload" as="font" type="font/woff" crossorigin>
<style>
@font-face{{font-family:'GmarketSans';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff');font-weight:700;font-display:swap}}
:root{{
  --sky:#F2F5FA; --ink:#14213D; --sub:#5A6880;
  --amber:#F59F00; --line:#DDE4EF; --card:#FFFFFF;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{background:var(--sky);color:var(--ink);font-family:Pretendard,-apple-system,sans-serif;line-height:1.55}}
.wrap{{max-width:560px;margin:0 auto;padding:0 18px 60px}}

/* ── 마스트헤드: 날짜가 주인공 ── */
header{{padding:34px 0 10px;border-bottom:2px solid var(--ink);position:relative}}
.club{{font-family:GmarketSans,Pretendard,sans-serif;font-size:13px;letter-spacing:.22em;color:var(--sub)}}
.date-big{{font-family:GmarketSans,Pretendard,sans-serif;font-size:clamp(56px,17vw,84px);line-height:1;margin:6px 0 2px;letter-spacing:-.02em}}
.date-big em{{font-style:normal;color:var(--amber)}}
.date-sub{{font-size:14px;color:var(--sub);padding-bottom:16px}}
.stamp{{position:absolute;right:0;top:38px;width:74px;height:74px;border:2px solid var(--amber);border-radius:50%;
  display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--amber);
  font-family:GmarketSans,sans-serif;font-size:11px;letter-spacing:.06em;transform:rotate(8deg);background:transparent}}
.stamp b{{font-size:16px}}
.intro{{font-size:14px;color:var(--sub);padding:14px 0 22px}}

/* ── 기사 카드 ── */
.card{{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  margin-bottom:16px;text-decoration:none;color:inherit;transition:transform .12s ease,box-shadow .12s ease}}
.card:active{{transform:scale(.985)}}
.thumb{{aspect-ratio:16/8;background:#E8EDF5;overflow:hidden}}
.thumb img{{width:100%;height:100%;object-fit:cover;display:block}}
.thumb.noimg{{display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,var(--c),color-mix(in srgb,var(--c) 55%,#fff))}}
.thumb.noimg::after{{content:attr(data-initial);font-family:GmarketSans,sans-serif;font-size:44px;color:rgba(255,255,255,.9)}}
.body{{padding:16px 18px 18px}}
.meta{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.tag{{font-size:12px;font-weight:700;color:var(--c);border:1px solid color-mix(in srgb,var(--c) 40%,#fff);
  background:color-mix(in srgb,var(--c) 8%,#fff);padding:3px 9px;border-radius:99px}}
.idx{{font-family:GmarketSans,sans-serif;font-size:12px;color:var(--sub)}}
.card h2{{font-size:17.5px;font-weight:700;line-height:1.4;letter-spacing:-.01em;margin-bottom:7px;word-break:keep-all}}
.card p{{font-size:14px;color:var(--sub);word-break:keep-all}}
.go{{display:inline-block;margin-top:12px;font-size:13.5px;font-weight:700;color:var(--amber)}}

/* ── 아카이브 & 푸터 ── */
.archive{{margin-top:36px;padding-top:22px;border-top:1px solid var(--line)}}
.archive h3{{font-size:13px;color:var(--sub);font-weight:600;margin-bottom:10px}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chips a{{font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);background:#fff;
  padding:5px 12px;border-radius:99px}}
footer{{margin-top:40px;font-size:12px;color:var(--sub);text-align:center;line-height:1.8}}
@media (prefers-reduced-motion:reduce){{.card{{transition:none}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="club">SNAAC MORNING BRIEFING</div>
    <div class="date-big">{date_big}<em>.</em></div>
    <div class="date-sub">{date_label}</div>
    <div class="stamp">DAILY<b>AM 9</b>DROP</div>
  </header>
  <p class="intro">어제 스타트업 생태계에서 SNAAC이 고른 소식 {len(picks)}가지. 카드를 누르면 원문으로 이동해요.</p>
  {cards}
  {_archive_links(slug)}
  <footer>
    매일 아침 자동으로 업데이트됩니다 · SNAAC Community Team<br>
    본 페이지는 기사 원문 링크만 제공하며, 모든 기사의 저작권은 각 매체에 있습니다.
  </footer>
</div>
</body>
</html>"""

    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "archive").mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    # 아카이브 사본은 archive/ 폴더 안에 있으므로 내부 링크 경로 보정
    archive_page = page.replace('href="archive/', 'href="')
    (DOCS_DIR / "archive" / f"{slug}.html").write_text(archive_page, encoding="utf-8")
    print(f"[페이지 생성 완료] docs/index.html, docs/archive/{slug}.html")
