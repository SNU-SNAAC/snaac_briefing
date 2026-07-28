"""SNAAC 모닝 브리핑 정적 웹페이지 생성 모듈.

생성 파일
- docs/index.html: 오늘의 브리핑
- docs/archive/YYYY-MM-DD.html: 날짜별 브리핑
- docs/archive/YYYY-MM-DD.json: 아카이브 데이터 및 최근 중복 방지
- docs/archive/index.html: 전체 지난 브리핑 목록
- docs/assets/snaac-logo.png: 상단 SNAAC 로고

핵심 UX
- 텍스트·인터페이스는 차분한 무채색, 기사와 영상 썸네일은 원본 컬러 유지
- 저장함은 상단 핵심 버튼과 하단 고정 버튼으로 강조
- 저장한 항목을 누르면 원문으로 바로 이동하지 않고 브리핑 카드 상세 화면 표시
- 선택형 스크랩 메모 지원
- Supabase 설정 시 이메일/비밀번호 로그인과 저장함·메모 기기 간 동기화
- 기사 저장과 저장함 열람은 로그인 후 이용하며, 기존 비로그인 저장 데이터는 첫 로그인 때 계정으로 이전
- 지난 브리핑은 월 → 주차 → 날짜 순의 서랍형 아카이브로 정리
- 지난 브리핑 아래에 SNAAC 공식 홈페이지로 연결되는 소개 카드 제공
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

SHOW_THUMBNAILS = True
DOCS_DIR = Path("docs")
ARCHIVE_KEEP = 14

# 로그인 기능은 Supabase 공개 설정이 있을 때만 활성화됩니다.
# Publishable key는 브라우저에서 쓰도록 설계된 공개 키이며, service_role/secret key는 절대 넣지 않습니다.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = (
    os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    or os.environ.get("SUPABASE_ANON_KEY", "")
).strip()
SUPABASE_REDIRECT_URL = os.environ.get("SUPABASE_REDIRECT_URL", "").strip()
AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)

LOGO_ASSET_NAME = "snaac-logo.png"
LOGO_PNG_BASE64 = """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"""

SOURCE_GRADIENTS = {
    "플래텀": ("#2752B8", "#6D9CFF"),
    "벤처스퀘어": ("#087C67", "#46C7A5"),
    "스타트업레시피": ("#C85B1A", "#F3A64A"),
    "바이라인네트워크": ("#5B3DB4", "#A06FE8"),
    "블로터": ("#9A3557", "#E87895"),
    "지디넷 스타트업": ("#176F9D", "#62BDE0"),
    "아웃스탠딩": ("#242A79", "#6D78E8"),
    "EO": ("#111111", "#5A5A5A"),
    "EO Korea": ("#111111", "#5A5A5A"),
    "LinkedIn": ("#0A66C2", "#58A8EA"),
    "링크드인": ("#0A66C2", "#58A8EA"),
    "YouTube": ("#C91524", "#FF6670"),
    "유튜브": ("#C91524", "#FF6670"),
    "a16z": ("#6A35C9", "#B37AF4"),
}
FALLBACK_GRADIENTS = [
    ("#2752B8", "#6D9CFF"),
    ("#087C67", "#46C7A5"),
    ("#C85B1A", "#F3A64A"),
    ("#5B3DB4", "#A06FE8"),
    ("#9A3557", "#E87895"),
    ("#176F9D", "#62BDE0"),
]

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
button, textarea { font: inherit; }
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

.intro { padding: 18px 0 8px; }
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
    linear-gradient(135deg, rgba(255,255,255,.24), transparent 56%),
    linear-gradient(135deg, var(--fallback, #2752B8), var(--fallback-2, #6D9CFF));
}
.thumb.noimg::before {
  content: attr(data-initial);
  position: relative;
  z-index: 1;
  color: rgba(255, 255, 255, .94);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 44px;
  text-shadow: 0 2px 16px rgba(0,0,0,.18);
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

.drawer,
.note-dialog {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.drawer { z-index: 50; }
.note-dialog { z-index: 70; }
.drawer-backdrop,
.note-backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(15, 15, 14, .5);
  cursor: pointer;
}
.drawer-panel,
.note-panel {
  position: relative;
  width: min(100%, 600px);
  overflow: hidden;
  border: 1px solid var(--line);
  border-bottom: 0;
  border-radius: 22px 22px 0 0;
  background: var(--surface);
  box-shadow: 0 -18px 50px rgba(0,0,0,.17);
  animation: drawer-up .18s ease-out both;
}
.drawer-panel {
  max-height: min(78vh, 720px);
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.note-panel {
  max-height: min(88vh, 720px);
  overflow-y: auto;
  padding: 8px 17px calc(18px + env(safe-area-inset-bottom));
}
@keyframes drawer-up {
  from { transform: translateY(18px); opacity: .5; }
  to { transform: translateY(0); opacity: 1; }
}
.drawer-handle {
  width: 42px;
  height: 4px;
  margin: 9px auto 2px;
  border-radius: 999px;
  background: var(--line-strong);
}
.drawer-head,
.note-head {
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.drawer-head { padding: 0 17px; border-bottom: 1px solid var(--line); }
.drawer-head h2,
.note-head h2 { margin: 0; font-size: 17px; }
.close-button {
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: #fff;
  color: var(--ink);
  font-size: 20px;
  cursor: pointer;
}
.saved-list {
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 8px 16px 18px;
}
.saved-empty {
  padding: 44px 18px;
  color: var(--muted);
  font-size: 14px;
  text-align: center;
}
.saved-item { padding: 14px 0; border-bottom: 1px solid var(--line); }
.saved-item:last-child { border-bottom: 0; }
.saved-meta {
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 11.5px;
  font-weight: 700;
}
.saved-title {
  display: block;
  color: var(--ink);
  text-decoration: none;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.45;
}
.saved-note {
  margin: 10px 0 0;
  padding: 10px 11px;
  border-left: 3px solid var(--ink);
  background: var(--surface-soft);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.saved-note-label {
  display: block;
  margin-bottom: 3px;
  color: var(--muted);
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: .08em;
}
.saved-actions {
  display: flex;
  justify-content: flex-end;
  gap: 7px;
  margin-top: 10px;
}
.saved-action-button {
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
.edit-note { color: var(--ink-2); }

.note-article-title {
  margin: 1px 0 13px;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.note-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 800;
}
.note-optional { color: var(--muted); font-weight: 600; }
.note-count { color: var(--muted); font-size: 11px; font-weight: 600; }
.note-input {
  width: 100%;
  min-height: 122px;
  display: block;
  resize: vertical;
  border: 1px solid var(--line-strong);
  border-radius: 13px;
  background: #fff;
  color: var(--ink);
  padding: 12px 13px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
  outline: none;
}
.note-input:focus {
  border-color: var(--ink);
  box-shadow: 0 0 0 3px rgba(23,23,23,.08);
}
.note-input::placeholder { color: #9a9a9a; }
.note-help { margin: 8px 1px 0; color: var(--muted); font-size: 11.5px; }
.note-actions {
  display: grid;
  grid-template-columns: 1fr 1.35fr;
  gap: 9px;
  margin-top: 15px;
}
.note-button {
  min-height: 46px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: #fff;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}
.note-button-primary { border-color: var(--ink); background: var(--ink); color: #fff; }
.note-button:active { transform: scale(.985); }

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
  .thumb img { transition: transform .25s ease; }
  .card:hover .thumb img { transform: scale(1.018); }
  .utility-button:hover,
  .save-button:hover,
  .close-button:hover,
  .saved-action-button:hover { border-color: var(--ink); }
  .archive-summary:hover { background: #fafafa; }
  .archive-day-row:hover { background: #fafafa; }
  .about-snaac-card:hover { transform: translateY(-1px); box-shadow: 0 13px 32px rgba(17,17,17,.15); }
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
  .note-panel { padding-left: 14px; padding-right: 14px; }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
"""

CSS_V5 = r"""
/* ── v5: 로그인 필수 저장, 서랍형 아카이브, ABOUT SNAAC ── */
.logo-row {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 0 18px;
}
.logo-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}
.site-logo {
  width: clamp(158px, 47vw, 208px);
  height: auto;
  display: block;
}
.topline {
  min-height: 44px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1fr);
  align-items: center;
  gap: 7px;
}
.topline .utility-button {
  width: 100%;
  min-width: 0;
  padding: 0 9px;
  white-space: nowrap;
}
.utility-button.saved-vault {
  border-color: var(--ink);
  background: var(--ink);
  color: #fff;
  box-shadow: 0 7px 18px rgba(17,17,17,.14);
}
.utility-button.saved-vault .count-badge {
  background: #fff;
  color: var(--ink);
}
.utility-button.saved-vault svg { width: 15px; height: 15px; fill: currentColor; }
.note-dialog { z-index: 90; }
.utility-button.auth-control {
  overflow: hidden;
}
.utility-button.auth-control span[data-auth-label] {
  overflow: hidden;
  text-overflow: ellipsis;
}
.masthead { padding-top: 0; }
.date-lockup { padding-top: 24px; }

.free-access-note {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.free-access-note::before {
  content: '✓';
  font-size: 11px;
  font-weight: 900;
}

.thumb.is-video::before,
.preview-thumb.is-video::after,
.saved-thumb.is-video::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 3;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: rgba(17,17,17,.82);
  box-shadow: 0 7px 22px rgba(0,0,0,.2);
  transform: translate(-50%, -50%);
  pointer-events: none;
}
.thumb.is-video .play-triangle,
.preview-thumb.is-video .play-triangle,
.saved-thumb.is-video .play-triangle {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 4;
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 13px solid #fff;
  transform: translate(-36%, -50%);
  pointer-events: none;
}

.floating-saved {
  position: fixed;
  left: 50%;
  bottom: calc(14px + env(safe-area-inset-bottom));
  z-index: 32;
  min-width: 176px;
  min-height: 50px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 0 18px;
  border: 1px solid #111;
  border-radius: 999px;
  background: #111;
  color: #fff;
  box-shadow: 0 12px 34px rgba(0,0,0,.24);
  font-size: 14px;
  font-weight: 850;
  cursor: pointer;
  transform: translateX(-50%);
  transition: opacity .16s ease, transform .16s ease;
}
.floating-saved svg { width: 17px; height: 17px; fill: currentColor; }
.floating-saved .count-badge { background: #fff; color: #111; }
.floating-saved:active { transform: translateX(-50%) scale(.98); }
body.drawer-open .floating-saved { opacity: 0; pointer-events: none; transform: translateX(-50%) translateY(12px); }

.drawer-panel { max-height: min(92dvh, 820px); }
.drawer-head {
  min-height: 70px;
  padding: 0 16px;
}
.drawer-title-wrap { min-width: 0; }
.drawer-head h2 { display: flex; align-items: center; gap: 8px; }
.drawer-head h2 svg { width: 18px; height: 18px; fill: currentColor; }
.drawer-subtitle { margin: 2px 0 0; color: var(--muted); font-size: 11.5px; }

.sync-strip {
  margin: 12px 16px 4px;
  padding: 12px 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface-soft);
}
.sync-copy { min-width: 0; }
.sync-title { margin: 0; color: var(--ink); font-size: 12.5px; font-weight: 800; }
.sync-text { margin: 2px 0 0; color: var(--muted); font-size: 11px; line-height: 1.4; }
.sync-action {
  flex: 0 0 auto;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--ink);
  border-radius: 999px;
  background: var(--ink);
  color: #fff;
  font-size: 11.5px;
  font-weight: 800;
  cursor: pointer;
}

.saved-list { padding: 10px 14px 24px; }
.saved-item {
  margin-bottom: 11px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: #fff;
}
.saved-item:last-child { margin-bottom: 0; border-bottom: 1px solid var(--line); }
.saved-preview-trigger {
  width: 100%;
  display: grid;
  grid-template-columns: 94px minmax(0, 1fr);
  gap: 12px;
  padding: 11px;
  border: 0;
  background: #fff;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.saved-thumb {
  position: relative;
  min-height: 78px;
  overflow: hidden;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--fallback, #2752B8), var(--fallback-2, #6D9CFF));
}
.saved-thumb img { width: 100%; height: 100%; display: block; object-fit: cover; }
.saved-thumb.noimg::before {
  content: attr(data-initial);
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255,255,255,.94);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 26px;
  font-weight: 700;
}
.saved-thumb.is-video::after { width: 34px; height: 34px; }
.saved-thumb.is-video .play-triangle {
  border-top-width: 6px;
  border-bottom-width: 6px;
  border-left-width: 10px;
}
.saved-copy { min-width: 0; align-self: center; }
.saved-meta { margin: 0 0 5px; }
.saved-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 14.5px;
  line-height: 1.43;
}
.saved-note-preview {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.saved-note-preview strong { color: var(--ink-2); font-size: 10px; letter-spacing: .06em; }
.saved-open-hint { margin-top: 7px; color: var(--ink-2); font-size: 11px; font-weight: 800; }
.saved-actions {
  margin: 0;
  padding: 9px 11px 10px;
  border-top: 1px solid var(--line);
}
.saved-action-button { background: #fff; }
.saved-action-button.preview-action { margin-right: auto; color: var(--ink); border-color: var(--line-strong); }

.preview-dialog,
.auth-dialog {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.preview-dialog { z-index: 80; }
.auth-dialog { z-index: 100; }
.preview-backdrop,
.auth-backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(15,15,14,.56);
  cursor: pointer;
}
.preview-panel,
.auth-panel {
  position: relative;
  width: min(100%, 600px);
  max-height: min(92dvh, 820px);
  overflow-y: auto;
  border: 1px solid var(--line);
  border-bottom: 0;
  border-radius: 22px 22px 0 0;
  background: var(--surface);
  box-shadow: 0 -18px 50px rgba(0,0,0,.2);
  padding-bottom: env(safe-area-inset-bottom);
  animation: drawer-up .18s ease-out both;
}
.preview-head,
.auth-head {
  position: sticky;
  top: 0;
  z-index: 7;
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid var(--line);
  background: rgba(255,255,255,.96);
  backdrop-filter: blur(12px);
}
.preview-head h2,
.auth-head h2 { margin: 0; font-size: 17px; }
.preview-card { margin: 14px; overflow: hidden; border: 1px solid var(--line); border-radius: 18px; background: #fff; }
.preview-thumb {
  position: relative;
  aspect-ratio: 16 / 8.8;
  overflow: hidden;
  background: linear-gradient(135deg, var(--fallback, #2752B8), var(--fallback-2, #6D9CFF));
}
.preview-thumb img { width: 100%; height: 100%; display: block; object-fit: cover; }
.preview-thumb.noimg::before {
  content: attr(data-initial);
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255,255,255,.94);
  font-family: GmarketSans, Pretendard, sans-serif;
  font-size: 42px;
}
.preview-body { padding: 17px; }
.preview-body h3 { margin: 0; font-size: 20px; line-height: 1.42; letter-spacing: -.025em; }
.preview-summary { margin: 11px 0 0; color: var(--ink-2); font-size: 15px; line-height: 1.65; }
.preview-note {
  margin-top: 14px;
  padding: 12px 13px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.preview-note strong { display: block; margin-bottom: 4px; color: var(--muted); font-size: 10.5px; letter-spacing: .09em; }
.preview-actions {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 9px;
  margin-top: 15px;
}
.preview-read,
.preview-secondary {
  min-height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 13.5px;
  font-weight: 800;
  text-decoration: none;
  cursor: pointer;
}
.preview-read { border: 1px solid var(--ink); background: var(--ink); color: #fff; }
.preview-secondary { border: 1px solid var(--line-strong); background: #fff; color: var(--ink-2); }
.preview-delete {
  width: 100%;
  min-height: 42px;
  margin-top: 8px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.auth-content { padding: 18px 16px calc(22px + env(safe-area-inset-bottom)); }
.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 4px;
  border-radius: 12px;
  background: var(--surface-soft);
}
.auth-tab {
  min-height: 40px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.auth-tab.is-active { background: #fff; color: var(--ink); box-shadow: 0 2px 9px rgba(0,0,0,.06); }
.auth-form { margin-top: 16px; }
.auth-label { display: block; margin-top: 12px; color: var(--ink-2); font-size: 12px; font-weight: 800; }
.auth-input {
  width: 100%;
  min-height: 48px;
  margin-top: 6px;
  padding: 0 13px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: #fff;
  color: var(--ink);
  font-size: 15px;
  outline: none;
}
.auth-input:focus { border-color: var(--ink); box-shadow: 0 0 0 3px rgba(23,23,23,.08); }
.auth-submit {
  width: 100%;
  min-height: 49px;
  margin-top: 17px;
  border: 1px solid var(--ink);
  border-radius: 12px;
  background: var(--ink);
  color: #fff;
  font-size: 14px;
  font-weight: 850;
  cursor: pointer;
}
.auth-submit:disabled { opacity: .55; cursor: wait; }
.auth-message { min-height: 20px; margin: 11px 2px 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
.auth-message.is-error { color: #4a2020; }
.auth-help { margin: 12px 2px 0; color: var(--muted); font-size: 11.5px; line-height: 1.55; }
.account-card {
  padding: 17px;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: var(--surface-soft);
}
.account-eyebrow { margin: 0 0 5px; color: var(--muted); font-size: 10.5px; font-weight: 800; letter-spacing: .1em; }
.account-email { margin: 0; color: var(--ink); font-size: 15px; font-weight: 800; overflow-wrap: anywhere; }
.account-copy { margin: 9px 0 0; color: var(--muted); font-size: 12px; line-height: 1.55; }
.account-logout {
  width: 100%;
  min-height: 46px;
  margin-top: 13px;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: #fff;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.auth-setup-note { padding: 18px; border: 1px solid var(--line); border-radius: 14px; background: var(--surface-soft); }
.auth-setup-note h3 { margin: 0 0 7px; font-size: 15px; }
.auth-setup-note p { margin: 0; color: var(--muted); font-size: 12.5px; line-height: 1.65; }


/* 로그인 목적 안내 */
.auth-intent {
  margin: 0 0 13px;
  padding: 12px 13px;
  border: 1px solid var(--ink);
  border-radius: 12px;
  background: var(--ink);
  color: #fff;
  font-size: 12.5px;
  font-weight: 750;
  line-height: 1.55;
}

/* 월 → 주차 → 날짜 순 서랍형 아카이브 */
.archive-tree {
  display: grid;
  gap: 10px;
}
.archive-month,
.archive-week {
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 15px;
  background: var(--surface);
}
.archive-month[open] {
  border-color: var(--line-strong);
  box-shadow: 0 8px 24px rgba(20,20,18,.045);
}
.archive-summary {
  min-height: 62px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 15px;
  list-style: none;
  cursor: pointer;
  user-select: none;
}
.archive-summary::-webkit-details-marker { display: none; }
.archive-summary::marker { content: ''; }
.archive-summary-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.archive-summary-title {
  color: var(--ink);
  font-size: 15px;
  font-weight: 850;
  letter-spacing: -.015em;
}
.archive-summary-meta {
  color: var(--muted);
  font-size: 11.5px;
  font-weight: 650;
}
.archive-chevron {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  color: var(--muted);
  font-size: 14px;
  transition: transform .16s ease;
}
details[open] > .archive-summary .archive-chevron { transform: rotate(180deg); }
.archive-month-body {
  display: grid;
  gap: 9px;
  padding: 10px;
  border-top: 1px solid var(--line);
  background: var(--surface-soft);
}
.archive-week {
  border-radius: 12px;
  box-shadow: none;
}
.archive-week .archive-summary {
  min-height: 54px;
  padding-left: 13px;
  padding-right: 13px;
}
.archive-week .archive-summary-title { font-size: 13.5px; }
.archive-week .archive-chevron {
  width: 25px;
  height: 25px;
  font-size: 12px;
}
.archive-day-list {
  border-top: 1px solid var(--line);
  background: #fff;
}
.archive-day-row {
  min-height: 56px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  padding: 0 13px;
  border-bottom: 1px solid var(--line);
  color: inherit;
  text-decoration: none;
}
.archive-day-row:last-child { border-bottom: 0; }
.archive-day-date {
  min-width: 0;
  color: var(--ink);
  font-size: 13.5px;
  font-weight: 800;
}
.archive-day-count {
  color: var(--muted);
  font-size: 11.5px;
  white-space: nowrap;
}
.archive-day-arrow { color: var(--muted); font-size: 14px; }
.archive-tree-compact .archive-month:not([open]) .archive-month-body { display: none; }

/* 지난 브리핑 아래 ABOUT SNAAC */
.about-snaac-section { margin-top: 18px; }
.about-snaac-card {
  position: relative;
  display: block;
  overflow: hidden;
  padding: 20px 58px 20px 18px;
  border: 1px solid var(--ink);
  border-radius: 16px;
  background: var(--ink);
  color: #fff;
  text-decoration: none;
  box-shadow: 0 10px 28px rgba(17,17,17,.11);
}
.about-snaac-card::after {
  content: '↗';
  position: absolute;
  top: 50%;
  right: 18px;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255,255,255,.34);
  border-radius: 50%;
  font-size: 17px;
  transform: translateY(-50%);
}
.about-snaac-eyebrow {
  display: block;
  margin-bottom: 5px;
  color: rgba(255,255,255,.62);
  font-size: 10.5px;
  font-weight: 850;
  letter-spacing: .14em;
}
.about-snaac-title {
  display: block;
  font-size: 16px;
  font-weight: 850;
  letter-spacing: -.015em;
}
.about-snaac-copy {
  display: block;
  margin-top: 5px;
  color: rgba(255,255,255,.7);
  font-size: 12px;
  line-height: 1.55;
}

@media (max-width: 390px) {
  .logo-row { padding-top: 11px; padding-bottom: 15px; }
  .site-logo { width: 164px; }
  .topline { gap: 5px; }
  .topline .utility-button { min-height: 39px; padding: 0 6px; font-size: 11.5px; }
  .saved-preview-trigger { grid-template-columns: 82px minmax(0, 1fr); gap: 10px; }
  .saved-thumb { min-height: 72px; }
  .floating-saved { min-width: 164px; min-height: 48px; }
  .preview-card { margin-left: 10px; margin-right: 10px; }
  .archive-day-row { grid-template-columns: minmax(0, 1fr) auto; }
  .archive-day-count { display: none; }
  .about-snaac-card { padding-left: 16px; }
}
"""

JS = r"""(() => {
  'use strict';

  const GUEST_STORAGE_KEY = 'snaac-saved-articles-v1';
  const USER_STORAGE_PREFIX = 'snaac-saved-articles-user-v1:';
  const dataElement = document.getElementById('briefingData');
  const authConfigElement = document.getElementById('authConfig');
  const currentItems = dataElement ? JSON.parse(dataElement.textContent || '[]') : [];
  const authConfig = authConfigElement ? JSON.parse(authConfigElement.textContent || '{}') : {};
  const currentByUrl = new Map(currentItems.map(item => [item.link, normalizeItem(item)]));

  const liveRegion = document.getElementById('saveStatus');
  const drawer = document.getElementById('savedDrawer');
  const savedList = document.getElementById('savedList');
  const savedDrawerSubtitle = document.getElementById('savedDrawerSubtitle');
  const syncTitle = document.getElementById('syncTitle');
  const syncText = document.getElementById('syncText');
  const syncAction = document.getElementById('syncAction');

  const noteDialog = document.getElementById('noteDialog');
  const noteInput = document.getElementById('noteInput');
  const noteArticleTitle = document.getElementById('noteArticleTitle');
  const noteCount = document.getElementById('noteCount');
  const noteSaveButton = document.getElementById('noteSaveButton');

  const previewDialog = document.getElementById('previewDialog');
  const previewThumb = document.getElementById('previewThumb');
  const previewMediaLabel = document.getElementById('previewMediaLabel');
  const previewCategory = document.getElementById('previewCategory');
  const previewSource = document.getElementById('previewSource');
  const previewTitle = document.getElementById('previewTitle');
  const previewSummary = document.getElementById('previewSummary');
  const previewTakeaway = document.getElementById('previewTakeaway');
  const previewNoteWrap = document.getElementById('previewNoteWrap');
  const previewNote = document.getElementById('previewNote');
  const previewReadLink = document.getElementById('previewReadLink');
  const previewEditButton = document.getElementById('previewEditButton');
  const previewDeleteButton = document.getElementById('previewDeleteButton');

  const authDialog = document.getElementById('authDialog');
  const authGuestView = document.getElementById('authGuestView');
  const authUserView = document.getElementById('authUserView');
  const authSetupView = document.getElementById('authSetupView');
  const authForm = document.getElementById('authForm');
  const authEmail = document.getElementById('authEmail');
  const authPassword = document.getElementById('authPassword');
  const authSubmit = document.getElementById('authSubmit');
  const authMessage = document.getElementById('authMessage');
  const authIntent = document.getElementById('authIntent');
  const accountEmail = document.getElementById('accountEmail');

  let storageAvailable = true;
  // 기존 버전의 비로그인 저장 데이터는 localStorage에 남겨 두었다가 첫 로그인 때 이전합니다.
  // 새 저장은 로그인 후에만 허용하므로, 로그아웃 화면에서는 저장함을 비워 둡니다.
  let savedItems = [];
  let drawerTrigger = null;
  let noteTrigger = null;
  let previewTrigger = null;
  let authTrigger = null;
  let activeNoteUrl = '';
  let activePreviewUrl = '';
  let authMode = 'login';
  let currentUser = null;
  let supabaseClient = null;
  let syncBusy = false;
  let pendingSaveUrl = '';
  let pendingOpenSaved = false;

  const authEnabled = Boolean(authConfig.url && authConfig.publishableKey);

  function normalizeItem(item) {
    const now = new Date().toISOString();
    return {
      title: String(item && item.title || '').trim(),
      link: String(item && (item.link || item.article_url) || '').trim(),
      source: String(item && item.source || '기타').trim() || '기타',
      summary: String(item && item.summary || '').trim(),
      takeaway: String(item && item.takeaway || '').trim(),
      category: String(item && item.category || '생태계 업데이트').trim(),
      contentType: String(item && (item.contentType || item.content_type) || '기사').trim(),
      briefingDate: String(item && (item.briefingDate || item.briefing_date) || '').trim(),
      image: String(item && (item.image || item.thumbnail_url) || '').trim(),
      fallbackA: String(item && (item.fallbackA || item.fallback_a) || '#2752B8').trim(),
      fallbackB: String(item && (item.fallbackB || item.fallback_b) || '#6D9CFF').trim(),
      note: String(item && item.note || ''),
      savedAt: String(item && (item.savedAt || item.saved_at) || now),
      updatedAt: String(item && (item.updatedAt || item.updated_at) || now),
      pendingSync: Boolean(item && item.pendingSync),
    };
  }

  function timestamp(item) {
    const value = Date.parse(item.updatedAt || item.savedAt || '');
    return Number.isFinite(value) ? value : 0;
  }

  function dedupeItems(groups) {
    const map = new Map();
    groups.flat().forEach(raw => {
      const item = normalizeItem(raw);
      if (!item.link) return;
      const previous = map.get(item.link);
      if (!previous || timestamp(item) >= timestamp(previous)) map.set(item.link, item);
    });
    return Array.from(map.values()).sort((a, b) => timestamp(b) - timestamp(a));
  }

  function readStorage(key) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]');
      storageAvailable = true;
      return Array.isArray(parsed) ? dedupeItems([parsed]) : [];
    } catch (error) {
      storageAvailable = false;
      return [];
    }
  }

  function writeStorage(key, items) {
    try {
      localStorage.setItem(key, JSON.stringify(items));
      storageAvailable = true;
      return true;
    } catch (error) {
      storageAvailable = false;
      return false;
    }
  }

  function clearStorage(key) {
    try {
      localStorage.removeItem(key);
    } catch (error) {
      storageAvailable = false;
    }
  }

  function activeStorageKey() {
    return currentUser ? `${USER_STORAGE_PREFIX}${currentUser.id}` : GUEST_STORAGE_KEY;
  }

  function persistActive() {
    return writeStorage(activeStorageKey(), savedItems);
  }

  function announce(message) {
    if (!liveRegion) return;
    liveRegion.textContent = '';
    window.setTimeout(() => { liveRegion.textContent = message; }, 20);
  }

  function isOpen(element) {
    return Boolean(element && !element.hidden);
  }

  function syncBodyLock() {
    const locked = [drawer, noteDialog, previewDialog, authDialog].some(isOpen);
    document.body.classList.toggle('drawer-open', locked);
  }

  function itemForUrl(url) {
    return savedItems.find(item => item.link === url) || currentByUrl.get(url) || null;
  }

  function savedMap() {
    return new Map(savedItems.map(item => [item.link, item]));
  }

  function updateSavedIndicators() {
    const byUrl = savedMap();
    document.querySelectorAll('.save-button').forEach(button => {
      const savedItem = byUrl.get(button.dataset.url);
      const isSaved = Boolean(savedItem);
      const hasNote = Boolean(savedItem && savedItem.note.trim());
      button.classList.toggle('is-saved', isSaved);
      button.setAttribute('aria-pressed', String(isSaved));
      button.setAttribute(
        'aria-label',
        isSaved ? (hasNote ? '저장한 기사 메모 보기' : '저장한 기사에 메모 추가') : '기사 저장하기'
      );
      const label = button.querySelector('.save-label');
      if (label) label.textContent = isSaved ? (hasNote ? '메모 보기' : '메모 추가') : '저장';
    });
    document.querySelectorAll('[data-saved-count]').forEach(node => {
      node.textContent = String(byUrl.size);
    });
    if (savedDrawerSubtitle) {
      savedDrawerSubtitle.textContent = byUrl.size
        ? `${byUrl.size}개의 아티클을 모아두었어요.`
        : (currentUser ? '좋았던 아티클을 저장하고 메모를 남겨보세요.' : '로그인 후 나만의 저장함을 만들어보세요.');
    }
  }

  function shortAccountLabel(email) {
    if (!email) return '내 계정';
    const local = email.split('@')[0] || '내 계정';
    return local.length > 7 ? `${local.slice(0, 7)}…` : local;
  }

  function updateAuthIndicators() {
    const label = currentUser ? shortAccountLabel(currentUser.email) : '로그인';
    document.querySelectorAll('[data-auth-label]').forEach(node => { node.textContent = label; });

    if (!syncTitle || !syncText || !syncAction) return;
    if (!authEnabled) {
      syncTitle.textContent = '로그인 연결이 필요해요';
      syncText.textContent = 'Supabase 설정을 완료해야 저장함을 사용할 수 있어요.';
      syncAction.textContent = '설정 안내';
      return;
    }
    if (currentUser) {
      syncTitle.textContent = syncBusy ? '계정과 동기화 중…' : '계정에 안전하게 동기화';
      syncText.textContent = currentUser.email || '로그인된 계정';
      syncAction.textContent = '내 계정';
    } else {
      syncTitle.textContent = '로그인 후 저장 가능';
      syncText.textContent = '저장한 기사와 메모는 로그인한 계정에 동기화돼요.';
      syncAction.textContent = '로그인';
    }
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function isVideo(item) {
    const type = String(item.contentType || '').toLowerCase();
    const link = String(item.link || '').toLowerCase();
    return type.includes('영상') || type.includes('video') || link.includes('youtube.com') || link.includes('youtu.be');
  }

  function fillThumbnail(container, item) {
    if (!container) return;
    container.replaceChildren();
    container.classList.add('noimg');
    container.classList.toggle('is-video', isVideo(item));
    container.dataset.initial = (item.source || 'S').slice(0, 1);
    container.style.setProperty('--fallback', item.fallbackA || '#2752B8');
    container.style.setProperty('--fallback-2', item.fallbackB || '#6D9CFF');

    if (item.image) {
      const image = document.createElement('img');
      image.alt = '';
      image.loading = 'lazy';
      image.decoding = 'async';
      image.addEventListener('load', () => container.classList.remove('noimg'), { once: true });
      image.addEventListener('error', () => image.remove(), { once: true });
      image.src = item.image;
      container.append(image);
    }

    if (isVideo(item)) {
      const triangle = makeElement('span', 'play-triangle');
      triangle.setAttribute('aria-hidden', 'true');
      container.append(triangle);
    }
    if (container === previewThumb && previewMediaLabel) container.append(previewMediaLabel);
  }

  function renderSaved() {
    if (!savedList) return;
    savedList.replaceChildren();
    updateSavedIndicators();
    updateAuthIndicators();

    if (!storageAvailable) {
      savedList.append(makeElement('p', 'saved-empty', '현재 브라우저의 저장 공간을 사용할 수 없어요.'));
      return;
    }
    if (!savedItems.length) {
      savedList.append(makeElement('p', 'saved-empty', currentUser
        ? '아직 저장한 기사가 없어요. 카드 아래의 저장 버튼을 눌러보세요.'
        : '저장함은 로그인 후 사용할 수 있어요.'));
      return;
    }

    savedItems.forEach(item => {
      const article = makeElement('article', 'saved-item');
      const previewButton = makeElement('button', 'saved-preview-trigger');
      previewButton.type = 'button';
      previewButton.dataset.previewUrl = item.link;
      previewButton.setAttribute('aria-label', `${item.title || '저장한 기사'} 상세 보기`);

      const thumb = makeElement('span', 'saved-thumb');
      fillThumbnail(thumb, item);

      const copy = makeElement('span', 'saved-copy');
      const meta = makeElement('span', 'saved-meta', [item.briefingDate, item.source].filter(Boolean).join(' · '));
      const title = makeElement('span', 'saved-title', item.title || '제목 없음');
      copy.append(meta, title);

      if (item.note && item.note.trim()) {
        const notePreview = makeElement('span', 'saved-note-preview');
        const noteLabel = makeElement('strong', '', 'MY NOTE · ');
        notePreview.append(noteLabel, document.createTextNode(item.note.trim()));
        copy.append(notePreview);
      }
      copy.append(makeElement('span', 'saved-open-hint', '카드로 다시 보기 →'));
      previewButton.append(thumb, copy);

      const actions = makeElement('div', 'saved-actions');
      const previewAction = makeElement('button', 'saved-action-button preview-action', '상세 보기');
      previewAction.type = 'button';
      previewAction.dataset.previewUrl = item.link;
      const editButton = makeElement(
        'button',
        'saved-action-button edit-note',
        item.note && item.note.trim() ? '메모 수정' : '메모 추가'
      );
      editButton.type = 'button';
      editButton.dataset.editNoteUrl = item.link;
      const removeButton = makeElement('button', 'saved-action-button remove-saved', '삭제');
      removeButton.type = 'button';
      removeButton.dataset.removeUrl = item.link;
      actions.append(previewAction, editButton, removeButton);

      article.append(previewButton, actions);
      savedList.append(article);
    });
  }

  function setAuthIntent(message = '') {
    if (!authIntent) return;
    authIntent.textContent = message;
    authIntent.hidden = !message;
  }

  function requestLogin(intent, { saveUrl = '', openSaved = false } = {}) {
    pendingSaveUrl = saveUrl;
    pendingOpenSaved = openSaved;
    setAuthMode('login');
    openAuthDialog();
    setAuthIntent(intent);
    if (!authEnabled) announce('로그인 연결이 완료된 뒤 저장함을 사용할 수 있어요.');
  }

  function openDrawer() {
    if (!currentUser) {
      requestLogin('저장함은 로그인 후 사용할 수 있어요. 로그인하면 저장한 기사와 메모를 여러 기기에서 이어볼 수 있습니다.', { openSaved: true });
      return;
    }
    if (!drawer) return;
    drawerTrigger = document.activeElement;
    renderSaved();
    drawer.hidden = false;
    syncBodyLock();
    const closeButton = drawer.querySelector('.close-button');
    if (closeButton) closeButton.focus();
  }

  function closeDrawer(restoreFocus = true) {
    if (!drawer) return;
    drawer.hidden = true;
    syncBodyLock();
    if (restoreFocus && drawerTrigger && typeof drawerTrigger.focus === 'function') drawerTrigger.focus();
  }

  function updateNoteCount() {
    if (noteCount && noteInput) noteCount.textContent = String(noteInput.value.length);
  }

  function openNoteDialog(url) {
    if (!currentUser) {
      requestLogin('기사를 저장하려면 먼저 로그인해 주세요. 로그인하면 바로 스크랩 메모 화면으로 이어집니다.', { saveUrl: url });
      return;
    }
    if (!noteDialog || !noteInput) return;
    const item = itemForUrl(url);
    if (!item) return;
    const savedItem = savedItems.find(entry => entry.link === url);
    activeNoteUrl = url;
    noteTrigger = document.activeElement;
    if (noteArticleTitle) noteArticleTitle.textContent = item.title || '제목 없음';
    noteInput.value = savedItem ? savedItem.note : '';
    if (noteSaveButton) noteSaveButton.textContent = savedItem ? '메모 저장' : '스크랩 저장';
    updateNoteCount();
    noteDialog.hidden = false;
    syncBodyLock();
    window.setTimeout(() => noteInput.focus(), 40);
  }

  function closeNoteDialog(restoreFocus = true) {
    if (!noteDialog) return;
    noteDialog.hidden = true;
    activeNoteUrl = '';
    syncBodyLock();
    if (restoreFocus && noteTrigger && typeof noteTrigger.focus === 'function') noteTrigger.focus();
  }

  function renderPreview(item) {
    if (!item) return;
    fillThumbnail(previewThumb, item);
    if (previewMediaLabel) previewMediaLabel.textContent = item.contentType || '기사';
    if (previewCategory) previewCategory.textContent = item.category || '생태계 업데이트';
    if (previewSource) previewSource.textContent = item.source || '기타';
    if (previewTitle) previewTitle.textContent = item.title || '제목 없음';
    if (previewSummary) previewSummary.textContent = item.summary || '';
    if (previewTakeaway) {
      previewTakeaway.textContent = item.takeaway || '원문에서 이번 변화가 창업가와 팀에 주는 의미를 확인해보세요.';
    }
    if (previewNoteWrap && previewNote) {
      const hasNote = Boolean(item.note && item.note.trim());
      previewNoteWrap.hidden = !hasNote;
      previewNote.textContent = hasNote ? item.note.trim() : '';
    }
    if (previewReadLink) previewReadLink.href = item.link;
    if (previewEditButton) previewEditButton.dataset.previewEditUrl = item.link;
    if (previewDeleteButton) previewDeleteButton.dataset.previewDeleteUrl = item.link;
  }

  function openPreview(url) {
    if (!previewDialog) return;
    const item = itemForUrl(url);
    if (!item) return;
    activePreviewUrl = url;
    previewTrigger = document.activeElement;
    renderPreview(item);
    previewDialog.hidden = false;
    syncBodyLock();
    const closeButton = previewDialog.querySelector('.close-button');
    if (closeButton) closeButton.focus();
  }

  function closePreview(restoreFocus = true) {
    if (!previewDialog) return;
    previewDialog.hidden = true;
    activePreviewUrl = '';
    syncBodyLock();
    if (restoreFocus && previewTrigger && typeof previewTrigger.focus === 'function') previewTrigger.focus();
  }

  function remoteRowToItem(row) {
    return normalizeItem({
      title: row.title,
      link: row.article_url,
      source: row.source,
      summary: row.summary,
      takeaway: row.takeaway,
      category: row.category,
      contentType: row.content_type,
      briefingDate: row.briefing_date,
      image: row.thumbnail_url,
      fallbackA: row.fallback_a,
      fallbackB: row.fallback_b,
      note: row.note,
      savedAt: row.saved_at,
      updatedAt: row.updated_at,
      pendingSync: false,
    });
  }

  function itemToRemote(item) {
    return {
      user_id: currentUser.id,
      article_url: item.link,
      title: item.title || '제목 없음',
      source: item.source || '기타',
      summary: item.summary || '',
      takeaway: item.takeaway || '',
      category: item.category || '생태계 업데이트',
      content_type: item.contentType || '기사',
      briefing_date: item.briefingDate || '',
      thumbnail_url: item.image || '',
      fallback_a: item.fallbackA || '#2752B8',
      fallback_b: item.fallbackB || '#6D9CFF',
      note: item.note || '',
      saved_at: item.savedAt || new Date().toISOString(),
      updated_at: item.updatedAt || new Date().toISOString(),
    };
  }

  async function upsertItemsToCloud(items) {
    if (!supabaseClient || !currentUser || !items.length) return true;
    const { error } = await supabaseClient
      .from('saved_articles')
      .upsert(items.map(itemToRemote), { onConflict: 'user_id,article_url' });
    if (error) {
      console.error('SNAAC saved article upsert failed:', error);
      return false;
    }
    return true;
  }

  async function syncSavedFromCloud() {
    if (!supabaseClient || !currentUser || syncBusy) return;
    syncBusy = true;
    updateAuthIndicators();

    const userKey = activeStorageKey();
    const userLocal = readStorage(userKey);
    const pendingLocal = userLocal.filter(item => item.pendingSync);
    const guestItems = readStorage(GUEST_STORAGE_KEY);

    const { data, error } = await supabaseClient
      .from('saved_articles')
      .select('*')
      .order('saved_at', { ascending: false });

    if (error) {
      console.error('SNAAC saved article fetch failed:', error);
      savedItems = dedupeItems([userLocal, guestItems]);
      writeStorage(userKey, savedItems);
      syncBusy = false;
      updateSavedIndicators();
      renderSaved();
      announce('계정 동기화에 실패했지만 이 기기에는 저장되어 있어요.');
      return;
    }

    const remoteItems = (data || []).map(remoteRowToItem);
    savedItems = dedupeItems([remoteItems, pendingLocal, guestItems]).map(item => ({ ...item, pendingSync: true }));
    writeStorage(userKey, savedItems);

    const uploaded = await upsertItemsToCloud(savedItems);
    if (uploaded) {
      savedItems = savedItems.map(item => ({ ...item, pendingSync: false }));
      writeStorage(userKey, savedItems);
      clearStorage(GUEST_STORAGE_KEY);
    }

    syncBusy = false;
    updateSavedIndicators();
    renderSaved();
    if (!uploaded) announce('기기 저장은 완료됐지만 계정 동기화를 다시 시도해 주세요.');
  }

  async function saveWithNote() {
    if (!activeNoteUrl || !noteInput) return;
    if (!currentUser) {
      const requestedUrl = activeNoteUrl;
      closeNoteDialog(false);
      requestLogin('기사를 저장하려면 먼저 로그인해 주세요. 로그인하면 바로 스크랩 메모 화면으로 이어집니다.', { saveUrl: requestedUrl });
      return;
    }
    const existingIndex = savedItems.findIndex(item => item.link === activeNoteUrl);
    const currentItem = currentByUrl.get(activeNoteUrl);
    const existingItem = existingIndex >= 0 ? savedItems[existingIndex] : null;
    const item = currentItem || existingItem;
    if (!item) return;

    const note = noteInput.value.trim();
    const now = new Date().toISOString();
    const nextItem = normalizeItem({
      ...(existingItem || {}),
      ...(currentItem || {}),
      note,
      savedAt: existingItem && existingItem.savedAt || now,
      updatedAt: now,
      pendingSync: Boolean(currentUser),
    });

    if (existingIndex >= 0) savedItems.splice(existingIndex, 1);
    savedItems.unshift(nextItem);
    savedItems = dedupeItems([savedItems]);

    if (!persistActive()) {
      announce('이 브라우저에서는 저장 기능을 사용할 수 없어요.');
      return;
    }

    closeNoteDialog();
    updateSavedIndicators();
    renderSaved();
    if (activePreviewUrl === nextItem.link) renderPreview(nextItem);

    if (currentUser) {
      const uploaded = await upsertItemsToCloud([nextItem]);
      if (uploaded) {
        const saved = savedItems.find(savedItem => savedItem.link === nextItem.link);
        if (saved) saved.pendingSync = false;
        persistActive();
        announce(note ? '메모와 함께 계정에 저장했어요.' : '기사를 계정에 저장했어요.');
      } else {
        announce('이 기기에는 저장했지만 계정 동기화에 실패했어요.');
      }
    }
  }

  async function removeSaved(url) {
    savedItems = savedItems.filter(item => item.link !== url);
    if (!persistActive()) {
      announce('이 브라우저에서는 저장 기능을 사용할 수 없어요.');
      return;
    }

    if (activeNoteUrl === url && isOpen(noteDialog)) closeNoteDialog(false);
    if (activePreviewUrl === url && isOpen(previewDialog)) closePreview(false);
    updateSavedIndicators();
    renderSaved();

    if (currentUser && supabaseClient) {
      const { error } = await supabaseClient
        .from('saved_articles')
        .delete()
        .eq('user_id', currentUser.id)
        .eq('article_url', url);
      if (error) {
        console.error('SNAAC saved article delete failed:', error);
        announce('기기에서는 삭제했지만 계정 동기화에 실패했어요.');
        return;
      }
    }
    announce('저장함에서 삭제했어요.');
  }

  function setAuthMode(mode) {
    authMode = mode === 'signup' ? 'signup' : 'login';
    document.querySelectorAll('[data-auth-mode]').forEach(button => {
      const active = button.dataset.authMode === authMode;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
    if (authSubmit) authSubmit.textContent = authMode === 'signup' ? '회원가입' : '로그인';
    if (authPassword) authPassword.autocomplete = authMode === 'signup' ? 'new-password' : 'current-password';
    if (authMessage) {
      authMessage.textContent = '';
      authMessage.classList.remove('is-error');
    }
  }

  function updateAuthDialogView() {
    if (!authGuestView || !authUserView || !authSetupView) return;
    authSetupView.hidden = authEnabled;
    authGuestView.hidden = !authEnabled || Boolean(currentUser);
    authUserView.hidden = !authEnabled || !currentUser;
    if (accountEmail) accountEmail.textContent = currentUser && currentUser.email || '';
  }

  function openAuthDialog() {
    if (!authDialog) return;
    authTrigger = document.activeElement;
    updateAuthDialogView();
    setAuthMode(authMode);
    authDialog.hidden = false;
    syncBodyLock();
    window.setTimeout(() => {
      if (currentUser) {
        const logout = authDialog.querySelector('[data-logout]');
        if (logout) logout.focus();
      } else if (authEnabled && authEmail) {
        authEmail.focus();
      } else {
        const closeButton = authDialog.querySelector('.close-button');
        if (closeButton) closeButton.focus();
      }
    }, 40);
  }

  function closeAuthDialog(restoreFocus = true, preserveIntent = false) {
    if (!authDialog) return;
    authDialog.hidden = true;
    if (!preserveIntent && !currentUser) {
      pendingSaveUrl = '';
      pendingOpenSaved = false;
      setAuthIntent('');
    }
    syncBodyLock();
    if (restoreFocus && authTrigger && typeof authTrigger.focus === 'function') authTrigger.focus();
  }

  function setAuthMessage(message, isError = false) {
    if (!authMessage) return;
    authMessage.textContent = message;
    authMessage.classList.toggle('is-error', isError);
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    if (!supabaseClient || !authEmail || !authPassword || !authSubmit) return;
    const email = authEmail.value.trim();
    const password = authPassword.value;
    if (!email || !password) {
      setAuthMessage('이메일과 비밀번호를 모두 입력해 주세요.', true);
      return;
    }
    if (password.length < 8) {
      setAuthMessage('비밀번호는 8자 이상으로 입력해 주세요.', true);
      return;
    }

    authSubmit.disabled = true;
    setAuthMessage(authMode === 'signup' ? '계정을 만들고 있어요…' : '로그인하고 있어요…');
    try {
      if (authMode === 'signup') {
        const redirectTo = authConfig.redirectUrl || new URL(authConfig.homeHref || './', window.location.href).href;
        const { data, error } = await supabaseClient.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: redirectTo },
        });
        if (error) throw error;
        if (data && data.session) {
          setAuthMessage('회원가입과 로그인이 완료됐어요.');
          closeAuthDialog(true, true);
        } else {
          setAuthMessage('확인 메일을 보냈어요. 메일의 링크를 누른 뒤 로그인해 주세요.');
        }
      } else {
        const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw error;
        setAuthMessage('로그인했어요. 저장함을 동기화합니다.');
        closeAuthDialog(true, true);
      }
    } catch (error) {
      console.error('SNAAC auth error:', error);
      setAuthMessage(error && error.message ? error.message : '로그인 처리 중 오류가 발생했어요.', true);
    } finally {
      authSubmit.disabled = false;
    }
  }

  async function handleSignOut() {
    if (!supabaseClient) return;
    const { error } = await supabaseClient.auth.signOut();
    if (error) {
      announce('로그아웃하지 못했어요. 잠시 후 다시 시도해 주세요.');
      return;
    }
    closeAuthDialog();
  }

  async function applySession(session) {
    const nextUser = session && session.user || null;
    const previousId = currentUser && currentUser.id || '';
    const nextId = nextUser && nextUser.id || '';
    currentUser = nextUser;
    updateAuthDialogView();
    updateAuthIndicators();

    if (nextUser) {
      if (nextId !== previousId || !savedItems.length) await syncSavedFromCloud();
      const saveUrl = pendingSaveUrl;
      const shouldOpenSaved = pendingOpenSaved;
      pendingSaveUrl = '';
      pendingOpenSaved = false;
      setAuthIntent('');
      if (saveUrl) window.setTimeout(() => openNoteDialog(saveUrl), 20);
      else if (shouldOpenSaved) window.setTimeout(() => openDrawer(), 20);
    } else {
      savedItems = [];
      updateSavedIndicators();
      renderSaved();
    }
  }

  async function initSupabase() {
    updateAuthDialogView();
    updateAuthIndicators();
    if (!authEnabled) return;
    if (!window.supabase || typeof window.supabase.createClient !== 'function') {
      console.error('Supabase library did not load.');
      return;
    }

    supabaseClient = window.supabase.createClient(authConfig.url, authConfig.publishableKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });

    const { data, error } = await supabaseClient.auth.getSession();
    if (error) console.error('Supabase session error:', error);
    await applySession(data && data.session || null);

    supabaseClient.auth.onAuthStateChange((_event, session) => {
      window.setTimeout(() => { void applySession(session); }, 0);
    });
  }

  document.addEventListener('click', event => {
    const saveButton = event.target.closest('.save-button');
    if (saveButton) {
      openNoteDialog(saveButton.dataset.url);
      return;
    }

    const previewButton = event.target.closest('[data-preview-url]');
    if (previewButton) {
      openPreview(previewButton.dataset.previewUrl);
      return;
    }

    const editNoteButton = event.target.closest('[data-edit-note-url]');
    if (editNoteButton) {
      openNoteDialog(editNoteButton.dataset.editNoteUrl);
      return;
    }

    const saveNoteButton = event.target.closest('[data-save-note]');
    if (saveNoteButton) {
      void saveWithNote();
      return;
    }

    const closeNoteButton = event.target.closest('[data-close-note]');
    if (closeNoteButton) {
      closeNoteDialog();
      return;
    }

    const openSavedButton = event.target.closest('[data-open-saved]');
    if (openSavedButton) {
      openDrawer();
      return;
    }

    const closeSavedButton = event.target.closest('[data-close-saved]');
    if (closeSavedButton) {
      closeDrawer();
      return;
    }

    const removeButton = event.target.closest('[data-remove-url]');
    if (removeButton) {
      void removeSaved(removeButton.dataset.removeUrl);
      return;
    }

    const closePreviewButton = event.target.closest('[data-close-preview]');
    if (closePreviewButton) {
      closePreview();
      return;
    }

    const previewEditButtonTarget = event.target.closest('[data-preview-edit-url]');
    if (previewEditButtonTarget) {
      openNoteDialog(previewEditButtonTarget.dataset.previewEditUrl);
      return;
    }

    const previewDeleteButtonTarget = event.target.closest('[data-preview-delete-url]');
    if (previewDeleteButtonTarget) {
      void removeSaved(previewDeleteButtonTarget.dataset.previewDeleteUrl);
      return;
    }

    const openAuthButton = event.target.closest('[data-open-auth]');
    if (openAuthButton) {
      pendingSaveUrl = '';
      pendingOpenSaved = false;
      setAuthIntent('');
      openAuthDialog();
      return;
    }

    const closeAuthButton = event.target.closest('[data-close-auth]');
    if (closeAuthButton) {
      closeAuthDialog();
      return;
    }

    const authTab = event.target.closest('[data-auth-mode]');
    if (authTab) {
      setAuthMode(authTab.dataset.authMode);
      return;
    }

    const logoutButton = event.target.closest('[data-logout]');
    if (logoutButton) void handleSignOut();
  });

  if (noteInput) {
    noteInput.addEventListener('input', updateNoteCount);
    noteInput.addEventListener('keydown', event => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        void saveWithNote();
      }
    });
  }

  if (authForm) authForm.addEventListener('submit', event => { void handleAuthSubmit(event); });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (isOpen(authDialog)) closeAuthDialog();
    else if (isOpen(noteDialog)) closeNoteDialog();
    else if (isOpen(previewDialog)) closePreview();
    else if (isOpen(drawer)) closeDrawer();
  });

  window.addEventListener('storage', () => {
    savedItems = readStorage(activeStorageKey());
    updateSavedIndicators();
    renderSaved();
    if (activePreviewUrl) {
      const item = itemForUrl(activePreviewUrl);
      if (item) renderPreview(item);
      else closePreview(false);
    }
  });

  setAuthMode('login');
  updateSavedIndicators();
  renderSaved();
  void initSupabase();
})();"""


def _safe_json_for_script(data: object) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _public_image_url(value: object) -> str | None:
    url = html.unescape(str(value or "").strip())
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return url if parts.scheme in {"http", "https"} and parts.netloc else None


def _youtube_video_id(url: str) -> str | None:
    """YouTube watch/shorts/embed/live/youtu.be URL에서 영상 ID를 추출합니다."""
    try:
        parts = urlsplit(url)
        host = parts.netloc.lower().split(":", 1)[0]
        for prefix in ("www.", "m.", "music."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        segments = [segment for segment in parts.path.split("/") if segment]

        video_id: str | None = None
        if host == "youtu.be" and segments:
            video_id = segments[0]
        elif host == "youtube.com" or host.endswith(".youtube.com"):
            if parts.path.rstrip("/") == "/watch":
                video_id = (parse_qs(parts.query).get("v") or [None])[0]
            elif segments and segments[0] in {"shorts", "embed", "live", "v"}:
                video_id = segments[1] if len(segments) > 1 else None

        if video_id and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
            return video_id
    except (TypeError, ValueError):
        return None
    return None


def _youtube_thumbnail(url: str) -> str | None:
    video_id = _youtube_video_id(url)
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None


def fetch_og_image(url: str) -> str | None:
    """공개 원문의 OG 이미지 URL만 추출합니다. 이미지 파일은 저장하지 않습니다.

    YouTube는 공개 영상 ID로 공식 썸네일 CDN 주소를 구성하므로, EO Korea 영상도
    원문 썸네일이 안정적으로 표시됩니다.
    """
    youtube_image = _youtube_thumbnail(url)
    if youtube_image:
        return youtube_image

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SNAACBriefingBot/4.0)",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            },
        )
        response.raise_for_status()
        patterns = [
            r"<meta[^>]+property=[\"\']og:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']",
            r"<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+property=[\"\']og:image[\"\']",
            r"<meta[^>]+name=[\"\']twitter:image[\"\'][^>]+content=[\"\']([^\"\']+)[\"\']",
            r"<meta[^>]+content=[\"\']([^\"\']+)[\"\'][^>]+name=[\"\']twitter:image[\"\']",
        ]
        for pattern in patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if not match:
                continue
            image_url = urljoin(response.url or url, html.unescape(match.group(1).strip()))
            public_url = _public_image_url(image_url)
            if public_url:
                return public_url
    except requests.RequestException as exc:
        print(f"[썸네일 스킵] {url}: {exc}")
    return None


def _source_gradient(source: str) -> tuple[str, str]:
    """원본 썸네일이 없을 때만 사용하는, 출처별 안정적인 컬러 폴백입니다."""
    source = source.strip()
    if source in SOURCE_GRADIENTS:
        return SOURCE_GRADIENTS[source]

    lower = source.lower()
    if "linkedin" in lower or "링크드인" in source:
        return SOURCE_GRADIENTS["LinkedIn"]
    if "youtube" in lower or "유튜브" in source:
        return SOURCE_GRADIENTS["YouTube"]
    if lower.startswith("eo"):
        return SOURCE_GRADIENTS["EO"]
    if "a16z" in lower:
        return SOURCE_GRADIENTS["a16z"]

    score = sum((index + 1) * ord(char) for index, char in enumerate(source or "SNAAC"))
    return FALLBACK_GRADIENTS[score % len(FALLBACK_GRADIENTS)]


def _prepare_picks(
    picks: list[dict],
    date_label: str,
    *,
    image_hints: dict[str, str] | None = None,
    fetch_missing_images: bool = True,
) -> list[dict]:
    prepared: list[dict] = []
    hints = image_hints or {}

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
        fallback_a, fallback_b = _source_gradient(item["source"])
        item["fallback_a"] = fallback_a
        item["fallback_b"] = fallback_b

        supplied_image = _public_image_url(pick.get("image") or pick.get("thumbnail"))
        hinted_image = _public_image_url(hints.get(item["link"]))
        youtube_image = _youtube_thumbnail(item["link"])
        image = supplied_image or hinted_image or youtube_image
        if not image and SHOW_THUMBNAILS and fetch_missing_images:
            image = fetch_og_image(item["link"])
        item["image"] = image
        prepared.append(item)
    return prepared


def _bookmark_icon() -> str:
    return (
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M6.5 4.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16l-5.5-3.2-5.5 3.2z"/>'
        "</svg>"
    )


def _is_video_pick(pick: dict) -> bool:
    content_type = str(pick.get("content_type", "")).lower()
    return (
        "영상" in content_type
        or "video" in content_type
        or _youtube_video_id(str(pick.get("link", ""))) is not None
    )


def _card(index: int, total: int, pick: dict) -> str:
    title = html.escape(pick["title"])
    summary = html.escape(pick["summary"])
    takeaway = html.escape(
        pick["takeaway"]
        or "원문에서 이번 변화가 스타트업과 창업가에게 주는 의미를 확인해보세요."
    )
    source = html.escape(pick["source"])
    fallback_a = html.escape(pick.get("fallback_a", "#2752B8"), quote=True)
    fallback_b = html.escape(pick.get("fallback_b", "#6D9CFF"), quote=True)
    category = html.escape(pick["category"])
    content_type = html.escape(pick["content_type"])
    link = html.escape(pick["link"], quote=True)
    initial = html.escape((pick["source"] or "S")[0])
    is_video = _is_video_pick(pick)

    if pick.get("image"):
        image = html.escape(str(pick["image"]), quote=True)
        thumb_inner = (
            f'<img src="{image}" alt="" loading="lazy" decoding="async" '
            'onerror="this.parentElement.classList.add(\'noimg\');this.remove()">'
        )
        thumb_classes = "thumb"
    else:
        thumb_inner = ""
        thumb_classes = "thumb noimg"

    if is_video:
        thumb_classes += " is-video"
        thumb_inner += '<span class="play-triangle" aria-hidden="true"></span>'

    return f"""
<article class="card">
  <a class="{thumb_classes}" href="{link}" target="_blank" rel="noopener noreferrer" data-initial="{initial}" style="--fallback:{fallback_a};--fallback-2:{fallback_b}" aria-label="{title} 원문 열기">
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

        week_number = ((date.day - 1) // 7) + 1
        entries.append(
            {
                "slug": slug,
                "label": f"{date.month}월 {date.day}일",
                "day_label": f"{date.month}월 {date.day}일 {WEEKDAYS[date.weekday()]}요일",
                "full_label": f"{date.year}년 {date.month}월 {date.day}일",
                "month_key": date.strftime("%Y-%m"),
                "month_label": f"{date.month}월 브리핑",
                "year_label": f"{date.year}년",
                "week_number": week_number,
                "week_label": f"{week_number}주차 브리핑",
                "count": count,
                "date": date,
            }
        )
    return entries


def _archive_tree(entries: list[dict], item_prefix: str = "", *, compact: bool = False) -> str:
    """아카이브를 월 → 주차 → 날짜 순의 details 서랍으로 렌더링합니다."""
    if not entries:
        return '<p class="empty-archive">지난 브리핑이 쌓이면 이곳에서 다시 볼 수 있어요.</p>'

    months: dict[str, dict] = {}
    for entry in entries:
        month = months.setdefault(
            entry["month_key"],
            {
                "label": entry["month_label"],
                "year": entry["year_label"],
                "entries": [],
                "weeks": {},
            },
        )
        month["entries"].append(entry)
        month["weeks"].setdefault(entry["week_number"], []).append(entry)

    month_blocks: list[str] = []
    for month_index, month in enumerate(months.values()):
        week_blocks: list[str] = []
        for week_index, (week_number, week_entries) in enumerate(month["weeks"].items()):
            dates = [entry["date"] for entry in week_entries]
            start = min(dates)
            end = max(dates)
            range_label = (
                f"{start.month}/{start.day} · 1회"
                if start.date() == end.date()
                else f"{start.month}/{start.day}–{end.month}/{end.day} · {len(week_entries)}회"
            )
            day_rows = "".join(
                f'<a class="archive-day-row" href="{item_prefix}{entry["slug"]}.html">'
                f'<span class="archive-day-date">{entry["day_label"]}</span>'
                f'<span class="archive-day-count">{entry["count"]}개의 큐레이션</span>'
                '<span class="archive-day-arrow" aria-hidden="true">→</span>'
                '</a>'
                for entry in week_entries
            )
            week_open = " open" if month_index == 0 and week_index == 0 else ""
            week_blocks.append(
                f'<details class="archive-week"{week_open}>'
                '<summary class="archive-summary archive-week-summary">'
                '<span class="archive-summary-copy">'
                f'<span class="archive-summary-title">{week_number}주차 브리핑</span>'
                f'<span class="archive-summary-meta">{range_label}</span>'
                '</span><span class="archive-chevron" aria-hidden="true">⌄</span>'
                '</summary>'
                f'<div class="archive-day-list">{day_rows}</div>'
                '</details>'
            )

        month_open = " open" if month_index == 0 else ""
        month_blocks.append(
            f'<details class="archive-month"{month_open}>'
            '<summary class="archive-summary archive-month-summary">'
            '<span class="archive-summary-copy">'
            f'<span class="archive-summary-title">{month["label"]}</span>'
            f'<span class="archive-summary-meta">{month["year"]} · {len(month["entries"])}회</span>'
            '</span><span class="archive-chevron" aria-hidden="true">⌄</span>'
            '</summary>'
            f'<div class="archive-month-body">{"".join(week_blocks)}</div>'
            '</details>'
        )

    compact_class = " archive-tree-compact" if compact else ""
    return f'<div class="archive-tree{compact_class}">{"".join(month_blocks)}</div>'


def _archive_section(today_slug: str, context: str) -> str:
    entries = _archive_entries(exclude_slug=today_slug)[:ARCHIVE_KEEP]
    if context == "home":
        item_prefix = "archive/"
        index_href = "archive/"
    else:
        item_prefix = ""
        index_href = "./"

    tree = _archive_tree(entries, item_prefix, compact=True)
    return f"""
<section class="archive-section" id="archive">
  <div class="section-head">
    <h2>지난 브리핑</h2>
    <a href="{index_href}">전체 보기 →</a>
  </div>
  {tree}
</section>"""


def _about_snaac_section() -> str:
    return """
<section class="about-snaac-section" aria-label="SNAAC 소개">
  <a class="about-snaac-card" href="https://www.snaac.co.kr" target="_blank" rel="noopener noreferrer">
    <span class="about-snaac-eyebrow">ABOUT SNAAC</span>
    <span class="about-snaac-title">SNAAC을 더 알아보세요</span>
    <span class="about-snaac-copy">대학 스타트업 동아리 SNAAC의 활동과 소식을 공식 홈페이지에서 확인할 수 있어요.</span>
  </a>
</section>"""


def _logo_html(context: str) -> str:
    asset_prefix = "" if context == "home" else "../"
    home_href = "./" if context == "home" else "../"
    return (
        '<div class="logo-row">'
        f'<a class="logo-link" href="{home_href}" aria-label="SNAAC 오늘 브리핑">'
        f'<img class="site-logo" src="{asset_prefix}assets/{LOGO_ASSET_NAME}" '
        'alt="SNAAC" width="932" height="232">'
        '</a></div>'
    )


def _header_html(context: str) -> str:
    if context == "home":
        archive_href = "archive/"
        left_label = "지난 회차"
        left_symbol = "↺"
    else:
        archive_href = "../"
        left_label = "오늘"
        left_symbol = "←"

    return f"""
{_logo_html(context)}
<div class="topline">
  <a class="utility-button" href="{archive_href}" aria-label="{html.escape(left_label)} 보기"><span>{html.escape(left_label)}</span><span aria-hidden="true">{left_symbol}</span></a>
  <button class="utility-button saved-vault" type="button" data-open-saved>{_bookmark_icon()}<span>저장함</span><span class="count-badge" data-saved-count>0</span></button>
  <button class="utility-button auth-control" type="button" data-open-auth aria-label="로그인 또는 내 계정"><span aria-hidden="true">◎</span><span data-auth-label>로그인</span></button>
</div>"""


def _overlays_html() -> str:
    return f"""
<button class="floating-saved" type="button" data-open-saved aria-label="저장함 열기">
  {_bookmark_icon()}<span>내 저장함</span><span class="count-badge" data-saved-count>0</span>
</button>

<div class="drawer" id="savedDrawer" hidden>
  <button class="drawer-backdrop" type="button" data-close-saved aria-label="저장함 닫기"></button>
  <section class="drawer-panel" role="dialog" aria-modal="true" aria-labelledby="savedTitle">
    <div class="drawer-handle" aria-hidden="true"></div>
    <div class="drawer-head">
      <div class="drawer-title-wrap">
        <h2 id="savedTitle">{_bookmark_icon()} 내 저장함</h2>
        <p class="drawer-subtitle" id="savedDrawerSubtitle">좋았던 아티클을 저장하고 메모를 남겨보세요.</p>
      </div>
      <button class="close-button" type="button" data-close-saved aria-label="닫기">×</button>
    </div>
    <div class="sync-strip">
      <div class="sync-copy">
        <p class="sync-title" id="syncTitle">계정 저장함</p>
        <p class="sync-text" id="syncText">로그인한 계정에서만 기사와 메모를 저장할 수 있어요.</p>
      </div>
      <button class="sync-action" id="syncAction" type="button" data-open-auth>로그인</button>
    </div>
    <div class="saved-list" id="savedList"></div>
  </section>
</div>

<div class="note-dialog" id="noteDialog" hidden>
  <button class="note-backdrop" type="button" data-close-note aria-label="스크랩 메모 닫기"></button>
  <section class="note-panel" role="dialog" aria-modal="true" aria-labelledby="noteTitle" aria-describedby="noteHelp">
    <div class="drawer-handle" aria-hidden="true"></div>
    <div class="note-head">
      <h2 id="noteTitle">스크랩 메모</h2>
      <button class="close-button" type="button" data-close-note aria-label="닫기">×</button>
    </div>
    <p class="note-article-title" id="noteArticleTitle"></p>
    <label class="note-label" for="noteInput">
      <span>이 기사를 저장한 이유 <span class="note-optional">선택</span></span>
      <span class="note-count"><span id="noteCount">0</span>/500</span>
    </label>
    <textarea class="note-input" id="noteInput" maxlength="500" placeholder="예: 다음 기획 회의에서 리텐션 사례로 다시 보기"></textarea>
    <p class="note-help" id="noteHelp">메모를 비워둔 채 기사만 저장해도 됩니다.</p>
    <div class="note-actions">
      <button class="note-button" type="button" data-close-note>취소</button>
      <button class="note-button note-button-primary" id="noteSaveButton" type="button" data-save-note>스크랩 저장</button>
    </div>
  </section>
</div>

<div class="preview-dialog" id="previewDialog" hidden>
  <button class="preview-backdrop" type="button" data-close-preview aria-label="저장한 기사 상세 닫기"></button>
  <section class="preview-panel" role="dialog" aria-modal="true" aria-labelledby="previewDialogTitle">
    <div class="drawer-handle" aria-hidden="true"></div>
    <div class="preview-head">
      <h2 id="previewDialogTitle">저장한 아티클</h2>
      <button class="close-button" type="button" data-close-preview aria-label="닫기">×</button>
    </div>
    <article class="preview-card">
      <div class="preview-thumb noimg" id="previewThumb" data-initial="S">
        <span class="media-label" id="previewMediaLabel">기사</span>
      </div>
      <div class="preview-body">
        <div class="card-meta">
          <div class="meta-left">
            <span class="category" id="previewCategory">생태계 업데이트</span>
            <span class="source" id="previewSource">SNAAC</span>
          </div>
        </div>
        <h3 id="previewTitle">저장한 기사</h3>
        <p class="preview-summary" id="previewSummary"></p>
        <div class="takeaway">
          <span class="takeaway-label">WHY IT MATTERS</span>
          <p id="previewTakeaway"></p>
        </div>
        <div class="preview-note" id="previewNoteWrap" hidden>
          <strong>MY NOTE</strong><span id="previewNote"></span>
        </div>
        <div class="preview-actions">
          <a class="preview-read" id="previewReadLink" href="#" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a>
          <button class="preview-secondary" id="previewEditButton" type="button">메모 수정</button>
        </div>
        <button class="preview-delete" id="previewDeleteButton" type="button">저장함에서 삭제</button>
      </div>
    </article>
  </section>
</div>

<div class="auth-dialog" id="authDialog" hidden>
  <button class="auth-backdrop" type="button" data-close-auth aria-label="로그인 창 닫기"></button>
  <section class="auth-panel" role="dialog" aria-modal="true" aria-labelledby="authTitle">
    <div class="drawer-handle" aria-hidden="true"></div>
    <div class="auth-head">
      <h2 id="authTitle">SNAAC 계정</h2>
      <button class="close-button" type="button" data-close-auth aria-label="닫기">×</button>
    </div>
    <div class="auth-content">
      <div id="authGuestView">
        <p class="auth-intent" id="authIntent" hidden></p>
        <div class="auth-tabs" role="tablist" aria-label="로그인 방식">
          <button class="auth-tab is-active" type="button" role="tab" data-auth-mode="login" aria-selected="true">로그인</button>
          <button class="auth-tab" type="button" role="tab" data-auth-mode="signup" aria-selected="false">회원가입</button>
        </div>
        <form class="auth-form" id="authForm">
          <label class="auth-label" for="authEmail">이메일</label>
          <input class="auth-input" id="authEmail" type="email" inputmode="email" autocomplete="email" required placeholder="name@example.com">
          <label class="auth-label" for="authPassword">비밀번호</label>
          <input class="auth-input" id="authPassword" type="password" minlength="8" autocomplete="current-password" required placeholder="8자 이상">
          <button class="auth-submit" id="authSubmit" type="submit">로그인</button>
          <p class="auth-message" id="authMessage" aria-live="polite"></p>
          <p class="auth-help">로그인하면 저장한 기사와 메모가 계정에 동기화되어 다른 기기에서도 이어볼 수 있어요.</p>
        </form>
      </div>
      <div id="authUserView" hidden>
        <div class="account-card">
          <p class="account-eyebrow">SIGNED IN AS</p>
          <p class="account-email" id="accountEmail"></p>
          <p class="account-copy">저장한 기사와 메모를 이 계정으로 동기화하고 있어요.</p>
        </div>
        <button class="account-logout" type="button" data-logout>로그아웃</button>
      </div>
      <div id="authSetupView" hidden>
        <div class="auth-setup-note">
          <h3>로그인 연결 전이에요</h3>
          <p>기사 저장과 저장함을 사용하려면 Supabase 로그인 연결이 필요합니다. 운영자가 공개 설정을 연결한 뒤 다시 시도해 주세요.</p>
        </div>
      </div>
    </div>
  </section>
</div>

<p class="sr-only" id="saveStatus" aria-live="polite"></p>
"""


def _auth_config(context: str) -> dict:
    return {
        "url": SUPABASE_URL if AUTH_ENABLED else "",
        "publishableKey": SUPABASE_PUBLISHABLE_KEY if AUTH_ENABLED else "",
        "redirectUrl": SUPABASE_REDIRECT_URL,
        "homeHref": "./" if context == "home" else "../",
    }


def _supabase_script() -> str:
    if not AUTH_ENABLED:
        return ""
    return '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'


def _page_html(picks: list[dict], now: datetime, context: str) -> str:
    date_big = f"{now.month}.{now.day}."
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    slug = now.strftime("%Y-%m-%d")
    total = len(picks)
    cards = "".join(_card(index, total, pick) for index, pick in enumerate(picks, 1))

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
            "image": pick.get("image") or "",
            "fallbackA": pick.get("fallback_a", "#2752B8"),
            "fallbackB": pick.get("fallback_b", "#6D9CFF"),
        }
        for pick in picks
    ]

    return f"""<!DOCTYPE html>
<html lang="ko" data-snaac-ui="5">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f2f2">
<title>SNAAC 모닝 브리핑 · {html.escape(date_label)}</title>
<meta name="description" content="SNAAC이 고른 오늘의 무료 스타트업 업데이트, 인터뷰와 인사이트 {total}가지">
<meta property="og:title" content="SNAAC 모닝 브리핑 · {now.month}/{now.day}">
<meta property="og:description" content="무료로 확인할 수 있는 스타트업 업데이트와 창업가·VC 인사이트">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<style>{CSS}\n{CSS_V5}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    {_header_html(context)}
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
      <span class="free-access-note">무료 원문만</span><span>생태계 업데이트</span><span>창업가·VC 관점</span><span>제품·성장</span><span>인터뷰·영상</span>
    </div>
  </section>

  <main class="cards">{cards}</main>
  {_archive_section(slug, context)}
  {_about_snaac_section()}

  <footer>
    매일 아침 자동 업데이트 · SNAAC Community Team<br>
    원문 링크와 자체 요약만 제공하며, 모든 콘텐츠의 저작권은 각 원저작자에게 있습니다.<br>
    저장함은 로그인한 개인 계정에 동기화됩니다.
  </footer>
</div>
{_overlays_html()}
<script id="briefingData" type="application/json">{_safe_json_for_script(storage_data)}</script>
<script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config(context))}</script>
{_supabase_script()}
<script>{JS}</script>
</body>
</html>"""


def _archive_index_html(entries: list[dict]) -> str:
    tree = _archive_tree(entries)
    context = "archive"
    return f"""<!DOCTYPE html>
<html lang="ko" data-snaac-ui="5">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f2f2f2">
<title>SNAAC 지난 브리핑</title>
<meta name="description" content="SNAAC 모닝 브리핑 지난 회차 모아보기">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<style>{CSS}
{CSS_V5}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    {_header_html(context)}
  </header>
  <header class="archive-hero">
    <p class="kicker">SNAAC morning archive</p>
    <h1>지난 브리핑</h1>
    <p>월별 서랍을 열고, 주차와 날짜 순으로 지난 큐레이션을 찾아보세요.</p>
  </header>
  <main class="archive-page-list">
    {tree}
  </main>
  {_about_snaac_section()}
  <footer>
    아카이브 열람에는 별도 AI 호출이나 토큰 비용이 발생하지 않습니다.<br>
    SNAAC Community Team
  </footer>
</div>
{_overlays_html()}
<script id="briefingData" type="application/json">[]</script>
<script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config(context))}</script>
{_supabase_script()}
<script>{JS}</script>
</body>
</html>"""


def _existing_image_hints(html_path: Path) -> dict[str, str]:
    """기존 아카이브를 최신 UI로 올릴 때 이미 쓰던 OG 이미지 URL을 재사용합니다."""
    if not html_path.exists():
        return {}
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    hints: dict[str, str] = {}
    pattern = re.compile(
        r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="([^"]+)"[^>]*>.*?'
        r'<img[^>]+src="([^"]+)"',
        flags=re.I | re.S,
    )
    for match in pattern.finditer(text):
        link = html.unescape(match.group(1))
        image = html.unescape(match.group(2))
        if _public_image_url(image):
            hints[link] = image
    return hints


def _upgrade_existing_archives(current_slug: str) -> int:
    """기존 날짜별 JSON을 사용해 과거 HTML에도 최신 저장함·아카이브 UI를 적용합니다.

    기존 HTML에 있던 썸네일 URL을 재사용하고, 새 네트워크 요청은 하지 않습니다.
    """
    archive_dir = DOCS_DIR / "archive"
    upgraded = 0
    for json_path in sorted(archive_dir.glob("????-??-??.json"), reverse=True):
        slug = json_path.stem
        if slug == current_slug:
            continue
        html_path = archive_dir / f"{slug}.html"
        if not html_path.exists():
            continue
        try:
            existing_head = html_path.read_text(encoding="utf-8")[:500]
            if 'data-snaac-ui="5"' in existing_head:
                continue
            data = json.loads(json_path.read_text(encoding="utf-8"))
            raw_picks = data.get("picks", [])
            day = datetime.strptime(slug, "%Y-%m-%d").replace(tzinfo=KST)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(raw_picks, list) or not raw_picks:
            continue

        date_label = f"{day.year}년 {day.month}월 {day.day}일 {WEEKDAYS[day.weekday()]}요일"
        prepared = _prepare_picks(
            raw_picks,
            date_label,
            image_hints=_existing_image_hints(html_path),
            fetch_missing_images=False,
        )
        html_path.write_text(_page_html(prepared, day, context="archive"), encoding="utf-8")
        upgraded += 1
    return upgraded


def _write_logo_asset() -> None:
    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)
    logo_bytes = base64.b64decode(LOGO_PNG_BASE64, validate=True)
    (assets_dir / LOGO_ASSET_NAME).write_bytes(logo_bytes)


def build_page(picks: list[dict]) -> None:
    """오늘 페이지, 날짜별 아카이브, JSON, 로고와 전체 목록을 생성합니다."""
    now = datetime.now(KST)
    slug = now.strftime("%Y-%m-%d")
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"

    DOCS_DIR.mkdir(exist_ok=True)
    archive_dir = DOCS_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    _write_logo_asset()

    prepared_picks = _prepare_picks(picks, date_label)

    (DOCS_DIR / "index.html").write_text(
        _page_html(prepared_picks, now, context="home"), encoding="utf-8"
    )
    (archive_dir / f"{slug}.html").write_text(
        _page_html(prepared_picks, now, context="archive"), encoding="utf-8"
    )

    # 이미지 파일은 저장하지 않으며, 썸네일의 공개 URL 문자열만 UI 재생성을 위해 보관합니다.
    archive_data = {
        "date": slug,
        "date_label": date_label,
        "generated_at": now.isoformat(),
        "picks": prepared_picks,
    }
    (archive_dir / f"{slug}.json").write_text(
        json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    upgraded = _upgrade_existing_archives(slug)
    (archive_dir / "index.html").write_text(
        _archive_index_html(_archive_entries()), encoding="utf-8"
    )

    auth_status = "Supabase 로그인 활성" if AUTH_ENABLED else "로그인 설정 대기"
    print(
        f"[페이지 생성 완료] docs/index.html, docs/archive/{slug}.html, "
        f"docs/archive/{slug}.json, docs/archive/index.html, docs/assets/{LOGO_ASSET_NAME} "
        f"({auth_status}, 기존 아카이브 UI 갱신 {upgraded}건)"
    )
