"""모바일 브리핑 정적 웹페이지 생성 모듈.

생성 파일
- docs/index.html
- docs/archive/YYYY-MM-DD.html
- docs/archive/YYYY-MM-DD.json
- docs/archive/index.html

기능
- 원본 컬러 썸네일과 모바일 카드 UI
- 로그인 필수 저장, 선택형 메모, 저장함 상세 카드
- 이메일/비밀번호 Supabase Auth 및 기기 간 동기화
- 날짜별 지난 회차 목록
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

import settings

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
DOCS_DIR = Path("docs")
SHOW_THUMBNAILS = True

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = (
    os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    or os.environ.get("SUPABASE_ANON_KEY", "")
).strip()
AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()
ABOUT_URL = os.environ.get("ABOUT_URL", "").strip() or (
    f"https://github.com/{GITHUB_REPOSITORY}" if GITHUB_REPOSITORY else ""
)

FALLBACK_GRADIENTS = [
    ("#1D4E89", "#7DB7E8"),
    ("#176B5B", "#75B8A9"),
    ("#6D4C7D", "#B89BC5"),
    ("#7B4B3A", "#D6A38E"),
    ("#3D5A6C", "#8AA7B7"),
    ("#5C5F72", "#A6A9B8"),
]

CSS = r"""
:root {
  --bg:#f2f3f4;
  --paper:#fff;
  --ink:#151515;
  --muted:#686868;
  --soft:#8b8b8b;
  --line:#d9dadd;
  --line-dark:#b9bbc0;
  --accent:__ACCENT__;
  --shadow:0 14px 34px rgba(18,18,18,.08);
  --radius:18px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}
button,input,textarea{font:inherit}
button,a{-webkit-tap-highlight-color:transparent}
button{color:inherit}
a{color:inherit}
body.modal-open{overflow:hidden}
.wrap{width:min(100%,620px);margin:0 auto;padding:0 18px calc(100px + env(safe-area-inset-bottom))}
.masthead{padding:18px 0 12px;border-bottom:2px solid var(--ink)}
.topbar{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:10px;min-height:58px}
.topbar-side{display:flex;align-items:center;gap:7px;min-width:0}
.topbar-side.right{justify-content:flex-end}
.nav-btn{appearance:none;border:1px solid var(--line-dark);background:rgba(255,255,255,.72);border-radius:999px;min-height:38px;padding:8px 11px;text-decoration:none;font-size:12px;font-weight:750;display:inline-flex;align-items:center;justify-content:center;gap:5px;white-space:nowrap;cursor:pointer}
.nav-btn:active{transform:scale(.98)}
.saved-nav{background:var(--ink);color:#fff;border-color:var(--ink)}
.saved-count{min-width:19px;height:19px;border-radius:999px;background:#fff;color:var(--ink);display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;padding:0 5px}
.brand{display:flex;flex-direction:column;align-items:center;justify-content:center;text-decoration:none;line-height:1;text-align:center;min-width:116px}
.brand-top{font-size:16px;font-weight:900;letter-spacing:.13em}
.brand-bottom{margin-top:6px;font-size:8px;font-weight:800;letter-spacing:.23em;color:var(--muted)}
.date-lockup{position:relative;padding:22px 0 8px}
.kicker{margin:0 0 5px;font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}
.date-big{margin:0;font-size:clamp(58px,17vw,86px);font-weight:900;line-height:.95;letter-spacing:-.065em}
.date-sub{margin-top:9px;font-size:13px;color:var(--muted);font-weight:600}
.stamp{position:absolute;right:2px;top:22px;width:76px;height:76px;border:2px solid var(--ink);border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(7deg);font-size:9px;font-weight:800;letter-spacing:.12em;background:rgba(242,243,244,.78)}
.stamp strong{font-size:16px;letter-spacing:.02em;line-height:1.1}
.intro{padding:19px 0 20px}
.intro>p{margin:0;font-size:14px;color:#4d4d4d;word-break:keep-all}
.editorial-rule{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}
.editorial-rule span{font-size:11px;font-weight:700;border:1px solid var(--line);background:rgba(255,255,255,.64);border-radius:999px;padding:5px 9px;color:#5f5f5f}
.editorial-rule span:first-child{border-color:var(--ink);color:var(--ink)}
.section-divider{display:flex;align-items:center;gap:10px;margin:28px 0 13px}
.section-divider::after{content:"";height:1px;flex:1;background:var(--line-dark)}
.section-divider h2{margin:0;font-size:13px;letter-spacing:.08em;text-transform:uppercase}
.card{background:var(--paper);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin-bottom:17px;box-shadow:0 1px 0 rgba(0,0,0,.02)}
.thumb{position:relative;display:block;aspect-ratio:16/8.6;background:linear-gradient(135deg,var(--fa),var(--fb));overflow:hidden;text-decoration:none}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb.no-image::after{content:attr(data-initial);position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.92);font-size:48px;font-weight:900;letter-spacing:-.05em}
.video-mark{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:52px;height:52px;border-radius:50%;background:rgba(0,0,0,.74);display:flex;align-items:center;justify-content:center;color:#fff;box-shadow:0 8px 22px rgba(0,0,0,.2)}
.video-mark::after{content:"";margin-left:4px;border-left:14px solid currentColor;border-top:9px solid transparent;border-bottom:9px solid transparent}
.card-body{padding:17px 18px 18px}
.meta{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
.meta-left{display:flex;align-items:center;gap:6px;min-width:0;flex-wrap:wrap}
.tag{display:inline-flex;align-items:center;min-height:24px;border:1px solid #d5d6d9;background:#f6f6f7;border-radius:999px;padding:3px 8px;font-size:10.5px;font-weight:800;color:#555}
.tag.section{background:#202020;border-color:#202020;color:#fff}
.idx{font-size:11px;color:var(--soft);font-weight:750;white-space:nowrap}
.card h2{margin:0 0 9px;font-size:19px;line-height:1.38;letter-spacing:-.025em;word-break:keep-all}
.summary{margin:0;color:#5e5e5e;font-size:14px;word-break:keep-all}
.takeaway{margin:14px 0 0;padding:12px 13px;border-left:3px solid var(--ink);background:#f5f5f5;font-size:13px;color:#454545;word-break:keep-all}
.takeaway strong{display:block;margin-bottom:3px;font-size:10px;letter-spacing:.12em;color:#777}
.card-actions{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:15px}
.open-link,.save-btn{min-height:43px;border-radius:12px;display:flex;align-items:center;justify-content:center;gap:7px;font-size:13px;font-weight:800;text-decoration:none;cursor:pointer}
.open-link{background:var(--ink);color:#fff;border:1px solid var(--ink)}
.save-btn{border:1px solid var(--line-dark);background:#fff;padding:0 13px}
.save-btn.saved{background:#ececed;border-color:#999}
.save-btn svg,.nav-btn svg{width:16px;height:16px;flex:none}
.archive-section{margin-top:34px;padding-top:24px;border-top:1px solid var(--line-dark)}
.archive-heading{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:13px}
.archive-heading h2{margin:0;font-size:16px}
.archive-heading a{font-size:12px;color:var(--muted);font-weight:700}
.archive-chips{display:flex;gap:8px;overflow-x:auto;padding:2px 0 6px;scrollbar-width:none}
.archive-chips::-webkit-scrollbar{display:none}
.archive-chips a{flex:none;border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 12px;text-decoration:none;font-size:12px;font-weight:700}
.about-section{margin-top:20px}
.about-card{display:block;position:relative;overflow:hidden;background:#1c1c1c;color:#fff;border-radius:18px;padding:20px 72px 20px 19px;text-decoration:none;min-height:128px}
.about-card::after{content:"↗";position:absolute;right:18px;top:17px;font-size:25px}
.about-eyebrow{display:block;font-size:9px;font-weight:850;letter-spacing:.18em;color:#bdbdbd}
.about-title{display:block;margin-top:11px;font-size:20px;font-weight:850;letter-spacing:-.02em}
.about-copy{display:block;margin-top:7px;font-size:12.5px;color:#d0d0d0;word-break:keep-all}
footer{margin:34px 0 0;text-align:center;color:#858585;font-size:11px;line-height:1.8}
.mobile-saved{position:fixed;z-index:30;left:50%;bottom:calc(12px + env(safe-area-inset-bottom));transform:translateX(-50%);width:min(calc(100% - 36px),584px);height:50px;border:0;border-radius:15px;background:#161616;color:#fff;box-shadow:0 12px 32px rgba(0,0,0,.23);font-weight:850;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer}
.mobile-saved .saved-count{background:#fff}
.archive-hero{padding:28px 0 18px;border-bottom:1px solid var(--line-dark)}
.archive-hero h1{font-size:38px;line-height:1.05;letter-spacing:-.04em;margin:4px 0 9px}
.archive-hero p:last-child{margin:0;color:var(--muted);font-size:13px}
.archive-list{margin-top:18px;border-top:1px solid var(--line-dark)}
.archive-row{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:10px;min-height:72px;padding:13px 2px;border-bottom:1px solid var(--line);text-decoration:none}
.archive-date{font-size:15px;font-weight:800}
.archive-count{font-size:11px;color:var(--muted)}
.archive-arrow{font-size:18px}
.empty{padding:34px 0;color:var(--muted);text-align:center;font-size:13px}
.overlay{position:fixed;z-index:90;inset:0;display:none;background:rgba(0,0,0,.45);backdrop-filter:blur(2px);padding:16px;align-items:flex-end;justify-content:center}
.overlay.open{display:flex}
.panel{width:min(100%,600px);max-height:min(88vh,820px);overflow:auto;background:#fff;border-radius:22px 22px 16px 16px;box-shadow:0 24px 70px rgba(0,0,0,.28)}
.panel-header{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 17px;background:rgba(255,255,255,.96);border-bottom:1px solid var(--line)}
.panel-header h2{margin:0;font-size:18px}
.close-btn{width:36px;height:36px;border:1px solid var(--line);background:#f5f5f5;border-radius:50%;font-size:20px;cursor:pointer}
.panel-body{padding:17px}
.saved-empty{padding:38px 8px;text-align:center;color:var(--muted);font-size:13px}
.saved-list{display:grid;gap:10px}
.saved-item{width:100%;display:grid;grid-template-columns:88px 1fr;gap:12px;text-align:left;border:1px solid var(--line);background:#fff;border-radius:14px;padding:0;overflow:hidden;cursor:pointer}
.saved-item-thumb{min-height:94px;background:linear-gradient(135deg,var(--fa),var(--fb));overflow:hidden}
.saved-item-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.saved-item-body{padding:11px 11px 11px 0;min-width:0}
.saved-item-source{font-size:10px;color:var(--muted);font-weight:800}
.saved-item-title{display:block;margin-top:4px;font-size:13px;line-height:1.35;font-weight:850;word-break:keep-all}
.saved-item-note{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-top:6px;font-size:11px;color:#777}
.form-label{display:block;font-size:12px;font-weight:800;margin:0 0 7px}
.note-textarea,.auth-input{width:100%;border:1px solid var(--line-dark);border-radius:12px;background:#fff;padding:12px 13px;outline:none}
.note-textarea{min-height:140px;resize:vertical}
.note-textarea:focus,.auth-input:focus{border-color:#444;box-shadow:0 0 0 3px rgba(0,0,0,.06)}
.form-help{margin:7px 0 0;font-size:11px;color:var(--muted)}
.form-actions{display:grid;grid-template-columns:1fr 1.3fr;gap:8px;margin-top:15px}
.secondary-btn,.primary-btn,.danger-btn{min-height:45px;border-radius:12px;font-weight:850;cursor:pointer}
.secondary-btn{border:1px solid var(--line-dark);background:#fff}
.primary-btn{border:1px solid var(--ink);background:var(--ink);color:#fff}
.danger-btn{border:1px solid #c8c8c8;background:#f4f4f4;color:#444}
.auth-tabs{display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--line);border-radius:12px;padding:3px;margin-bottom:16px}
.auth-tab{border:0;background:transparent;border-radius:9px;min-height:38px;font-size:12px;font-weight:800;cursor:pointer}
.auth-tab.active{background:#1c1c1c;color:#fff}
.auth-label{display:block;margin:12px 0 6px;font-size:12px;font-weight:800}
.auth-submit{width:100%;min-height:46px;margin-top:15px;border:0;border-radius:12px;background:#171717;color:#fff;font-weight:850;cursor:pointer}
.auth-message{min-height:20px;margin:9px 0 0;font-size:12px;color:#555}
.auth-help{margin:4px 0 0;font-size:11px;color:#888}
.account-card{padding:17px;border:1px solid var(--line);border-radius:14px;background:#f7f7f7}
.account-eyebrow{margin:0;font-size:9px;letter-spacing:.15em;color:#777;font-weight:800}
.account-email{margin:8px 0 0;font-size:16px;font-weight:850;word-break:break-all}
.account-copy{margin:7px 0 0;font-size:12px;color:#666}
.account-logout{width:100%;min-height:44px;margin-top:12px;border:1px solid var(--line-dark);background:#fff;border-radius:12px;font-weight:800;cursor:pointer}
.setup-note{padding:18px;border:1px solid var(--line);border-radius:14px;background:#f6f6f6}
.setup-note h3{margin:0 0 6px;font-size:16px}
.setup-note p{margin:0;color:#666;font-size:12px}
.preview-thumb{aspect-ratio:16/8.6;background:linear-gradient(135deg,var(--fa),var(--fb));overflow:hidden}
.preview-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.preview-content{padding:17px}
.preview-tags{display:flex;gap:6px;flex-wrap:wrap}
.preview-content h3{font-size:21px;line-height:1.37;letter-spacing:-.025em;margin:12px 0 9px;word-break:keep-all}
.preview-summary{margin:0;color:#5d5d5d;font-size:14px}
.preview-note{margin-top:13px;padding:12px;border-radius:12px;background:#f3f3f3;font-size:13px;white-space:pre-wrap;word-break:break-word}
.preview-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:16px}
.preview-actions .open-link{grid-column:1/-1}
.status{position:fixed;z-index:120;left:50%;bottom:calc(76px + env(safe-area-inset-bottom));transform:translate(-50%,16px);max-width:calc(100% - 36px);background:#111;color:#fff;border-radius:999px;padding:10px 14px;font-size:12px;opacity:0;pointer-events:none;transition:.2s}
.status.show{opacity:1;transform:translate(-50%,0)}
.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
[hidden]{display:none!important}
@media(min-width:700px){
  .mobile-saved{display:none}
  .wrap{padding-bottom:70px}
  .overlay{align-items:center}
  .panel{border-radius:22px}
}
@media(max-width:410px){
  .wrap{padding-left:14px;padding-right:14px}
  .topbar{gap:5px}
  .nav-btn{padding:7px 8px;font-size:10.5px}
  .brand{min-width:102px}
  .brand-top{font-size:14px}
  .brand-bottom{font-size:7px}
  .stamp{width:67px;height:67px;font-size:8px}
  .stamp strong{font-size:14px}
  .card h2{font-size:18px}
}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""

JS = r"""
(() => {
  'use strict';
  const briefingDataEl = document.getElementById('briefingData');
  const authConfigEl = document.getElementById('authConfig');
  const siteConfigEl = document.getElementById('siteConfig');
  const articles = briefingDataEl ? JSON.parse(briefingDataEl.textContent || '[]') : [];
  const authConfig = authConfigEl ? JSON.parse(authConfigEl.textContent || '{}') : {};
  const siteConfig = siteConfigEl ? JSON.parse(siteConfigEl.textContent || '{}') : {};
  const articleMap = new Map(articles.map((item) => [item.link, item]));
  const authEnabled = Boolean(authConfig.url && authConfig.publishableKey);

  let supabaseClient = null;
  let currentUser = null;
  let savedMap = new Map();
  let pendingArticle = null;
  let activePreview = null;
  let authMode = 'signin';
  let statusTimer = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const overlays = {
    saved: $('#savedOverlay'),
    note: $('#noteOverlay'),
    auth: $('#authOverlay'),
    preview: $('#previewOverlay'),
  };

  function showStatus(message) {
    const node = $('#statusToast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => node.classList.remove('show'), 2400);
  }

  function openOverlay(name) {
    const node = overlays[name];
    if (!node) return;
    node.classList.add('open');
    node.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }

  function closeOverlay(name) {
    const node = overlays[name];
    if (!node) return;
    node.classList.remove('open');
    node.setAttribute('aria-hidden', 'true');
    if (!Object.values(overlays).some((overlay) => overlay && overlay.classList.contains('open'))) {
      document.body.classList.remove('modal-open');
    }
  }

  function closeAll() {
    Object.keys(overlays).forEach(closeOverlay);
  }

  function savedCount() {
    return savedMap.size;
  }

  function updateCounts() {
    $$('[data-saved-count]').forEach((node) => { node.textContent = String(savedCount()); });
  }

  function isSaved(link) {
    return savedMap.has(link);
  }

  function updateSaveButtons() {
    $$('[data-save-link]').forEach((button) => {
      const link = button.dataset.saveLink || '';
      const saved = isSaved(link);
      button.classList.toggle('saved', saved);
      const label = button.querySelector('[data-save-label]');
      if (label) label.textContent = saved ? (savedMap.get(link)?.note ? '메모 보기' : '저장됨') : '저장';
      button.setAttribute('aria-pressed', saved ? 'true' : 'false');
    });
    updateCounts();
  }

  function normalizeRecord(record) {
    return {
      link: record.article_url || record.link || '',
      title: record.title || '',
      source: record.source || '',
      summary: record.summary || '',
      takeaway: record.takeaway || '',
      section: record.section || '',
      category: record.category || '',
      contentType: record.content_type || record.contentType || '기사',
      image: record.image_url || record.image || '',
      briefingDate: record.briefing_date || record.briefingDate || '',
      note: record.note || '',
      fallbackA: record.fallback_a || record.fallbackA || '#3D5A6C',
      fallbackB: record.fallback_b || record.fallbackB || '#8AA7B7',
      savedAt: record.saved_at || '',
    };
  }

  async function loadSaved() {
    if (!supabaseClient || !currentUser) {
      savedMap = new Map();
      updateSaveButtons();
      renderSavedList();
      return;
    }
    const { data, error } = await supabaseClient
      .from(siteConfig.table)
      .select('*')
      .order('saved_at', { ascending: false });
    if (error) {
      console.error('saved article fetch failed', error);
      showStatus('저장함을 불러오지 못했어요.');
      return;
    }
    savedMap = new Map((data || []).map((row) => {
      const item = normalizeRecord(row);
      return [item.link, item];
    }));
    updateSaveButtons();
    renderSavedList();
  }

  function getArticle(link) {
    return savedMap.get(link) || articleMap.get(link) || null;
  }

  function requireAuth(action, article = null) {
    if (!authEnabled) {
      renderAuthState();
      openOverlay('auth');
      return false;
    }
    if (!currentUser) {
      pendingArticle = action === 'save' ? article : null;
      setAuthMode('signin');
      renderAuthState();
      openOverlay('auth');
      return false;
    }
    return true;
  }

  function openNote(article) {
    if (!article) return;
    pendingArticle = article;
    const existing = savedMap.get(article.link);
    $('#noteTitle').textContent = existing ? '스크랩 메모 수정' : '기사 저장';
    $('#noteArticleTitle').textContent = article.title || '';
    $('#noteText').value = existing?.note || '';
    openOverlay('note');
    setTimeout(() => $('#noteText')?.focus(), 80);
  }

  async function savePendingArticle() {
    if (!pendingArticle || !supabaseClient || !currentUser) return;
    const article = pendingArticle;
    const note = ($('#noteText')?.value || '').trim().slice(0, 500);
    const payload = {
      user_id: currentUser.id,
      article_url: article.link,
      title: article.title,
      source: article.source || '',
      summary: article.summary || '',
      takeaway: article.takeaway || '',
      section: article.section || '',
      category: article.category || '',
      content_type: article.contentType || '기사',
      image_url: article.image || '',
      briefing_date: article.briefingDate || '',
      note,
      fallback_a: article.fallbackA || '#3D5A6C',
      fallback_b: article.fallbackB || '#8AA7B7',
      updated_at: new Date().toISOString(),
    };
    const { error } = await supabaseClient
      .from(siteConfig.table)
      .upsert(payload, { onConflict: 'user_id,article_url' });
    if (error) {
      console.error('saved article upsert failed', error);
      showStatus('저장하지 못했어요. 잠시 후 다시 시도해 주세요.');
      return;
    }
    closeOverlay('note');
    pendingArticle = null;
    await loadSaved();
    showStatus(note ? '기사와 메모를 저장했어요.' : '기사를 저장했어요.');
  }

  async function removeSaved(link) {
    if (!supabaseClient || !currentUser || !link) return;
    const { error } = await supabaseClient
      .from(siteConfig.table)
      .delete()
      .eq('user_id', currentUser.id)
      .eq('article_url', link);
    if (error) {
      console.error('saved article delete failed', error);
      showStatus('삭제하지 못했어요.');
      return;
    }
    closeOverlay('preview');
    await loadSaved();
    showStatus('저장함에서 삭제했어요.');
  }

  function renderSavedList() {
    const list = $('#savedList');
    const empty = $('#savedEmpty');
    if (!list || !empty) return;
    list.textContent = '';
    const items = Array.from(savedMap.values());
    empty.hidden = items.length > 0;
    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'saved-item';
      button.addEventListener('click', () => openPreview(item));

      const thumb = document.createElement('span');
      thumb.className = 'saved-item-thumb';
      thumb.style.setProperty('--fa', item.fallbackA || '#3D5A6C');
      thumb.style.setProperty('--fb', item.fallbackB || '#8AA7B7');
      if (item.image) {
        const img = document.createElement('img');
        img.src = item.image;
        img.alt = '';
        img.loading = 'lazy';
        img.onerror = () => img.remove();
        thumb.appendChild(img);
      }

      const body = document.createElement('span');
      body.className = 'saved-item-body';
      const source = document.createElement('span');
      source.className = 'saved-item-source';
      source.textContent = [item.section, item.source].filter(Boolean).join(' · ');
      const title = document.createElement('span');
      title.className = 'saved-item-title';
      title.textContent = item.title;
      body.append(source, title);
      if (item.note) {
        const note = document.createElement('span');
        note.className = 'saved-item-note';
        note.textContent = item.note;
        body.appendChild(note);
      }
      button.append(thumb, body);
      list.appendChild(button);
    });
  }

  function openSavedDrawer() {
    if (!requireAuth('drawer')) return;
    renderSavedList();
    openOverlay('saved');
  }

  function openPreview(item) {
    if (!item) return;
    activePreview = item;
    const thumb = $('#previewThumb');
    thumb.textContent = '';
    thumb.style.setProperty('--fa', item.fallbackA || '#3D5A6C');
    thumb.style.setProperty('--fb', item.fallbackB || '#8AA7B7');
    if (item.image) {
      const img = document.createElement('img');
      img.src = item.image;
      img.alt = '';
      img.onerror = () => img.remove();
      thumb.appendChild(img);
    }
    $('#previewSection').textContent = item.section || '';
    $('#previewSource').textContent = item.source || '';
    $('#previewCategory').textContent = item.category || '';
    $('#previewTitle').textContent = item.title || '';
    $('#previewSummary').textContent = item.summary || '';
    $('#previewTakeaway').textContent = item.takeaway || '';
    const note = $('#previewNote');
    note.textContent = item.note ? `저장 메모\n${item.note}` : '저장 메모가 없습니다.';
    const link = $('#previewOriginal');
    link.href = item.link || '#';
    closeOverlay('saved');
    openOverlay('preview');
  }

  function setAuthMode(mode) {
    authMode = mode;
    $$('.auth-tab').forEach((tab) => {
      const active = tab.dataset.authMode === mode;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    $('#authSubmit').textContent = mode === 'signup' ? '회원가입' : '로그인';
    $('#authPassword').autocomplete = mode === 'signup' ? 'new-password' : 'current-password';
    $('#authMessage').textContent = '';
  }

  function renderAuthState() {
    const signedOut = $('#authSignedOut');
    const signedIn = $('#authSignedIn');
    const setup = $('#authSetup');
    if (!authEnabled) {
      signedOut.hidden = true;
      signedIn.hidden = true;
      setup.hidden = false;
    } else if (currentUser) {
      signedOut.hidden = true;
      setup.hidden = true;
      signedIn.hidden = false;
      $('#accountEmail').textContent = currentUser.email || '로그인 계정';
    } else {
      setup.hidden = true;
      signedIn.hidden = true;
      signedOut.hidden = false;
    }
    $$('[data-account-label]').forEach((node) => {
      node.textContent = currentUser ? '계정' : '로그인';
    });
  }

  async function submitAuth(event) {
    event.preventDefault();
    if (!supabaseClient) return;
    const email = ($('#authEmail').value || '').trim();
    const password = $('#authPassword').value || '';
    const message = $('#authMessage');
    message.textContent = authMode === 'signup' ? '계정을 만들고 있어요…' : '로그인하고 있어요…';

    try {
      if (authMode === 'signup') {
        const { data, error } = await supabaseClient.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.href.split('#')[0] },
        });
        if (error) throw error;
        if (!data.session) {
          message.textContent = '가입 확인 메일을 보냈어요. 이메일 인증 후 로그인해 주세요.';
          return;
        }
      } else {
        const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      message.textContent = '';
      closeOverlay('auth');
    } catch (error) {
      console.error('auth error', error);
      message.textContent = error?.message || '로그인 처리 중 오류가 발생했어요.';
    }
  }

  async function signOut() {
    if (!supabaseClient) return;
    await supabaseClient.auth.signOut();
    closeOverlay('auth');
    showStatus('로그아웃했어요.');
  }

  async function applySession(session) {
    currentUser = session?.user || null;
    renderAuthState();
    await loadSaved();
    if (currentUser && pendingArticle) {
      const article = pendingArticle;
      setTimeout(() => openNote(article), 100);
    }
  }

  async function initAuth() {
    renderAuthState();
    if (!authEnabled || !window.supabase) return;
    supabaseClient = window.supabase.createClient(authConfig.url, authConfig.publishableKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
    const { data } = await supabaseClient.auth.getSession();
    await applySession(data?.session || null);
    supabaseClient.auth.onAuthStateChange((_event, session) => {
      setTimeout(() => applySession(session), 0);
    });
  }

  $$('[data-save-link]').forEach((button) => {
    button.addEventListener('click', () => {
      const article = getArticle(button.dataset.saveLink || '');
      if (!article) return;
      if (!requireAuth('save', article)) return;
      openNote(article);
    });
  });
  $$('[data-open-saved]').forEach((button) => button.addEventListener('click', openSavedDrawer));
  $$('[data-open-auth]').forEach((button) => button.addEventListener('click', () => {
    renderAuthState();
    openOverlay('auth');
  }));
  $$('[data-close-overlay]').forEach((button) => button.addEventListener('click', () => closeOverlay(button.dataset.closeOverlay)));
  $$('.overlay').forEach((overlay) => overlay.addEventListener('click', (event) => {
    if (event.target === overlay) closeOverlay(overlay.dataset.overlay);
  }));
  $$('.auth-tab').forEach((tab) => tab.addEventListener('click', () => setAuthMode(tab.dataset.authMode || 'signin')));
  $('#authForm')?.addEventListener('submit', submitAuth);
  $('#logoutButton')?.addEventListener('click', signOut);
  $('#noteSave')?.addEventListener('click', savePendingArticle);
  $('#noteCancel')?.addEventListener('click', () => { pendingArticle = null; closeOverlay('note'); });
  $('#previewEdit')?.addEventListener('click', () => { closeOverlay('preview'); openNote(activePreview); });
  $('#previewDelete')?.addEventListener('click', () => removeSaved(activePreview?.link || ''));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAll();
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && overlays.note?.classList.contains('open')) {
      savePendingArticle();
    }
  });

  setAuthMode('signin');
  updateSaveButtons();
  initAuth();
})();
"""


def _safe_json_for_script(data: object) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("</", "<\\/")
    )


def _public_image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith(("https://", "http://")):
        return value
    return None


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


def _youtube_thumbnail(url: str) -> str | None:
    video_id = _youtube_video_id(url)
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


def fetch_og_image(url: str) -> str | None:
    youtube = _youtube_thumbnail(url)
    if youtube:
        return youtube
    try:
        response = requests.get(
            url,
            timeout=12,
            allow_redirects=True,
            headers={
                "User-Agent": f"Mozilla/5.0 (compatible; {settings.DOMAIN_ID.title()}BriefingBot/1.0)",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            },
        )
        if response.status_code >= 400:
            return None
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, response.text[:700_000], flags=re.I)
            if match:
                image = html.unescape(match.group(1).strip())
                image = urljoin(response.url, image)
                return _public_image_url(image)
    except requests.RequestException as exc:
        print(f"[썸네일 스킵] {url}: {exc}")
    return None


def _source_gradient(source: str) -> tuple[str, str]:
    score = sum((index + 1) * ord(char) for index, char in enumerate(source or settings.SITE_NAME))
    return FALLBACK_GRADIENTS[score % len(FALLBACK_GRADIENTS)]


def _prepare_picks(picks: list[dict], date_label: str, *, fetch_missing_images: bool = True) -> list[dict]:
    prepared: list[dict] = []
    for pick in picks:
        source = str(pick.get("source", "기타")).strip() or "기타"
        link = str(pick.get("link", "")).strip()
        image = _public_image_url(pick.get("image")) or _public_image_url(pick.get("thumbnail"))
        if not image and SHOW_THUMBNAILS and fetch_missing_images:
            image = fetch_og_image(link)
        fallback_a = str(pick.get("fallback_a") or "")
        fallback_b = str(pick.get("fallback_b") or "")
        if not fallback_a or not fallback_b:
            fallback_a, fallback_b = _source_gradient(source)
        prepared.append(
            {
                "title": str(pick.get("title", "")).strip(),
                "link": link,
                "source": source,
                "summary": str(pick.get("summary", "")).strip(),
                "takeaway": str(pick.get("takeaway", "")).strip(),
                "section": str(pick.get("section", "")).strip(),
                "category": str(pick.get("category", "")).strip(),
                "content_type": str(pick.get("content_type", "기사")).strip() or "기사",
                "published": str(pick.get("published", "unknown")).strip(),
                "image": image or "",
                "fallback_a": fallback_a,
                "fallback_b": fallback_b,
                "briefing_date": date_label,
            }
        )
    return prepared


def _bookmark_icon() -> str:
    return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.5 4.75A1.75 1.75 0 0 1 8.25 3h7.5a1.75 1.75 0 0 1 1.75 1.75V21l-5.5-3.45L6.5 21V4.75Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>'


def _card(index: int, total: int, pick: dict) -> str:
    title = html.escape(pick["title"])
    link = html.escape(pick["link"], quote=True)
    source = html.escape(pick["source"])
    section = html.escape(pick["section"])
    category = html.escape(pick["category"])
    summary = html.escape(pick["summary"])
    takeaway = html.escape(pick["takeaway"])
    image = html.escape(pick.get("image", ""), quote=True)
    fa = html.escape(pick["fallback_a"], quote=True)
    fb = html.escape(pick["fallback_b"], quote=True)
    initial = html.escape((pick["source"] or settings.BRAND_TOP)[0])
    video = pick.get("content_type") == "영상" or _youtube_video_id(pick["link"]) is not None

    if image:
        thumb_inner = f'<img src="{image}" alt="" loading="lazy" onerror="this.remove();this.parentElement.classList.add(\'no-image\')">'
    else:
        thumb_inner = ""
    if video:
        thumb_inner += '<span class="video-mark" aria-hidden="true"></span>'

    return f"""
<article class="card">
  <a class="thumb{' no-image' if not image else ''}" href="{link}" target="_blank" rel="noopener noreferrer" style="--fa:{fa};--fb:{fb}" data-initial="{initial}">
    {thumb_inner}
  </a>
  <div class="card-body">
    <div class="meta">
      <div class="meta-left"><span class="tag section">{section}</span><span class="tag">{category}</span><span class="tag">{source}</span></div>
      <span class="idx">{index}/{total}</span>
    </div>
    <h2>{title}</h2>
    <p class="summary">{summary}</p>
    <p class="takeaway"><strong>WHY IT MATTERS</strong>{takeaway}</p>
    <div class="card-actions">
      <a class="open-link" href="{link}" target="_blank" rel="noopener noreferrer">원문 읽기 <span aria-hidden="true">↗</span></a>
      <button class="save-btn" type="button" data-save-link="{link}" aria-pressed="false">{_bookmark_icon()}<span data-save-label>저장</span></button>
    </div>
  </div>
</article>"""


def _header_html(context: str) -> str:
    home_href = "./" if context == "home" else "../"
    archive_href = "archive/index.html" if context == "home" else ("./" if context == "archive-index" else "index.html")
    return f"""
<div class="topbar">
  <div class="topbar-side"><a class="nav-btn" href="{archive_href}">지난 회차</a></div>
  <a class="brand" href="{home_href}" aria-label="{html.escape(settings.SITE_KOREAN_NAME)} 홈">
    <span class="brand-top">{html.escape(settings.BRAND_TOP)}</span>
    <span class="brand-bottom">{html.escape(settings.BRAND_BOTTOM)}</span>
  </a>
  <div class="topbar-side right">
    <button class="nav-btn saved-nav" type="button" data-open-saved>저장함 <span class="saved-count" data-saved-count>0</span></button>
    <button class="nav-btn" type="button" data-open-auth><span data-account-label>로그인</span></button>
  </div>
</div>"""


def _archive_entries(exclude_slug: str | None = None) -> list[dict]:
    archive_dir = DOCS_DIR / "archive"
    entries: list[dict] = []
    for path in archive_dir.glob("????-??-??.json"):
        if path.stem == exclude_slug:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            day = datetime.strptime(path.stem, "%Y-%m-%d")
            picks = data.get("picks", [])
            entries.append(
                {
                    "slug": path.stem,
                    "full_label": data.get("date_label") or f"{day.year}년 {day.month}월 {day.day}일",
                    "short_label": f"{day.month}/{day.day}",
                    "count": len(picks) if isinstance(picks, list) else 0,
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(entries, key=lambda item: item["slug"], reverse=True)


def _archive_section(today_slug: str, context: str) -> str:
    entries = _archive_entries(exclude_slug=today_slug)[:14]
    if not entries:
        return ""
    prefix = "archive/" if context == "home" else ""
    chips = "".join(
        f'<a href="{prefix}{entry["slug"]}.html">{html.escape(entry["short_label"])}</a>'
        for entry in entries
    )
    index_href = "archive/index.html" if context == "home" else "index.html"
    return f"""
<section class="archive-section">
  <div class="archive-heading"><h2>지난 브리핑</h2><a href="{index_href}">전체 보기 →</a></div>
  <div class="archive-chips">{chips}</div>
</section>"""


def _about_section() -> str:
    tag = "a" if ABOUT_URL else "div"
    href = f' href="{html.escape(ABOUT_URL, quote=True)}" target="_blank" rel="noopener noreferrer"' if ABOUT_URL else ""
    return f"""
<section class="about-section">
  <{tag} class="about-card"{href}>
    <span class="about-eyebrow">{html.escape(settings.ABOUT_EYEBROW)}</span>
    <span class="about-title">{html.escape(settings.ABOUT_TITLE)}</span>
    <span class="about-copy">{html.escape(settings.ABOUT_COPY)}</span>
  </{tag}>
</section>"""


def _overlays_html() -> str:
    return """
<button class="mobile-saved" type="button" data-open-saved>내 저장함 <span class="saved-count" data-saved-count>0</span></button>

<div class="overlay" id="savedOverlay" data-overlay="saved" aria-hidden="true">
  <section class="panel" role="dialog" aria-modal="true" aria-labelledby="savedTitle">
    <header class="panel-header"><h2 id="savedTitle">내 저장함</h2><button class="close-btn" type="button" data-close-overlay="saved" aria-label="닫기">×</button></header>
    <div class="panel-body"><p class="saved-empty" id="savedEmpty">저장한 아티클이 아직 없어요.</p><div class="saved-list" id="savedList"></div></div>
  </section>
</div>

<div class="overlay" id="noteOverlay" data-overlay="note" aria-hidden="true">
  <section class="panel" role="dialog" aria-modal="true" aria-labelledby="noteTitle">
    <header class="panel-header"><h2 id="noteTitle">기사 저장</h2><button class="close-btn" type="button" data-close-overlay="note" aria-label="닫기">×</button></header>
    <div class="panel-body">
      <p id="noteArticleTitle" style="margin:0 0 15px;font-weight:850;word-break:keep-all"></p>
      <label class="form-label" for="noteText">이 기사를 저장한 이유 <span style="font-weight:500;color:#888">(선택)</span></label>
      <textarea class="note-textarea" id="noteText" maxlength="500" placeholder="나중에 다시 봤을 때 기억하고 싶은 생각을 적어두세요."></textarea>
      <p class="form-help">메모 없이 기사만 저장해도 됩니다. Ctrl/Cmd + Enter로 저장할 수 있어요.</p>
      <div class="form-actions"><button class="secondary-btn" id="noteCancel" type="button">취소</button><button class="primary-btn" id="noteSave" type="button">저장하기</button></div>
    </div>
  </section>
</div>

<div class="overlay" id="authOverlay" data-overlay="auth" aria-hidden="true">
  <section class="panel" role="dialog" aria-modal="true" aria-labelledby="authTitle">
    <header class="panel-header"><h2 id="authTitle">브리핑 계정</h2><button class="close-btn" type="button" data-close-overlay="auth" aria-label="닫기">×</button></header>
    <div class="panel-body">
      <div id="authSignedOut">
        <div class="auth-tabs" role="tablist"><button class="auth-tab active" type="button" data-auth-mode="signin">로그인</button><button class="auth-tab" type="button" data-auth-mode="signup">회원가입</button></div>
        <form id="authForm">
          <label class="auth-label" for="authEmail">이메일</label><input class="auth-input" id="authEmail" type="email" inputmode="email" autocomplete="email" required placeholder="name@example.com">
          <label class="auth-label" for="authPassword">비밀번호</label><input class="auth-input" id="authPassword" type="password" minlength="8" autocomplete="current-password" required placeholder="8자 이상">
          <button class="auth-submit" id="authSubmit" type="submit">로그인</button>
          <p class="auth-message" id="authMessage" aria-live="polite"></p>
          <p class="auth-help">로그인하면 저장한 기사와 메모를 다른 기기에서도 이어볼 수 있어요.</p>
        </form>
      </div>
      <div id="authSignedIn" hidden><div class="account-card"><p class="account-eyebrow">SIGNED IN AS</p><p class="account-email" id="accountEmail"></p><p class="account-copy">이 계정의 저장함과 메모를 동기화하고 있어요.</p></div><button class="account-logout" id="logoutButton" type="button">로그아웃</button></div>
      <div id="authSetup" hidden><div class="setup-note"><h3>로그인 연결 전이에요</h3><p>기사 저장과 저장함을 사용하려면 Supabase 공개 설정을 GitHub Secret에 연결해야 합니다.</p></div></div>
    </div>
  </section>
</div>

<div class="overlay" id="previewOverlay" data-overlay="preview" aria-hidden="true">
  <section class="panel" role="dialog" aria-modal="true" aria-labelledby="previewTitle">
    <header class="panel-header"><h2>저장한 아티클</h2><button class="close-btn" type="button" data-close-overlay="preview" aria-label="닫기">×</button></header>
    <div class="preview-thumb" id="previewThumb"></div>
    <div class="preview-content">
      <div class="preview-tags"><span class="tag section" id="previewSection"></span><span class="tag" id="previewCategory"></span><span class="tag" id="previewSource"></span></div>
      <h3 id="previewTitle"></h3><p class="preview-summary" id="previewSummary"></p><p class="takeaway"><strong>WHY IT MATTERS</strong><span id="previewTakeaway"></span></p><div class="preview-note" id="previewNote"></div>
      <div class="preview-actions"><a class="open-link" id="previewOriginal" href="#" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a><button class="secondary-btn" id="previewEdit" type="button">메모 수정</button><button class="danger-btn" id="previewDelete" type="button">저장 삭제</button></div>
    </div>
  </section>
</div>
<div class="status" id="statusToast" aria-live="polite"></div>
"""


def _auth_config(context: str) -> dict:
    return {
        "url": SUPABASE_URL if AUTH_ENABLED else "",
        "publishableKey": SUPABASE_PUBLISHABLE_KEY if AUTH_ENABLED else "",
        "homeHref": "./" if context == "home" else "../",
    }


def _site_config() -> dict:
    return {"domain": settings.DOMAIN_ID, "table": settings.SUPABASE_TABLE}


def _supabase_script() -> str:
    if not AUTH_ENABLED:
        return ""
    return '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'


def _storage_data(picks: list[dict], now: datetime) -> list[dict]:
    return [
        {
            "title": pick["title"],
            "link": pick["link"],
            "source": pick["source"],
            "summary": pick["summary"],
            "takeaway": pick["takeaway"],
            "section": pick["section"],
            "category": pick["category"],
            "contentType": pick["content_type"],
            "briefingDate": f"{now.month}/{now.day}",
            "image": pick.get("image", ""),
            "fallbackA": pick.get("fallback_a", "#3D5A6C"),
            "fallbackB": pick.get("fallback_b", "#8AA7B7"),
        }
        for pick in picks
    ]


def _cards_html(picks: list[dict]) -> str:
    total = len(picks)
    chunks: list[str] = []
    current_section = None
    for index, pick in enumerate(picks, 1):
        section = pick.get("section", "")
        if section != current_section:
            chunks.append(f'<div class="section-divider"><h2>{html.escape(section)}</h2></div>')
            current_section = section
        chunks.append(_card(index, total, pick))
    return "".join(chunks)


def _page_html(picks: list[dict], now: datetime, context: str) -> str:
    date_big = f"{now.month}.{now.day}."
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    slug = now.strftime("%Y-%m-%d")
    chips = "".join(f"<span>{html.escape(chip)}</span>" for chip in settings.EDITORIAL_CHIPS)
    css = CSS.replace("__ACCENT__", settings.ACCENT)
    storage = _storage_data(picks, now)

    return f"""<!DOCTYPE html>
<html lang="ko" data-briefing-ui="1" data-domain="{html.escape(settings.DOMAIN_ID)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="{html.escape(settings.THEME_COLOR)}">
<title>{html.escape(settings.SITE_KOREAN_NAME)} · {html.escape(date_label)}</title>
<meta name="description" content="{html.escape(settings.INTRO_TEXT)}">
<meta property="og:title" content="{html.escape(settings.SITE_KOREAN_NAME)} · {now.month}/{now.day}">
<meta property="og:description" content="{html.escape(settings.INTRO_TEXT)}">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    {_header_html(context)}
    <div class="date-lockup"><p class="kicker">{html.escape(settings.KICKER)}</p><h1 class="date-big">{date_big}</h1><div class="date-sub">{html.escape(date_label)}</div><div class="stamp">DAILY<strong>AM 8</strong>DROP</div></div>
  </header>
  <section class="intro"><p>{html.escape(settings.INTRO_TEXT)}</p><div class="editorial-rule">{chips}</div></section>
  <main>{_cards_html(picks)}</main>
  {_archive_section(slug, context)}
  {_about_section()}
  <footer>{html.escape(settings.FOOTER_LINE)}<br>원문 링크와 자체 요약만 제공하며, 저작권은 각 원저작자에게 있습니다.<br>저장함은 로그인한 개인 계정에 동기화됩니다.</footer>
</div>
{_overlays_html()}
<script id="briefingData" type="application/json">{_safe_json_for_script(storage)}</script>
<script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config(context))}</script>
<script id="siteConfig" type="application/json">{_safe_json_for_script(_site_config())}</script>
{_supabase_script()}
<script>{JS}</script>
</body>
</html>"""


def _archive_index_html(entries: list[dict]) -> str:
    rows = "".join(
        f'<a class="archive-row" href="{entry["slug"]}.html"><span class="archive-date">{html.escape(entry["full_label"])}</span><span class="archive-count">{entry["count"]}개의 큐레이션</span><span class="archive-arrow" aria-hidden="true">→</span></a>'
        for entry in entries
    )
    if not rows:
        rows = '<p class="empty">아직 저장된 지난 브리핑이 없어요.</p>'
    css = CSS.replace("__ACCENT__", settings.ACCENT)
    return f"""<!DOCTYPE html>
<html lang="ko" data-briefing-ui="1" data-domain="{html.escape(settings.DOMAIN_ID)}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="{html.escape(settings.THEME_COLOR)}">
<title>{html.escape(settings.SITE_KOREAN_NAME)} · 지난 회차</title>
<meta name="description" content="{html.escape(settings.SITE_KOREAN_NAME)} 지난 브리핑 모아보기">
<link rel="preconnect" href="https://cdn.jsdelivr.net"><link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet"><style>{css}</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">{_header_html('archive-index')}</header>
  <header class="archive-hero"><p class="kicker">{html.escape(settings.BRAND_TOP)} MORNING ARCHIVE</p><h1>지난 브리핑</h1><p>날짜를 눌러 그날의 큐레이션을 다시 확인하세요.</p></header>
  <main class="archive-list">{rows}</main>
  {_about_section()}
  <footer>아카이브 열람에는 별도 AI 호출이나 토큰 비용이 발생하지 않습니다.<br>{html.escape(settings.FOOTER_LINE)}</footer>
</div>
{_overlays_html()}
<script id="briefingData" type="application/json">[]</script>
<script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config('archive-index'))}</script>
<script id="siteConfig" type="application/json">{_safe_json_for_script(_site_config())}</script>
{_supabase_script()}<script>{JS}</script>
</body></html>"""


def _rebuild_existing_archives(current_slug: str) -> int:
    archive_dir = DOCS_DIR / "archive"
    rebuilt = 0
    for json_path in archive_dir.glob("????-??-??.json"):
        if json_path.stem == current_slug:
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            raw_picks = data.get("picks", [])
            day = datetime.strptime(json_path.stem, "%Y-%m-%d").replace(tzinfo=KST)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(raw_picks, list) or not raw_picks:
            continue
        date_label = data.get("date_label") or f"{day.year}년 {day.month}월 {day.day}일 {WEEKDAYS[day.weekday()]}요일"
        prepared = _prepare_picks(raw_picks, date_label, fetch_missing_images=False)
        (archive_dir / f"{json_path.stem}.html").write_text(_page_html(prepared, day, "archive"), encoding="utf-8")
        rebuilt += 1
    return rebuilt


def build_page(picks: list[dict]) -> None:
    now = datetime.now(KST)
    slug = now.strftime("%Y-%m-%d")
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    DOCS_DIR.mkdir(exist_ok=True)
    archive_dir = DOCS_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    prepared = _prepare_picks(picks, date_label)
    (DOCS_DIR / "index.html").write_text(_page_html(prepared, now, "home"), encoding="utf-8")
    (archive_dir / f"{slug}.html").write_text(_page_html(prepared, now, "archive"), encoding="utf-8")
    archive_data = {
        "date": slug,
        "date_label": date_label,
        "generated_at": now.isoformat(),
        "domain": settings.DOMAIN_ID,
        "picks": prepared,
    }
    (archive_dir / f"{slug}.json").write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8")
    rebuilt = _rebuild_existing_archives(slug)
    (archive_dir / "index.html").write_text(_archive_index_html(_archive_entries()), encoding="utf-8")

    auth_status = "Supabase 로그인 활성" if AUTH_ENABLED else "로그인 설정 대기"
    print(f"[페이지 생성 완료] {settings.SITE_KOREAN_NAME} / {slug} / {len(prepared)}건 / {auth_status} / 과거 아카이브 {rebuilt}건 갱신")
