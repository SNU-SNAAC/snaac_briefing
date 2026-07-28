"""SNAAC 모닝 브리핑 정적 웹페이지 생성 모듈.

생성 파일
- docs/index.html: 오늘의 브리핑
- docs/archive/YYYY-MM-DD.html: 날짜별 브리핑 원본
- docs/archive/YYYY-MM-DD.json: 최근 중복 방지와 데이터 보관용
- docs/archive/index.html: 전체 지난 브리핑 목록

디자인 원칙
- 카카오톡 인앱 브라우저를 기준으로 한 모바일 우선 레이아웃
- 노란색/매체별 원색을 없앤 무채색 팔레트
- 썸네일까지 흑백 처리해 전체 톤 통일
- 카드 전체를 링크로 감싸지 않고, 원문 읽기와 저장 버튼을 분리
- 저장 기능은 localStorage를 사용하므로 별도 서버·DB·AI 토큰이 필요 없음
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

SHOW_THUMBNAILS = True
DOCS_DIR = Path("docs")
ARCHIVE_KEEP = 14

CSS = r"""
@font-face {
  font-family: 'GmarketSans';
  src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff');
  font-weight: 700;
  font-display: swap;
}

:root {
  --page: #f2f2f2;
  --surface: #ffffff;
  --surface-soft: #e9e9e9;
  --ink: #171717;
  --ink-2: #3f3f3f;
  --muted: #717171;
  --line: #d5d5d5;
  --line-strong: #b9b9b9;
  --shadow: 0 10px 30px rgba(20, 20, 18, .055);
  --radius: 18px;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--page);
  color: var(--ink);
  font-family: Pretendard, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 16px;
  line-height: 1.6;
  word-break: keep-all;
  overflow-wrap: break-word;
}
body.drawer-open { overflow: hidden; }
a { color: inherit; }
button, a { -webkit-tap-highlight-color: transparent; }
button { font: inherit; }
[hidden] { display: none !important; }

.wrap {
  width: min(100%, 600px);
  margin: 0 auto;
  padding: 0 18px calc(72px + env(safe-area-inset-bottom));
}

.masthead {
  padding: 18px 0 20px;
  border-bottom: 1px solid var(--ink);
}
.topline {
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
  text-decoration: none;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .16em;
  white-space: nowrap;
}
.brand-mark {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink);
}
.top-actions { display: flex; align-items: center; gap: 7px; }
.utility-button {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: transparent;
  color: var(--ink-2);
  text-decoration: none;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}
.utility-button:active { transform: scale(.98); }
.count-badge {
  min-width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--ink);
  color: #fff;
  font-size: 11px;
  line-height: 1;
}

.date-lockup {
  position: relative;
  padding: 28px 0 6px;
  min-height: 150px;
}
.kicker {
  margin: 0 0 9px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .14em;
  text-transform: uppercase;
}
.date-big {
  margin: 0;
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: clamp(58px, 18vw, 88px);
  line-height: .95;
  letter-spacing: -.055em;
}
.date-sub {
  margin-top: 12px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
}
.stamp {
  position: absolute;
  top: 27px;
  right: 2px;
  width: 76px;
  height: 76px;
  display: grid;
  place-content: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--ink-2);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 9px;
  line-height: 1.25;
  letter-spacing: .08em;
  text-align: center;
  transform: rotate(6deg);
}
.stamp strong { display: block; font-size: 15px; letter-spacing: 0; }

.intro {
  padding: 18px 0 8px;
}
.intro p {
  margin: 0;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1.65;
}
.editorial-rule {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 14px;
}
.editorial-rule span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 11.5px;
  font-weight: 700;
}

.cards { padding-top: 14px; }
.card {
  margin-bottom: 18px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.thumb {
  position: relative;
  display: block;
  aspect-ratio: 16 / 8.8;
  overflow: hidden;
  background: #dedede;
  text-decoration: none;
}
.thumb img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  filter: grayscale(100%) contrast(.92) brightness(.98);
  transform: scale(1.002);
}
.thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0, 0, 0, .12), transparent 42%);
  pointer-events: none;
}
.thumb.noimg {
  display: grid;
  place-items: center;
  background:
    linear-gradient(135deg, rgba(255,255,255,.52), transparent 55%),
    repeating-linear-gradient(135deg, #d6d6d6 0, #d6d6d6 12px, #e3e3e3 12px, #e3e3e3 24px);
}
.thumb.noimg::before {
  content: attr(data-initial);
  color: rgba(23, 23, 22, .72);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 44px;
  z-index: 1;
}
.media-label {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 2;
  min-height: 27px;
  display: inline-flex;
  align-items: center;
  padding: 0 9px;
  border: 1px solid rgba(255,255,255,.45);
  border-radius: 999px;
  background: rgba(20,20,18,.72);
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  backdrop-filter: blur(6px);
}
.card-body { padding: 17px 17px 18px; }
.card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.meta-left { min-width: 0; display: flex; align-items: center; gap: 8px; }
.category {
  max-width: 72vw;
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--ink);
  color: #fff;
  font-size: 11.5px;
  font-weight: 800;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.source {
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-index {
  flex: 0 0 auto;
  color: var(--muted);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 11px;
}
.title-link { text-decoration: none; }
.card h2 {
  margin: 0;
  font-size: clamp(18px, 4.8vw, 20px);
  line-height: 1.42;
  letter-spacing: -.025em;
}
.summary {
  margin: 10px 0 0;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1.68;
}
.takeaway {
  margin-top: 15px;
  padding: 13px 14px;
  border-left: 3px solid var(--ink);
  background: var(--surface-soft);
}
.takeaway-label {
  display: block;
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: .11em;
}
.takeaway p {
  margin: 0;
  color: var(--ink-2);
  font-size: 13.5px;
  line-height: 1.55;
}
.card-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 15px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}
.read-link {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--ink);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 800;
}
.read-link::after { content: '↗'; font-size: 15px; }
.save-button {
  min-width: 84px;
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 13px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: #fff;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.save-button svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.8; }
.save-button.is-saved { background: var(--ink); border-color: var(--ink); color: #fff; }
.save-button.is-saved svg { fill: currentColor; }
.save-button:active { transform: scale(.97); }

.archive-section {
  margin-top: 42px;
  padding-top: 24px;
  border-top: 1px solid var(--line-strong);
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}
.section-head h2 { margin: 0; font-size: 17px; letter-spacing: -.02em; }
.section-head a {
  color: var(--muted);
  font-size: 12.5px;
  font-weight: 700;
  text-decoration: none;
}
.archive-list {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
}
.archive-row {
  min-height: 58px;
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 11px;
  padding: 0 14px;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
}
.archive-row:last-child { border-bottom: 0; }
.archive-date { font-size: 14px; font-weight: 800; }
.archive-count { color: var(--muted); font-size: 12px; }
.archive-arrow { color: var(--muted); font-size: 15px; }
.empty-archive {
  padding: 22px 16px;
  color: var(--muted);
  font-size: 13px;
  text-align: center;
}

.archive-hero { padding: 32px 0 18px; border-bottom: 1px solid var(--ink); }
.archive-hero h1 {
  margin: 8px 0 6px;
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: clamp(35px, 10vw, 52px);
  line-height: 1.08;
  letter-spacing: -.045em;
}
.archive-hero p { margin: 0; color: var(--muted); font-size: 14px; }
.archive-page-list { margin-top: 22px; }

footer {
  margin-top: 44px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.8;
  text-align: center;
}

.drawer {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.drawer-backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(15, 15, 14, .48);
  cursor: pointer;
}
.drawer-panel {
  position: relative;
  width: min(100%, 600px);
  max-height: min(78vh, 720px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--line);
  border-bottom: 0;
  border-radius: 22px 22px 0 0;
  background: var(--surface);
  box-shadow: 0 -18px 50px rgba(0,0,0,.16);
  padding-bottom: env(safe-area-inset-bottom);
  animation: drawer-up .18s ease-out both;
}
@keyframes drawer-up { from { transform: translateY(18px); opacity: .5; } to { transform: translateY(0); opacity: 1; } }
.drawer-handle { width: 42px; height: 4px; margin: 9px auto 2px; border-radius: 999px; background: var(--line-strong); }
.drawer-head {
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 17px;
  border-bottom: 1px solid var(--line);
}
.drawer-head h2 { margin: 0; font-size: 17px; }
.close-button {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: #fff;
  color: var(--ink);
  font-size: 20px;
  cursor: pointer;
}
.saved-list { overflow-y: auto; overscroll-behavior: contain; padding: 8px 16px 18px; }
.saved-empty { padding: 44px 18px; color: var(--muted); font-size: 14px; text-align: center; }
.saved-item { padding: 14px 0; border-bottom: 1px solid var(--line); }
.saved-item:last-child { border-bottom: 0; }
.saved-meta { margin-bottom: 4px; color: var(--muted); font-size: 11.5px; font-weight: 700; }
.saved-title { display: block; color: var(--ink); text-decoration: none; font-size: 15px; font-weight: 800; line-height: 1.45; }
.saved-actions { display: flex; justify-content: flex-end; margin-top: 8px; }
.remove-saved {
  min-height: 36px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}

@media (hover: hover) {
  .card { transition: transform .16s ease, box-shadow .16s ease; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 14px 34px rgba(20,20,18,.085); }
  .thumb img { transition: filter .2s ease, transform .25s ease; }
  .card:hover .thumb img { filter: grayscale(82%) contrast(.96); transform: scale(1.018); }
  .utility-button:hover, .save-button:hover, .close-button:hover { border-color: var(--ink); }
}

@media (max-width: 390px) {
  .wrap { padding-left: 14px; padding-right: 14px; }
  .utility-button { padding: 0 10px; }
  .utility-label-optional { display: none; }
  .stamp { width: 68px; height: 68px; top: 31px; }
  .stamp strong { font-size: 14px; }
  .card-body { padding-left: 15px; padding-right: 15px; }
  .source { max-width: 100px; }
  .archive-count { display: none; }
  .archive-row { grid-template-columns: 1fr auto; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
"""

JS = r"""
(() => {
  const STORAGE_KEY = 'snaac-saved-articles-v1';
  const dataElement = document.getElementById('briefingData');
  const liveRegion = document.getElementById('saveStatus');
  const drawer = document.getElementById('savedDrawer');
  const savedList = document.getElementById('savedList');
  const currentItems = dataElement ? JSON.parse(dataElement.textContent || '[]') : [];
  const currentByUrl = new Map(currentItems.map(item => [item.link, item]));
  let storageAvailable = true;
  let drawerTrigger = null;

  function readSaved() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      storageAvailable = false;
      return [];
    }
  }

  function writeSaved(items) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
      storageAvailable = true;
      return true;
    } catch (error) {
      storageAvailable = false;
      return false;
    }
  }

  function announce(message) {
    if (!liveRegion) return;
    liveRegion.textContent = '';
    window.setTimeout(() => { liveRegion.textContent = message; }, 20);
  }

  function updateButtons() {
    const savedUrls = new Set(readSaved().map(item => item.link));
    document.querySelectorAll('.save-button').forEach(button => {
      const isSaved = savedUrls.has(button.dataset.url);
      button.classList.toggle('is-saved', isSaved);
      button.setAttribute('aria-pressed', String(isSaved));
      const label = button.querySelector('.save-label');
      if (label) label.textContent = isSaved ? '저장됨' : '저장';
    });
    document.querySelectorAll('[data-saved-count]').forEach(node => {
      node.textContent = String(savedUrls.size);
    });
  }

  function toggleSaved(url) {
    const item = currentByUrl.get(url);
    if (!item) return;

    const saved = readSaved();
    const index = saved.findIndex(entry => entry.link === url);
    let message = '';

    if (index >= 0) {
      saved.splice(index, 1);
      message = '저장을 취소했어요.';
    } else {
      saved.unshift({ ...item, savedAt: new Date().toISOString() });
      message = '저장함에 담았어요.';
    }

    if (!writeSaved(saved)) {
      announce('이 브라우저에서는 저장 기능을 사용할 수 없어요.');
      return;
    }
    updateButtons();
    renderSaved();
    announce(message);
  }

  function removeSaved(url) {
    const saved = readSaved().filter(item => item.link !== url);
    writeSaved(saved);
    updateButtons();
    renderSaved();
    announce('저장한 기사에서 삭제했어요.');
  }

  function renderSaved() {
    if (!savedList) return;
    const saved = readSaved();
    savedList.replaceChildren();

    if (!storageAvailable) {
      const note = document.createElement('p');
      note.className = 'saved-empty';
      note.textContent = '현재 브라우저의 저장 공간을 사용할 수 없어요.';
      savedList.append(note);
      return;
    }

    if (!saved.length) {
      const note = document.createElement('p');
      note.className = 'saved-empty';
      note.textContent = '아직 저장한 기사가 없어요. 카드 아래의 저장 버튼을 눌러보세요.';
      savedList.append(note);
      return;
    }

    saved.forEach(item => {
      const article = document.createElement('article');
      article.className = 'saved-item';

      const meta = document.createElement('div');
      meta.className = 'saved-meta';
      meta.textContent = [item.briefingDate, item.source].filter(Boolean).join(' · ');

      const link = document.createElement('a');
      link.className = 'saved-title';
      link.href = item.link;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = item.title || '제목 없음';

      const actions = document.createElement('div');
      actions.className = 'saved-actions';
      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'remove-saved';
      removeButton.dataset.removeUrl = item.link;
      removeButton.textContent = '삭제';
      actions.append(removeButton);

      article.append(meta, link, actions);
      savedList.append(article);
    });
  }

  function openDrawer() {
    if (!drawer) return;
    drawerTrigger = document.activeElement;
    renderSaved();
    drawer.hidden = false;
    document.body.classList.add('drawer-open');
    const closeButton = drawer.querySelector('.close-button');
    if (closeButton) closeButton.focus();
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.hidden = true;
    document.body.classList.remove('drawer-open');
    if (drawerTrigger && typeof drawerTrigger.focus === 'function') drawerTrigger.focus();
  }

  document.addEventListener('click', event => {
    const saveButton = event.target.closest('.save-button');
    if (saveButton) {
      toggleSaved(saveButton.dataset.url);
      return;
    }

    const openButton = event.target.closest('[data-open-saved]');
    if (openButton) {
      openDrawer();
      return;
    }

    const closeButton = event.target.closest('[data-close-saved]');
    if (closeButton) {
      closeDrawer();
      return;
    }

    const removeButton = event.target.closest('[data-remove-url]');
    if (removeButton) removeSaved(removeButton.dataset.removeUrl);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && drawer && !drawer.hidden) closeDrawer();
  });

  window.addEventListener('storage', () => {
    updateButtons();
    renderSaved();
  });

  updateButtons();
  renderSaved();
})();
"""


def fetch_og_image(url: str) -> str | None:
    """원문 페이지의 og:image URL만 추출합니다. 이미지 파일은 저장하지 않습니다."""
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SNAACBriefingBot/2.0)"
            },
        )
        response.raise_for_status()
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if not match:
                continue
            image_url = html.unescape(match.group(1).strip())
            image_url = urljoin(url, image_url)
            if image_url.startswith(("http://", "https://")):
                return image_url
    except Exception as exc:
        print(f"[썸네일 스킵] {url}: {exc}")
    return None


def _safe_json_for_script(data: object) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _prepare_picks(picks: list[dict], date_label: str) -> list[dict]:
    prepared: list[dict] = []
    for pick in picks:
        item = {
            "title": str(pick.get("title", "")).strip(),
            "link": str(pick.get("link", "")).strip(),
            "source": str(pick.get("source", "기타")).strip() or "기타",
            "summary": str(pick.get("summary", "")).strip(),
            "takeaway": str(pick.get("takeaway", "")).strip(),
            "category": str(pick.get("category", "생태계 업데이트")).strip(),
            "content_type": str(pick.get("content_type", "기사")).strip(),
            "published": str(pick.get("published", "unknown")).strip(),
            "briefingDate": date_label,
        }
        item["image"] = fetch_og_image(item["link"]) if SHOW_THUMBNAILS else None
        prepared.append(item)
    return prepared


def _bookmark_icon() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M6.5 4.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16l-5.5-3.2-5.5 3.2z"/>'
        "</svg>"
    )


def _card(index: int, total: int, pick: dict) -> str:
    title = html.escape(pick["title"])
    summary = html.escape(pick["summary"])
    takeaway = html.escape(
        pick["takeaway"]
        or "원문에서 이번 변화가 스타트업과 창업가에게 주는 의미를 확인해보세요."
    )
    source = html.escape(pick["source"])
    category = html.escape(pick["category"])
    content_type = html.escape(pick["content_type"])
    link = html.escape(pick["link"], quote=True)
    initial = html.escape((pick["source"] or "S")[0])

    if pick.get("image"):
        image = html.escape(pick["image"], quote=True)
        thumb_inner = (
            f'<img src="{image}" alt="" loading="lazy" decoding="async" '
            'onerror="this.parentElement.classList.add(\'noimg\');this.remove()">'
        )
        thumb_class = "thumb"
    else:
        thumb_inner = ""
        thumb_class = "thumb noimg"

    return f"""
<article class="card">
  <a class="{thumb_class}" href="{link}" target="_blank" rel="noopener noreferrer" data-initial="{initial}" aria-label="{title} 원문 열기">
    {thumb_inner}
    <span class="media-label">{content_type}</span>
  </a>
  <div class="card-body">
    <div class="card-meta">
      <div class="meta-left">
        <span class="category">{category}</span>
        <span class="source">{source}</span>
      </div>
      <span class="card-index">{index:02d}/{total:02d}</span>
    </div>
    <a class="title-link" href="{link}" target="_blank" rel="noopener noreferrer"><h2>{title}</h2></a>
    <p class="summary">{summary}</p>
    <div class="takeaway">
      <span class="takeaway-label">WHY IT MATTERS</span>
      <p>{takeaway}</p>
    </div>
    <div class="card-actions">
      <a class="read-link" href="{link}" target="_blank" rel="noopener noreferrer">원문 읽기</a>
      <button class="save-button" type="button" data-url="{link}" aria-pressed="false">
        {_bookmark_icon()}<span class="save-label">저장</span>
      </button>
    </div>
  </div>
</article>"""


def _archive_entries(exclude_slug: str | None = None) -> list[dict]:
    archive_dir = DOCS_DIR / "archive"
    if not archive_dir.exists():
        return []

    entries: list[dict] = []
    slugs = sorted(
        [path.stem for path in archive_dir.glob("????-??-??.html")], reverse=True
    )
    for slug in slugs:
        if slug == exclude_slug:
            continue
        try:
            date = datetime.strptime(slug, "%Y-%m-%d")
        except ValueError:
            continue

        count = 5
        json_path = archive_dir / f"{slug}.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                count = len(data.get("picks", [])) or 5
            except (OSError, json.JSONDecodeError):
                pass

        entries.append(
            {
                "slug": slug,
                "label": f"{date.month}월 {date.day}일",
                "full_label": f"{date.year}년 {date.month}월 {date.day}일",
                "count": count,
            }
        )
    return entries


def _archive_section(today_slug: str, context: str) -> str:
    entries = _archive_entries(exclude_slug=today_slug)[:ARCHIVE_KEEP]
    if context == "home":
        item_prefix = "archive/"
        index_href = "archive/"
    else:
        item_prefix = ""
        index_href = "./"

    if entries:
        rows = "".join(
            f'<a class="archive-row" href="{item_prefix}{entry["slug"]}.html">'
            f'<span class="archive-date">{entry["label"]}</span>'
            f'<span class="archive-count">{entry["count"]}개의 큐레이션</span>'
            '<span class="archive-arrow" aria-hidden="true">→</span>'
            "</a>"
            for entry in entries
        )
    else:
        rows = '<p class="empty-archive">지난 브리핑이 쌓이면 이곳에서 다시 볼 수 있어요.</p>'

    return f"""
<section class="archive-section" id="archive">
  <div class="section-head">
    <h2>지난 브리핑</h2>
    <a href="{index_href}">전체 보기 →</a>
  </div>
  <div class="archive-list">{rows}</div>
</section>"""


def _drawer_html() -> str:
    return """
<div class="drawer" id="savedDrawer" hidden>
  <button class="drawer-backdrop" type="button" data-close-saved aria-label="저장함 닫기"></button>
  <section class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="savedTitle">
    <div class="drawer-handle" aria-hidden="true"></div>
    <div class="drawer-head">
      <h2 id="savedTitle">저장한 기사</h2>
      <button class="close-button" type="button" data-close-saved aria-label="닫기">×</button>
    </div>
    <div class="saved-list" id="savedList"></div>
  </section>
</div>
<p class="sr-only" id="saveStatus" aria-live="polite"></p>
"""


def _page_html(
    picks: list[dict],
    now: datetime,
    context: str,
) -> str:
    date_big = f"{now.month}.{now.day}."
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    slug = now.strftime("%Y-%m-%d")
    total = len(picks)
    cards = "".join(_card(index, total, pick) for index, pick in enumerate(picks, 1))

    if context == "home":
        brand = '<span class="brand"><span class="brand-mark"></span>SNAAC MORNING</span>'
        archive_href = "archive/"
    else:
        brand = '<a class="brand" href="../"><span class="brand-mark"></span>오늘 브리핑</a>'
        archive_href = "./"

    storage_data = [
        {
            "title": pick["title"],
            "link": pick["link"],
            "source": pick["source"],
            "summary": pick["summary"],
            "takeaway": pick["takeaway"],
            "category": pick["category"],
            "contentType": pick["content_type"],
            "briefingDate": f"{now.month}/{now.day}",
        }
        for pick in picks
    ]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f2f2">
<title>SNAAC 모닝 브리핑 · {html.escape(date_label)}</title>
<meta name="description" content="SNAAC이 고른 오늘의 스타트업 업데이트, 인터뷰와 인사이트 {total}가지">
<meta property="og:title" content="SNAAC 모닝 브리핑 · {now.month}/{now.day}">
<meta property="og:description" content="스타트업 생태계 업데이트부터 창업가·VC 관점과 실무 인사이트까지">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <div class="topline">
      {brand}
      <div class="top-actions">
        <a class="utility-button" href="{archive_href}" aria-label="지난 브리핑 보기"><span class="utility-label-optional">지난 회차</span><span aria-hidden="true">↺</span></a>
        <button class="utility-button" type="button" data-open-saved>저장함 <span class="count-badge" data-saved-count>0</span></button>
      </div>
    </div>
    <div class="date-lockup">
      <p class="kicker">Daily startup journal</p>
      <h1 class="date-big">{date_big}</h1>
      <div class="date-sub">{html.escape(date_label)}</div>
      <div class="stamp">DAILY<strong>AM 9</strong>DROP</div>
    </div>
  </header>

  <section class="intro">
    <p>단순 투자 단신보다, 오늘 스타트업을 이해하는 데 도움이 되는 업데이트와 관점을 골랐어요. 각 카드에는 핵심 맥락과 읽어볼 이유를 함께 담았습니다.</p>
    <div class="editorial-rule" aria-label="큐레이션 범위">
      <span>생태계 업데이트</span><span>창업가·VC 관점</span><span>제품·성장</span><span>인터뷰·영상</span>
    </div>
  </section>

  <main class="cards">{cards}</main>
  {_archive_section(slug, context)}

  <footer>
    매일 아침 자동 업데이트 · SNAAC Community Team<br>
    원문 링크와 자체 요약만 제공하며, 모든 콘텐츠의 저작권은 각 원저작자에게 있습니다.<br>
    저장한 기사는 현재 기기의 브라우저에만 보관됩니다.
  </footer>
</div>
{_drawer_html()}
<script id="briefingData" type="application/json">{_safe_json_for_script(storage_data)}</script>
<script>{JS}</script>
</body>
</html>"""


def _archive_index_html(entries: list[dict]) -> str:
    rows = "".join(
        f'<a class="archive-row" href="{entry["slug"]}.html">'
        f'<span class="archive-date">{entry["full_label"]}</span>'
        f'<span class="archive-count">{entry["count"]}개의 큐레이션</span>'
        '<span class="archive-arrow" aria-hidden="true">→</span>'
        "</a>"
        for entry in entries
    )
    if not rows:
        rows = '<p class="empty-archive">아직 저장된 지난 브리핑이 없어요.</p>'

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f2f2">
<title>SNAAC 지난 브리핑</title>
<meta name="description" content="SNAAC 모닝 브리핑 지난 회차 모아보기">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <div class="topline" style="padding-top:18px">
    <a class="brand" href="../"><span class="brand-mark"></span>오늘 브리핑</a>
    <button class="utility-button" type="button" data-open-saved>저장함 <span class="count-badge" data-saved-count>0</span></button>
  </div>
  <header class="archive-hero">
    <p class="kicker">SNAAC morning archive</p>
    <h1>지난 브리핑</h1>
    <p>날짜를 눌러 그날 소개한 기사 5개를 다시 확인하세요.</p>
  </header>
  <main class="archive-page-list">
    <div class="archive-list">{rows}</div>
  </main>
  <footer>
    아카이브 열람에는 별도 AI 호출이나 토큰 비용이 발생하지 않습니다.<br>
    SNAAC Community Team
  </footer>
</div>
{_drawer_html()}
<script id="briefingData" type="application/json">[]</script>
<script>{JS}</script>
</body>
</html>"""


def build_page(picks: list[dict]) -> None:
    """오늘 페이지, 날짜별 아카이브, JSON 데이터, 전체 목록을 생성합니다."""
    now = datetime.now(KST)
    slug = now.strftime("%Y-%m-%d")
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"

    DOCS_DIR.mkdir(exist_ok=True)
    archive_dir = DOCS_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    prepared_picks = _prepare_picks(picks, date_label)

    # 오늘 고정 링크
    home_page = _page_html(prepared_picks, now, context="home")
    (DOCS_DIR / "index.html").write_text(home_page, encoding="utf-8")

    # 날짜별 HTML 아카이브
    archived_page = _page_html(prepared_picks, now, context="archive")
    (archive_dir / f"{slug}.html").write_text(archived_page, encoding="utf-8")

    # 최근 중복 방지와 장기 보관을 위한 작은 JSON. 기사 본문/이미지는 저장하지 않습니다.
    archive_data = {
        "date": slug,
        "date_label": date_label,
        "generated_at": now.isoformat(),
        "picks": [
            {key: value for key, value in pick.items() if key != "image"}
            for pick in prepared_picks
        ],
    }
    (archive_dir / f"{slug}.json").write_text(
        json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 매일 최신 상태로 갱신되는 전체 아카이브 목록
    archive_index = _archive_index_html(_archive_entries())
    (archive_dir / "index.html").write_text(archive_index, encoding="utf-8")

    print(
        f"[페이지 생성 완료] docs/index.html, "
        f"docs/archive/{slug}.html, docs/archive/{slug}.json, docs/archive/index.html"
    )
