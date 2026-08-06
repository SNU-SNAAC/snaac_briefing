"""SNAAC 모닝 브리핑 정적 웹페이지 생성 모듈 (v6).

생성 파일
- docs/index.html: 오늘의 브리핑
- docs/archive/YYYY-MM-DD.html: 날짜별 브리핑
- docs/archive/YYYY-MM-DD.json: 아카이브 데이터 및 최근 중복 방지
- docs/archive/index.html: 검색 가능한 전체 지난 브리핑 목록
- docs/assets/snaac-logo.png: 상단 SNAAC 로고

주요 기능
- 마지막 업데이트 시각과 오늘자 지연 경고
- 로그인 필수 저장함, 메모, 계정 간 동기화
- 이메일·비밀번호 로그인, 비밀번호 재설정, 회원 탈퇴
- 기사 오류·페이월 신고, 익명 이용 통계, 간단한 오늘의 피드백
- 모바일 접근성, 이미지 실패 폴백, 단순 날짜형 아카이브 검색
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
SHOW_THUMBNAILS = True
ARCHIVE_KEEP = 10
DOCS_DIR = Path(os.environ.get("BRIEFING_OUTPUT_DIR", "docs"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_PUBLISHABLE_KEY = (
    os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    or os.environ.get("SUPABASE_ANON_KEY", "")
).strip()
SUPABASE_REDIRECT_URL = os.environ.get("SUPABASE_REDIRECT_URL", "").strip()
# 로그인·회원가입은 이메일과 비밀번호만 사용합니다.
TURNSTILE_SITE_KEY = ""
DELETE_ACCOUNT_FUNCTION = os.environ.get("DELETE_ACCOUNT_FUNCTION", "delete-account").strip()
PRIVACY_CONTACT_EMAIL = os.environ.get("PRIVACY_CONTACT_EMAIL", "").strip()
SITE_URL = os.environ.get("SITE_URL", "").strip()
ABOUT_URL = os.environ.get("ABOUT_URL", "https://www.snaac.co.kr").strip()
AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY)

BRIEFING_MODE = (os.environ.get("BRIEFING_MODE", "deploy") or "deploy").strip().lower()
MIXPANEL_ENABLED_REQUESTED = os.environ.get("MIXPANEL_ENABLED", "0").strip().lower() in {
    "1", "true", "yes", "on",
}
MIXPANEL_PROJECT_TOKEN = os.environ.get("MIXPANEL_PROJECT_TOKEN", "").strip()
MIXPANEL_API_HOST = (
    os.environ.get("MIXPANEL_API_HOST", "https://api.mixpanel.com")
    .strip()
    .rstrip("/")
)
MIXPANEL_CONFIGURED = bool(
    MIXPANEL_PROJECT_TOKEN
    and not any(character.isspace() for character in MIXPANEL_PROJECT_TOKEN)
    and MIXPANEL_API_HOST.startswith("https://")
)
# Preview artifact를 열어도 운영 대시보드에 테스트 이벤트가 섞이지 않게 전송은 deploy에서만 켭니다.
MIXPANEL_ENABLED = bool(
    MIXPANEL_ENABLED_REQUESTED
    and MIXPANEL_CONFIGURED
    and BRIEFING_MODE != "preview"
)

SOURCE_ASSET = Path(__file__).resolve().parent / "assets" / "snaac-logo.png"
LOGO_ASSET_NAME = "snaac-logo.png"

SOURCE_GRADIENTS = {
    "플래텀": ("#2455d6", "#7ba5ff"),
    "벤처스퀘어": ("#08735f", "#51c0a1"),
    "스타트업레시피": ("#a54d12", "#ed9a57"),
    "바이라인네트워크": ("#5a2a8f", "#aa78dc"),
    "블로터": ("#8e2947", "#de7894"),
    "지디넷 스타트업": ("#1a6385", "#69aed0"),
    "EO": ("#151515", "#525252"),
    "EO Korea": ("#151515", "#525252"),
    "YouTube": ("#c81717", "#f45b5b"),
    "LinkedIn": ("#0a66c2", "#67a8e8"),
    "a16z": ("#1e1e1e", "#747474"),
}
FALLBACK_GRADIENTS = [
    ("#2d4a74", "#7699c8"),
    ("#40604d", "#89aa94"),
    ("#70445b", "#ba829f"),
    ("#614d75", "#aa8dbc"),
    ("#6b553a", "#b49a74"),
]

CSS = r"""
@font-face{font-family:'GmarketSans';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff');font-weight:700;font-display:swap}
:root{
  --bg:#f2f2f2;--surface:#fff;--ink:#111;--muted:#686868;--soft:#ececec;
  --line:#d9d9d9;--strong:#161616;--focus:#1f5eff;--danger:#b42318;
  --success:#17653c;--warning:#8a5200;--radius:18px;--shadow:0 18px 48px rgba(0,0,0,.12)
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55;padding-bottom:calc(84px + env(safe-area-inset-bottom))}
body.modal-open{overflow:hidden;touch-action:none}
a{color:inherit}
button,input,textarea{font:inherit}
button{cursor:pointer}
button:disabled{cursor:not-allowed;opacity:.55}
:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
[hidden]{display:none!important}
.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
.wrap{width:min(100%,600px);margin:0 auto;padding:0 18px 64px}
.masthead{padding:18px 0 0}
.logo-row{display:flex;justify-content:center;padding:5px 0 13px}
.logo-link{display:inline-flex;align-items:center;justify-content:center;min-height:50px;text-decoration:none}
.site-logo{display:block;width:min(230px,62vw);height:auto;object-fit:contain}
.logo-fallback{font:700 28px/1 GmarketSans,Pretendard,sans-serif;letter-spacing:.05em}
.topline{display:grid;grid-template-columns:1fr 1.18fr 1fr;gap:7px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:9px 0}
.utility-button{min-height:44px;border:1px solid #c9c9c9;background:#fff;border-radius:12px;display:flex;align-items:center;justify-content:center;gap:6px;text-decoration:none;font-size:13px;font-weight:700;color:#252525;padding:8px 9px}
.utility-button svg,.floating-saved svg,.drawer-title svg,.save-button svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8}
.saved-vault{background:#171717;color:#fff;border-color:#171717}
.count-badge{min-width:21px;height:21px;border-radius:999px;background:#fff;color:#111;display:inline-grid;place-items:center;font-size:11px;font-weight:800;padding:0 5px}
.auth-control{overflow:hidden}
.auth-control span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.date-lockup{position:relative;padding:26px 0 20px;border-bottom:2px solid #111}
.kicker{text-transform:uppercase;letter-spacing:.18em;font-size:11px;font-weight:800;color:#666;margin:0 0 3px}
.date-big{font:700 clamp(58px,18vw,92px)/.95 GmarketSans,Pretendard,sans-serif;letter-spacing:-.055em;margin:0}
.date-sub{font-size:14px;color:#5d5d5d;margin-top:7px}
.stamp{position:absolute;right:0;top:28px;width:76px;height:76px;border:2px solid #171717;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;font:700 10px/1.2 GmarketSans,sans-serif;letter-spacing:.07em;transform:rotate(7deg)}
.stamp strong{font-size:16px;margin:2px 0}
.freshness{margin:15px 0 0;border:1px solid var(--line);border-radius:14px;background:#fff;padding:12px 14px;display:flex;gap:11px;align-items:flex-start}
.freshness-dot{width:9px;height:9px;border-radius:50%;background:#707070;margin-top:7px;flex:0 0 auto}
.freshness.is-current .freshness-dot{background:var(--success)}
.freshness.is-pending .freshness-dot{background:#c17a00}
.freshness.is-stale{border-color:#d7a54f;background:#fff8e8}
.freshness.is-stale .freshness-dot{background:#b66500}
.freshness-title{font-size:13.5px;font-weight:800;margin:0}
.freshness-copy{font-size:12.5px;color:#666;margin:2px 0 0}
.intro{padding:18px 0 22px}
.intro>p{font-size:15px;color:#4f4f4f;margin:0;word-break:keep-all}
.editorial-rule{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}
.editorial-rule span{font-size:11.5px;font-weight:700;border:1px solid #d2d2d2;background:#fff;border-radius:999px;padding:5px 9px;color:#555}
.cards{display:grid;gap:18px}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;box-shadow:0 5px 18px rgba(0,0,0,.035)}
.thumb{position:relative;display:block;aspect-ratio:16/8.6;overflow:hidden;background:linear-gradient(135deg,var(--fallback),var(--fallback-2));text-decoration:none}
.thumb img,.saved-thumb img,.preview-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.thumb.noimg::before,.saved-thumb.noimg::before,.preview-thumb.noimg::before{content:attr(data-initial);position:absolute;inset:0;display:grid;place-items:center;color:rgba(255,255,255,.92);font:700 48px/1 GmarketSans,sans-serif;background:linear-gradient(135deg,var(--fallback),var(--fallback-2))}
.media-label{position:absolute;left:12px;bottom:12px;background:rgba(0,0,0,.78);color:#fff;border-radius:999px;padding:5px 9px;font-size:10px;font-weight:800;letter-spacing:.08em}
.play-triangle{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:54px;height:54px;border-radius:50%;background:rgba(0,0,0,.72);box-shadow:0 6px 22px rgba(0,0,0,.25)}
.play-triangle::after{content:"";position:absolute;left:22px;top:16px;border-left:17px solid #fff;border-top:11px solid transparent;border-bottom:11px solid transparent}
.card-body{padding:17px 17px 18px}
.card-meta{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.meta-left{display:flex;gap:6px;flex-wrap:wrap;min-width:0}
.category,.source{display:inline-flex;align-items:center;min-height:25px;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:800}
.category{background:#111;color:#fff}
.source{background:#f0f0f0;color:#444;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-index{font:700 12px/1.8 GmarketSans,sans-serif;color:#7a7a7a;flex:0 0 auto}
.title-link{text-decoration:none;display:block}
.card h2{font-size:19px;line-height:1.4;letter-spacing:-.015em;margin:12px 0 7px;word-break:keep-all}
.summary{font-size:14.5px;line-height:1.62;color:#555;margin:0;word-break:keep-all}
.article-facts{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0}
.article-facts span{font-size:11.5px;color:#656565;background:#f5f5f5;border:1px solid #e4e4e4;border-radius:999px;padding:4px 8px}
.takeaway{margin-top:14px;padding:13px 14px;background:#f4f4f4;border-left:3px solid #111;border-radius:0 11px 11px 0}
.takeaway-label{font-size:10px;letter-spacing:.13em;font-weight:900;color:#5a5a5a}
.takeaway p{font-size:13.5px;font-weight:650;margin:4px 0 0;word-break:keep-all}
.card-actions{display:grid;grid-template-columns:1fr auto auto;gap:7px;margin-top:15px}
.read-link,.save-button,.report-button{min-height:43px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;font-size:13px;font-weight:800;padding:9px 12px}
.read-link{background:#171717;color:#fff}
.save-button,.report-button{border:1px solid #cfcfcf;background:#fff;color:#222;gap:6px}
.save-button.is-saved{background:#e9e9e9;border-color:#949494}
.report-button{width:44px;padding:0;color:#666}
.feedback{margin-top:22px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:11px 1px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.feedback-copy{min-width:0;flex:1}
.feedback h2{font-size:12.5px;margin:0;font-weight:800}
.feedback p{font-size:11px;color:#777;margin:2px 0 0}
.feedback-actions{display:flex;gap:6px;margin:0}
.feedback-button{min-height:34px;border:1px solid #cfcfcf;background:#fff;border-radius:999px;font-size:11px;font-weight:800;padding:6px 10px;white-space:nowrap}
.feedback-button.is-selected{background:#171717;color:#fff;border-color:#171717}
.feedback-thanks{width:100%;font-size:11px;font-weight:700;margin:0;color:var(--success)}
.archive-section,.about-snaac-section{margin-top:34px}
.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:11px}
.section-head h2{font-size:16px;margin:0}
.section-head a{font-size:12.5px;color:#555}
.archive-list{display:grid;gap:8px}
.archive-row{display:grid;grid-template-columns:1fr auto auto;gap:9px;align-items:center;min-height:52px;padding:10px 13px;border:1px solid var(--line);background:#fff;border-radius:12px;text-decoration:none}
.archive-date{font-size:13.5px;font-weight:800}
.archive-count{font-size:11.5px;color:#777}
.archive-arrow{font-size:17px}
.empty-archive{background:#fff;border:1px dashed #cfcfcf;border-radius:12px;padding:18px;color:#777;font-size:13px}
.about-snaac-card{display:flex;flex-direction:column;background:#171717;color:#fff;border-radius:16px;padding:20px;text-decoration:none;position:relative;overflow:hidden}
.about-snaac-card::after{content:"→";position:absolute;right:18px;top:17px;font-size:22px}
.about-snaac-eyebrow{font-size:10px;letter-spacing:.17em;font-weight:900;color:#bdbdbd}
.about-snaac-title{font-size:18px;font-weight:800;margin-top:8px}
.about-snaac-copy{font-size:13px;color:#c9c9c9;max-width:82%;margin-top:5px}
footer{margin-top:36px;border-top:1px solid var(--line);padding:22px 0 0;text-align:center;font-size:11.5px;line-height:1.8;color:#777}
.footer-links{display:flex;justify-content:center;gap:14px;margin-top:8px}
.footer-link{border:0;background:none;padding:3px;text-decoration:underline;color:#555;font-size:12px}
.floating-saved{position:fixed;z-index:30;left:50%;bottom:calc(13px + env(safe-area-inset-bottom));transform:translateX(-50%);min-height:50px;border:0;border-radius:999px;background:#171717;color:#fff;box-shadow:0 10px 30px rgba(0,0,0,.28);display:flex;align-items:center;gap:8px;padding:10px 17px;font-weight:800}
.overlay{position:fixed;inset:0;z-index:60;display:flex;align-items:flex-end;justify-content:center}
.overlay-backdrop{position:absolute;inset:0;border:0;background:rgba(0,0,0,.48);width:100%;height:100%}
.panel{position:relative;z-index:1;width:min(100%,600px);max-height:min(88dvh,820px);overflow:auto;background:#fff;border-radius:22px 22px 0 0;padding:13px 18px calc(22px + env(safe-area-inset-bottom));box-shadow:var(--shadow);overscroll-behavior:contain}
.drawer-handle{width:42px;height:4px;border-radius:999px;background:#d0d0d0;margin:0 auto 10px}
.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
.panel-head h2{font-size:20px;margin:0}
.panel-head p{font-size:12.5px;color:#6b6b6b;margin:3px 0 0}
.close-button{border:1px solid #d2d2d2;background:#fff;width:42px;height:42px;border-radius:50%;font-size:23px;line-height:1}
.sync-strip{display:flex;align-items:center;justify-content:space-between;gap:10px;background:#f1f1f1;border-radius:13px;padding:12px;margin-bottom:13px}
.sync-title{font-size:12.5px;font-weight:800;margin:0}.sync-text{font-size:11.5px;color:#676767;margin:2px 0 0}
.sync-action{border:0;border-radius:9px;background:#171717;color:#fff;min-height:38px;padding:8px 11px;font-size:12px;font-weight:800}
.saved-list{display:grid;gap:11px}
.saved-empty{border:1px dashed #ccc;border-radius:12px;padding:22px;text-align:center;color:#777;font-size:13px}
.saved-item{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.saved-preview-trigger{display:grid;grid-template-columns:94px 1fr;gap:12px;width:100%;border:0;background:#fff;text-align:left;padding:0}
.saved-thumb{position:relative;min-height:105px;background:linear-gradient(135deg,var(--fallback),var(--fallback-2));overflow:hidden}
.saved-thumb.noimg::before{font-size:31px}
.saved-copy{display:flex;flex-direction:column;padding:12px 12px 10px 0;min-width:0}
.saved-meta{font-size:10.5px;color:#777}.saved-title{font-size:14px;font-weight:800;line-height:1.42;margin-top:4px}
.saved-note-preview{font-size:11.5px;color:#555;margin-top:7px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.saved-open-hint{font-size:11px;font-weight:800;margin-top:auto;padding-top:8px}
.saved-actions{display:grid;grid-template-columns:1fr 1fr auto;border-top:1px solid var(--line)}
.saved-action-button{min-height:41px;border:0;background:#fafafa;border-right:1px solid var(--line);font-size:11.5px;font-weight:750}
.saved-action-button:last-child{border-right:0;color:var(--danger)}
.form-label{display:flex;justify-content:space-between;font-size:12.5px;font-weight:800;margin:12px 0 6px}
.form-input,.form-textarea,.archive-search{width:100%;border:1px solid #c9c9c9;border-radius:11px;background:#fff;min-height:46px;padding:11px 12px;color:#111}
.form-textarea{min-height:110px;resize:vertical}
.form-help{font-size:11.5px;color:#777;margin:6px 0 0}
.form-actions{display:flex;gap:8px;margin-top:15px}
.secondary-button,.primary-button,.danger-button{min-height:44px;border-radius:11px;padding:10px 13px;font-size:13px;font-weight:800}
.secondary-button{border:1px solid #ccc;background:#fff;color:#222}.primary-button{border:1px solid #171717;background:#171717;color:#fff;flex:1}.danger-button{border:1px solid #c44237;background:#fff;color:var(--danger);width:100%;margin-top:9px}
.preview-card{border:1px solid var(--line);border-radius:16px;overflow:hidden}
.preview-thumb{position:relative;aspect-ratio:16/8.5;overflow:hidden;background:linear-gradient(135deg,var(--fallback),var(--fallback-2))}
.preview-body{padding:16px}.preview-body h3{font-size:20px;line-height:1.4;margin:11px 0 8px}.preview-summary{font-size:14px;color:#555}
.preview-note{margin-top:13px;border:1px dashed #aaa;border-radius:11px;padding:11px;font-size:13px}.preview-note strong{display:block;font-size:10px;letter-spacing:.12em;margin-bottom:4px}
.preview-actions{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:14px}.preview-read,.preview-secondary{min-height:44px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800}.preview-read{background:#171717;color:#fff;text-decoration:none}.preview-secondary{border:1px solid #ccc;background:#fff;padding:9px 12px}.preview-delete{border:0;background:none;color:var(--danger);text-decoration:underline;width:100%;margin-top:13px;font-size:12px}
.auth-tabs{display:grid;grid-template-columns:1fr 1fr;background:#eee;border-radius:11px;padding:4px;margin-bottom:13px}.auth-tab{min-height:39px;border:0;background:transparent;border-radius:8px;font-weight:800;color:#666}.auth-tab.is-active{background:#fff;color:#111;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.auth-intent{background:#fff4d9;border:1px solid #e7c87f;border-radius:10px;padding:10px;font-size:12.5px;margin:0 0 12px}
.auth-message{min-height:20px;font-size:12px;color:var(--success);margin:8px 0}.auth-message.is-error{color:var(--danger)}.auth-help{font-size:11.5px;color:#777;margin:8px 0 0}
.auth-link-row{display:flex;justify-content:space-between;gap:10px;margin-top:9px}.text-button{border:0;background:none;text-decoration:underline;color:#555;font-size:12px;padding:4px 0}
.account-card{background:#f2f2f2;border-radius:13px;padding:14px}.account-eyebrow{font-size:9px;letter-spacing:.14em;font-weight:900;color:#777;margin:0}.account-email{font-size:15px;font-weight:800;word-break:break-all;margin:5px 0}.account-copy{font-size:12px;color:#666;margin:0}.account-actions{display:grid;gap:8px;margin-top:12px}.account-action{min-height:43px;border:1px solid #ccc;background:#fff;border-radius:10px;font-weight:800}.account-action.is-danger{color:var(--danger);border-color:#d9a5a1}
.report-options{display:grid;gap:8px;margin:10px 0}.report-option{display:flex;align-items:flex-start;gap:9px;border:1px solid #d2d2d2;border-radius:11px;padding:10px;font-size:13px}.report-option input{margin-top:3px}
.privacy-copy h3{font-size:15px;margin:17px 0 5px}.privacy-copy p,.privacy-copy li{font-size:12.5px;color:#555}.privacy-copy ul{padding-left:20px}.privacy-copy a{word-break:break-all}.privacy-copy .account-action{width:100%;margin-top:8px}
.archive-hero{padding:27px 0 20px;border-bottom:2px solid #111}.archive-hero h1{font:700 clamp(40px,13vw,64px)/1 GmarketSans,sans-serif;margin:4px 0 8px}.archive-hero p{font-size:13.5px;color:#666;margin:0}
.archive-tools{position:sticky;top:0;z-index:10;background:linear-gradient(var(--bg) 82%,transparent);padding:14px 0 10px}.archive-search{background:#fff}.archive-page-list{padding-top:4px}.archive-month-label{font-size:11px;letter-spacing:.12em;color:#777;font-weight:900;margin:20px 0 8px}.archive-no-result{padding:25px;border:1px dashed #bbb;background:#fff;border-radius:13px;text-align:center;color:#777;font-size:13px}
.saved-tools{display:grid;gap:9px;margin-bottom:12px}.saved-search{width:100%;border:1px solid #c9c9c9;border-radius:11px;background:#fff;min-height:44px;padding:10px 12px}.saved-search-status{font-size:11px;color:#777;margin:0}.saved-tags,.preview-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.saved-tag,.preview-tag{display:inline-flex;border:1px solid #d0d0d0;background:#f7f7f7;border-radius:999px;padding:3px 7px;font-size:10px;font-weight:750;color:#555}
.tag-input{width:100%;border:1px solid #c9c9c9;border-radius:11px;background:#fff;min-height:46px;padding:11px 12px;color:#111}.tag-hint{font-size:11px;color:#777;margin:5px 0 0}
.status-pill{display:inline-flex;border-radius:999px;padding:3px 8px;background:#efefef;font-size:10.5px;font-weight:800;color:#555}
@media(max-width:390px){.wrap{padding-left:14px;padding-right:14px}.topline{gap:5px}.utility-button{font-size:11.5px;padding:7px 5px}.stamp{width:66px;height:66px;font-size:9px}.stamp strong{font-size:14px}.card-actions{grid-template-columns:1fr auto auto}.source{max-width:125px}.saved-preview-trigger{grid-template-columns:82px 1fr}}
@media(min-width:601px){.overlay{align-items:center}.panel{border-radius:22px;max-height:86vh}.floating-saved{bottom:20px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation:none!important;transition:none!important}}
"""

MIXPANEL_BOOTSTRAP_JS = r"""
(() => {
  'use strict';

  const configElement = document.getElementById('mixpanelConfig');
  const config = configElement ? JSON.parse(configElement.textContent || '{}') : {};
  const INTERNAL_KEY = 'snaac-internal-analytics-v1';
  const ANALYTICS_OPTOUT_KEY = 'snaac-analytics-optout-v1';
  const ATTRIBUTION_KEY = 'snaac-mixpanel-attribution-v1';
  const SENSITIVE_QUERY_KEYS = new Set([
    'access_token','refresh_token','provider_token','token','code','email','recovery','type','expires_in'
  ]);
  const UTM_KEYS = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'];

  function readLocal(key) {
    try { return localStorage.getItem(key); }
    catch (error) { return null; }
  }

  function writeLocal(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, value);
    } catch (error) {}
  }

  function readSessionJson(key) {
    try { return JSON.parse(sessionStorage.getItem(key) || '{}'); }
    catch (error) { return {}; }
  }

  function writeSessionJson(key, value) {
    try { sessionStorage.setItem(key, JSON.stringify(value)); }
    catch (error) {}
  }

  function applyInternalModeFromUrl() {
    try {
      const url = new URL(window.location.href);
      const value = url.searchParams.get('internal');
      if (value === '1') writeLocal(INTERNAL_KEY, '1');
      if (value === '0') writeLocal(INTERNAL_KEY, null);
      if (value === '1' || value === '0') {
        url.searchParams.delete('internal');
        history.replaceState(history.state, '', `${url.pathname}${url.search}${url.hash}`);
      }
    } catch (error) {}
  }

  function sanitizedLocation() {
    try {
      const url = new URL(window.location.href);
      Array.from(url.searchParams.keys()).forEach(key => {
        if (SENSITIVE_QUERY_KEYS.has(key.toLowerCase()) || key.toLowerCase() === 'internal') {
          url.searchParams.delete(key);
        }
      });
      url.hash = '';
      return url;
    } catch (error) {
      return null;
    }
  }

  function attributionProperties(url) {
    const stored = readSessionJson(ATTRIBUTION_KEY);
    const next = {...stored};
    if (url) {
      UTM_KEYS.forEach(key => {
        const value = String(url.searchParams.get(key) || '').trim().slice(0, 200);
        if (value) next[key] = value;
      });
    }
    if (!next.referrer_domain && document.referrer) {
      try { next.referrer_domain = new URL(document.referrer).hostname.slice(0, 200); }
      catch (error) {}
    }
    if (!next.landing_path && url) next.landing_path = url.pathname.slice(0, 500);
    writeSessionJson(ATTRIBUTION_KEY, next);
    return next;
  }

  function dntEnabled() {
    return navigator.doNotTrack === '1' || window.doNotTrack === '1';
  }

  applyInternalModeFromUrl();
  const internal = readLocal(INTERNAL_KEY) === '1';
  const optedOut = readLocal(ANALYTICS_OPTOUT_KEY) === '1';
  const dnt = dntEnabled();
  const locationUrl = sanitizedLocation();
  const attribution = attributionProperties(locationUrl);
  window.__snaacInternalAnalytics = internal;
  window.__snaacMixpanelAttribution = attribution;

  const pageViewProperties = {
    current_page_title: document.title,
    current_domain: window.location.hostname,
    current_url_path: locationUrl ? locationUrl.pathname : window.location.pathname,
    current_url_protocol: window.location.protocol.replace(':',''),
    current_url_search: locationUrl ? locationUrl.search : '',
    page_url: locationUrl ? locationUrl.toString() : `${window.location.origin}${window.location.pathname}`,
    ...attribution,
  };
  window.__snaacMixpanelPageViewProperties = pageViewProperties;

  // preview 모드에서는 config.enabled가 false라 SDK를 불러오지 않고 테스트 데이터도 전송하지 않습니다.
  if (!config.enabled || !config.token || !config.apiHost) return;

  // Official Mixpanel browser loader. It queues calls until the SDK has loaded.
  (function(f,b){
    if(!b.__SV){
      var e,g,i,h;
      window.mixpanel=b;
      b._i=[];
      b.init=function(e,f,c){
        function g(a,d){
          var parts=d.split('.');
          if(parts.length===2){a=a[parts[0]];d=parts[1];}
          a[d]=function(){a.push([d].concat(Array.prototype.slice.call(arguments,0)));};
        }
        var instance=b;
        if(typeof c!=='undefined') instance=b[c]=[];
        else c='mixpanel';
        instance.people=instance.people||[];
        instance.toString=function(isPeople){
          var name='mixpanel';
          if(c!=='mixpanel') name+='.'+c;
          if(!isPeople) name+=' (stub)';
          return name;
        };
        instance.people.toString=function(){return instance.toString(1)+'.people (stub)';};
        i='disable time_event track track_pageview track_links track_forms track_with_groups add_group set_group remove_group register register_once alias unregister identify name_tag set_config reset opt_in_tracking opt_out_tracking has_opted_in_tracking has_opted_out_tracking clear_opt_in_out_tracking start_batch_senders people.set people.set_once people.unset people.increment people.append people.union people.track_charge people.clear_charges people.delete_user people.remove'.split(' ');
        for(h=0;h<i.length;h++) g(instance,i[h]);
        var groupMethods='set set_once union unset remove delete'.split(' ');
        instance.get_group=function(){
          var group=[];
          var descriptor=['get_group'].concat(Array.prototype.slice.call(arguments,0));
          group.push=function(call){instance.push([descriptor,call]);};
          for(var idx=0;idx<groupMethods.length;idx++){
            (function(method){
              group[method]=function(){
                group.push([method].concat(Array.prototype.slice.call(arguments,0)));
              };
            })(groupMethods[idx]);
          }
          return group;
        };
        b._i.push([e,f,c]);
      };
      b.__SV=1.2;
      e=f.createElement('script');
      e.type='text/javascript';
      e.async=true;
      e.src='https://cdn.mxpnl.com/libs/mixpanel-2-latest.min.js';
      g=f.getElementsByTagName('script')[0];
      g.parentNode.insertBefore(e,g);
    }
  })(document,window.mixpanel||[]);

  window.mixpanel.init(config.token, {
    api_host: config.apiHost,
    persistence: 'localStorage',
    autocapture: false,
    track_pageview: false,
    record_sessions_percent: 0,
    record_heatmap_data: false,
    ip: false,
    debug: false,
    batch_requests: true,
    opt_out_tracking_by_default: internal || optedOut || dnt,
    property_blacklist: ['$current_url','$initial_referrer','$referrer'],
  });

  window.mixpanel.register({
    product_name: 'SNAAC Briefing',
    analytics_schema_version: 'mixpanel-v1',
  });

  if (internal || optedOut || dnt) {
    window.mixpanel.opt_out_tracking();
  } else {
    window.mixpanel.track('$mp_web_page_view', pageViewProperties, {send_immediately:true});
  }

  window.__snaacMixpanelReady = true;
  window.dispatchEvent(new CustomEvent('snaac:mixpanel-ready'));
})();
"""

JS = r"""
(() => {
  'use strict';

  const GUEST_STORAGE_KEY = 'snaac-saved-articles-v1';
  const USER_STORAGE_PREFIX = 'snaac-saved-articles-user-v1:';
  const SESSION_KEY = 'snaac-anonymous-session-v1';
  const ANALYTICS_OPTOUT_KEY = 'snaac-analytics-optout-v1';
  const INTERNAL_ANALYTICS_KEY = 'snaac-internal-analytics-v1';
  const dataElement = document.getElementById('briefingData');
  const configElement = document.getElementById('pageConfig');
  const authConfigElement = document.getElementById('authConfig');
  const mixpanelConfigElement = document.getElementById('mixpanelConfig');
  const currentItems = dataElement ? JSON.parse(dataElement.textContent || '[]') : [];
  const pageConfig = configElement ? JSON.parse(configElement.textContent || '{}') : {};
  const authConfig = authConfigElement ? JSON.parse(authConfigElement.textContent || '{}') : {};
  const mixpanelConfig = mixpanelConfigElement ? JSON.parse(mixpanelConfigElement.textContent || '{}') : {};
  const currentByUrl = new Map(currentItems.map(item => [item.link, normalizeItem(item)]));

  let currentUser = null;
  let supabaseClient = null;
  let savedItems = [];
  let activeNoteUrl = '';
  let activePreviewUrl = '';
  let activeReportUrl = '';
  let authMode = 'login';
  let pendingSaveUrl = '';
  let pendingOpenSaved = false;
  let storageAvailable = true;
  let syncBusy = false;
  let recoveryMode = false;
  let savedSearchQuery = '';
  let archiveSearchTimer = 0;
  let activeSeconds = 0;
  let maxScrollDepth = 0;
  let reachedScroll50 = false;
  let reachedScroll90 = false;
  let engaged30Sent = false;
  let sessionEndSent = false;
  let lastActivityAt = Date.now();
  const lastFocused = new WeakMap();
  const authEnabled = Boolean(authConfig.url && authConfig.publishableKey);
  const mixpanelEnabled = Boolean(mixpanelConfig.enabled && window.mixpanel);
  const meaningfulSessionKey = `snaac-meaningful-read:${pageConfig.briefingDate || 'archive'}:${pageConfig.context || 'home'}`;
  let meaningfulReadSent = (() => {
    try { return sessionStorage.getItem(meaningfulSessionKey) === '1'; }
    catch (error) { return false; }
  })();

  const byId = id => document.getElementById(id);
  const liveRegion = byId('liveStatus');
  const drawer = byId('savedDrawer');
  const noteDialog = byId('noteDialog');
  const previewDialog = byId('previewDialog');
  const authDialog = byId('authDialog');
  const reportDialog = byId('reportDialog');
  const privacyDialog = byId('privacyDialog');
  const deleteDialog = byId('deleteDialog');
  const allOverlays = [drawer, noteDialog, previewDialog, authDialog, reportDialog, privacyDialog, deleteDialog];

  function announce(message) {
    if (!liveRegion) return;
    liveRegion.textContent = '';
    window.setTimeout(() => { liveRegion.textContent = message; }, 20);
  }

  function normalizeTags(value) {
    const raw = Array.isArray(value) ? value : String(value || '').split(/[,#\n]/);
    return Array.from(new Set(raw.map(tag => String(tag || '').trim()).filter(Boolean).map(tag => tag.slice(0,20)))).slice(0,5);
  }

  function normalizeItem(item) {
    const now = new Date().toISOString();
    return {
      title: String(item?.title || '').trim(),
      link: String(item?.link || item?.article_url || '').trim(),
      source: String(item?.source || '기타').trim() || '기타',
      summary: String(item?.summary || '').trim(),
      takeaway: String(item?.takeaway || '').trim(),
      category: String(item?.category || '생태계 업데이트').trim(),
      contentType: String(item?.contentType || item?.content_type || '기사').trim(),
      published: String(item?.published || '').trim(),
      briefingDate: String(item?.briefingDate || item?.briefing_date || '').trim(),
      briefingSlug: String(item?.briefingSlug || item?.briefing_slug || pageConfig.briefingDate || '').trim(),
      image: String(item?.image || item?.thumbnail_url || '').trim(),
      fallbackA: String(item?.fallbackA || item?.fallback_a || '#2d4a74').trim(),
      fallbackB: String(item?.fallbackB || item?.fallback_b || '#7699c8').trim(),
      note: String(item?.note || ''),
      tags: normalizeTags(item?.tags || item?.tag_list || []),
      savedAt: String(item?.savedAt || item?.saved_at || now),
      updatedAt: String(item?.updatedAt || item?.updated_at || now),
      pendingSync: Boolean(item?.pendingSync),
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
    try { localStorage.removeItem(key); } catch (error) { storageAvailable = false; }
  }

  function anonymousSession() {
    try {
      let value = localStorage.getItem(SESSION_KEY);
      if (!value) {
        value = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
        localStorage.setItem(SESSION_KEY, value);
      }
      return value;
    } catch (error) {
      return 'storage-unavailable';
    }
  }

  function userAnalyticsOptedOut() {
    try { return localStorage.getItem(ANALYTICS_OPTOUT_KEY) === '1'; }
    catch (error) { return false; }
  }

  function internalAnalyticsMode() {
    try {
      return window.__snaacInternalAnalytics === true || localStorage.getItem(INTERNAL_ANALYTICS_KEY) === '1';
    } catch (error) {
      return window.__snaacInternalAnalytics === true;
    }
  }

  function browserDoNotTrackEnabled() {
    const value = navigator.doNotTrack || window.doNotTrack || navigator.msDoNotTrack;
    return value === '1' || value === 'yes';
  }

  function analyticsOptedOut() {
    return userAnalyticsOptedOut() || internalAnalyticsMode() || browserDoNotTrackEnabled();
  }

  function updateAnalyticsPreferenceUi() {
    const button = byId('analyticsPreferenceButton');
    const status = byId('analyticsPreferenceStatus');
    if (!button || !status) return;
    const internal = internalAnalyticsMode();
    const dnt = browserDoNotTrackEnabled();
    const optedOut = userAnalyticsOptedOut();
    button.disabled = internal || dnt;
    button.textContent = internal
      ? '운영자 제외 모드 적용 중'
      : (dnt ? '브라우저 추적 방지 적용 중' : (optedOut ? '익명 통계 다시 허용' : '익명 통계 끄기'));
    status.textContent = internal
      ? '현재 브라우저는 운영자 제외 모드라 이용 통계를 보내지 않습니다.'
      : (dnt
          ? '브라우저의 Do Not Track 설정에 따라 이용 통계를 보내지 않습니다.'
          : (optedOut ? '현재 익명 이용 통계를 보내지 않습니다.' : '현재 개인을 식별하지 않는 최소 이용 통계를 사용합니다.'));
  }

  function syncMixpanelConsent(allowExplicitOptIn = false) {
    if (!mixpanelEnabled || !window.mixpanel) return;
    if (analyticsOptedOut()) window.mixpanel.opt_out_tracking();
    else if (allowExplicitOptIn) window.mixpanel.opt_in_tracking();
  }

  function toggleAnalyticsPreference() {
    if (internalAnalyticsMode()) {
      announce('운영자 제외 모드에서는 통계를 켤 수 없어요. 주소에 ?internal=0을 붙여 해제할 수 있습니다.');
      return;
    }
    if (browserDoNotTrackEnabled()) {
      announce('브라우저의 Do Not Track 설정이 켜져 있어 이용 통계를 보낼 수 없어요.');
      return;
    }
    try {
      const nextOptOut = !userAnalyticsOptedOut();
      localStorage.setItem(ANALYTICS_OPTOUT_KEY, nextOptOut ? '1' : '0');
      if (nextOptOut) localStorage.removeItem(SESSION_KEY);
      syncMixpanelConsent(!nextOptOut);
      updateAnalyticsPreferenceUi();
      if (!nextOptOut) {
        captureMixpanelEvent('analytics_opted_in', null, {source:'privacy_control'});
        captureMixpanelPageView({consent_restored:true});
        captureMixpanelEvent('briefing_viewed', null, initialBriefingProperties({consent_restored:true}));
      }
      announce(nextOptOut ? '익명 이용 통계를 껐어요.' : '익명 이용 통계를 다시 허용했어요.');
    } catch (error) {
      announce('브라우저 저장소를 사용할 수 없어 설정을 바꾸지 못했어요.');
    }
  }




  function safePublicUrl(value) {
    if (!value) return '';
    try {
      const url = new URL(String(value), window.location.origin);
      ['access_token','refresh_token','token','code','email','recovery','type','provider_token'].forEach(key => url.searchParams.delete(key));
      url.hash = '';
      return url.toString();
    } catch (error) {
      return String(value).split('#')[0];
    }
  }

  function articlePositionFromElement(element) {
    const card = element?.closest?.('[data-article-card]');
    const value = Number(card?.dataset.articlePosition || 0);
    return Number.isFinite(value) ? value : 0;
  }

  function articleProperties(article, metadata = {}) {
    return {
      briefing_date: pageConfig.briefingDate || '',
      page_context: pageConfig.context || 'home',
      article_url: safePublicUrl(article?.link || ''),
      article_title: article?.title || '',
      article_source: article?.source || '',
      article_category: article?.category || '',
      content_type: article?.contentType || '',
      ...(window.__snaacMixpanelAttribution || {}),
      ...metadata,
    };
  }

  function initialBriefingProperties(extra = {}) {
    const today = formatKstDate(new Date()).slug;
    return {
      briefing_date: pageConfig.briefingDate || '',
      page_context: pageConfig.context || 'home',
      article_count: currentItems.length,
      is_fresh: Boolean(pageConfig.context === 'home' && pageConfig.briefingDate === today),
      is_logged_in: currentUser ? true : (authEnabled ? 'unknown' : false),
      ...extra,
    };
  }

  function captureMixpanelEvent(eventName, article = null, metadata = {}, captureOptions = undefined) {
    if (!mixpanelEnabled || !window.mixpanel || analyticsOptedOut()) return;
    window.mixpanel.track(eventName, articleProperties(article, metadata), captureOptions);
  }

  function captureMixpanelPageView(extra = {}) {
    if (!mixpanelEnabled || !window.mixpanel || analyticsOptedOut()) return;
    const properties = {
      ...(window.__snaacMixpanelPageViewProperties || {}),
      ...extra,
    };
    window.mixpanel.track('$mp_web_page_view', properties, {send_immediately:true});
  }

  function identifyMixpanelUser(user) {
    if (!mixpanelEnabled || !window.mixpanel || analyticsOptedOut() || !user?.id) return;
    window.mixpanel.identify(user.id);
    window.mixpanel.register({is_logged_in:true});
  }

  function resetMixpanelUser() {
    if (!mixpanelEnabled || !window.mixpanel) return;
    window.mixpanel.reset();
    window.mixpanel.register({is_logged_in:false});
    syncMixpanelConsent();
  }

  function markMeaningfulRead(trigger, article = null, metadata = {}) {
    if (meaningfulReadSent || analyticsOptedOut() || !currentItems.length) return;
    meaningfulReadSent = true;
    try { sessionStorage.setItem(meaningfulSessionKey, '1'); } catch (error) {}
    captureMixpanelEvent('meaningful_read', article, {
      trigger,
      active_seconds: activeSeconds,
      max_scroll_depth: maxScrollDepth,
      ...metadata,
    });
  }

  function updateScrollAnalytics() {
    const root = document.documentElement;
    const documentHeight = Math.max(root.scrollHeight, document.body.scrollHeight, 1);
    const depth = Math.min(100, Math.max(0, Math.round(((window.scrollY + window.innerHeight) / documentHeight) * 100)));
    maxScrollDepth = Math.max(maxScrollDepth, depth);
    if (depth >= 50 && !reachedScroll50) {
      reachedScroll50 = true;
      captureMixpanelEvent('scroll_depth_reached', null, {depth:50});
      if (engaged30Sent) markMeaningfulRead('engaged_30s_and_scroll_50');
    }
    if (depth >= 90 && !reachedScroll90) {
      reachedScroll90 = true;
      captureMixpanelEvent('scroll_depth_reached', null, {depth:90});
    }
  }

  function setupArticleImpressions() {
    const cards = Array.from(document.querySelectorAll('[data-article-card]'));
    if (!cards.length || !('IntersectionObserver' in window)) return;
    const seen = new WeakSet();
    const timers = new WeakMap();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const card = entry.target;
        if (seen.has(card)) return;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          if (timers.has(card)) return;
          const timer = window.setTimeout(() => {
            timers.delete(card);
            if (seen.has(card)) return;
            seen.add(card);
            const item = currentByUrl.get(card.dataset.articleUrl || '');
            captureMixpanelEvent('article_impression', item, {
              position: Number(card.dataset.articlePosition || 0),
              visibility_threshold: 0.5,
              visible_ms: 1000,
            });
            observer.unobserve(card);
          }, 1000);
          timers.set(card, timer);
        } else if (timers.has(card)) {
          window.clearTimeout(timers.get(card));
          timers.delete(card);
        }
      });
    }, {threshold:[0,0.5,1]});
    cards.forEach(card => observer.observe(card));
  }

  function sendSessionEnd() {
    if (sessionEndSent || analyticsOptedOut()) return;
    sessionEndSent = true;
    captureMixpanelEvent('briefing_session_ended', null, {
      active_seconds: activeSeconds,
      max_scroll_depth: maxScrollDepth,
      engaged_30s: engaged30Sent,
    }, {send_immediately:true});
  }

  function setupEngagementAnalytics() {
    ['pointerdown','touchstart','keydown'].forEach(type => {
      document.addEventListener(type, () => { lastActivityAt = Date.now(); }, {passive:true});
    });
    window.addEventListener('scroll', () => {
      lastActivityAt = Date.now();
      updateScrollAnalytics();
    }, {passive:true});
    updateScrollAnalytics();
    window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - lastActivityAt > 60000) return;
      activeSeconds += 1;
      if (activeSeconds >= 30 && !engaged30Sent) {
        engaged30Sent = true;
        captureMixpanelEvent('engaged_30s', null, {active_seconds:activeSeconds});
        if (reachedScroll50) markMeaningfulRead('engaged_30s_and_scroll_50');
      }
    }, 1000);
    window.addEventListener('pagehide', sendSessionEnd, {once:true});
    setupArticleImpressions();
  }

  function initializeProductAnalytics() {
    syncMixpanelConsent();
    captureMixpanelEvent('briefing_viewed', null, initialBriefingProperties());
    setupEngagementAnalytics();
  }

  function activeStorageKey() {
    return currentUser ? `${USER_STORAGE_PREFIX}${currentUser.id}` : GUEST_STORAGE_KEY;
  }

  function persistActive() { return writeStorage(activeStorageKey(), savedItems); }
  function itemForUrl(url) { return savedItems.find(item => item.link === url) || currentByUrl.get(url) || null; }
  function isOpen(element) { return Boolean(element && !element.hidden); }

  function syncBodyLock() {
    document.body.classList.toggle('modal-open', allOverlays.some(isOpen));
  }

  function openOverlay(element, trigger = document.activeElement) {
    if (!element) return;
    lastFocused.set(element, trigger);
    element.hidden = false;
    syncBodyLock();
    window.setTimeout(() => {
      const target = element.querySelector('[autofocus], input:not([type="hidden"]), textarea, button, a[href]');
      target?.focus();
    }, 35);
  }

  function closeOverlay(element, restore = true) {
    if (!element) return;
    element.hidden = true;
    syncBodyLock();
    if (restore) lastFocused.get(element)?.focus?.();
  }

  function focusableWithin(element) {
    return Array.from(element.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])')).filter(node => !node.hidden && node.offsetParent !== null);
  }

  function trapFocus(event, element) {
    if (event.key !== 'Tab' || !isOpen(element)) return;
    const items = focusableWithin(element);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  function formatKstDate(date) {
    const parts = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hourCycle:'h23'}).formatToParts(date);
    const map = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return { slug:`${map.year}-${map.month}-${map.day}`, hour:Number(map.hour || 0) };
  }

  function updateFreshness() {
    const box = byId('freshness');
    const title = byId('freshnessTitle');
    const copy = byId('freshnessCopy');
    if (!box || !title || !copy) return;
    const generated = new Date(pageConfig.generatedAt || '');
    const generatedText = Number.isFinite(generated.getTime())
      ? new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul',month:'long',day:'numeric',hour:'numeric',minute:'2-digit'}).format(generated)
      : '시간 확인 불가';

    if (pageConfig.context !== 'home') {
      box.classList.add('is-current');
      title.textContent = `${pageConfig.briefingLabel || '지난'} 회차`;
      copy.textContent = `생성 시각 · ${generatedText}`;
      return;
    }

    const now = formatKstDate(new Date());
    const todayNumber = Date.parse(`${now.slug}T00:00:00+09:00`);
    const briefingNumber = Date.parse(`${pageConfig.briefingDate || ''}T00:00:00+09:00`);
    const ageDays = Number.isFinite(todayNumber) && Number.isFinite(briefingNumber)
      ? Math.round((todayNumber - briefingNumber) / 86400000)
      : 999;
    if (now.slug === pageConfig.briefingDate) {
      box.classList.add('is-current');
      title.textContent = '오늘 브리핑이 업데이트됐어요.';
      copy.textContent = `마지막 업데이트 · ${generatedText}`;
    } else if (ageDays === 1 && now.hour < 9) {
      box.classList.add('is-pending');
      title.textContent = '오늘 브리핑을 준비하고 있어요.';
      copy.textContent = `현재는 ${pageConfig.briefingLabel || pageConfig.briefingDate} 회차입니다. 오전 9시 전 다시 확인해 주세요.`;
    } else {
      box.classList.add('is-stale');
      title.textContent = '오늘 브리핑 업데이트가 지연되고 있어요.';
      copy.textContent = `현재는 ${pageConfig.briefingLabel || pageConfig.briefingDate} 회차입니다. 운영팀이 확인 중입니다.`;
    }
  }

  function updateSavedIndicators() {
    const map = new Map(savedItems.map(item => [item.link, item]));
    document.querySelectorAll('.save-button').forEach(button => {
      const item = map.get(button.dataset.url);
      const saved = Boolean(item);
      button.classList.toggle('is-saved', saved);
      button.setAttribute('aria-pressed', String(saved));
      const label = button.querySelector('.save-label');
      if (label) label.textContent = saved ? (item.note.trim() ? '메모 보기' : '메모 추가') : '저장';
    });
    document.querySelectorAll('[data-saved-count]').forEach(node => { node.textContent = String(savedItems.length); });
    const subtitle = byId('savedDrawerSubtitle');
    if (subtitle) subtitle.textContent = savedItems.length ? `${savedItems.length}개의 아티클을 모아두었어요.` : (currentUser ? '좋았던 아티클을 저장해보세요.' : '로그인 후 나만의 저장함을 만들어보세요.');
  }

  function shortAccountLabel(email) {
    const local = String(email || '').split('@')[0] || '내 계정';
    return local.length > 7 ? `${local.slice(0,7)}…` : local;
  }

  function updateAuthIndicators() {
    document.querySelectorAll('[data-auth-label]').forEach(node => { node.textContent = currentUser ? shortAccountLabel(currentUser.email) : '로그인'; });
    const syncTitle = byId('syncTitle');
    const syncText = byId('syncText');
    const syncAction = byId('syncAction');
    if (!syncTitle || !syncText || !syncAction) return;
    if (!authEnabled) {
      syncTitle.textContent = '로그인 연결이 필요해요';
      syncText.textContent = '운영자가 Supabase 설정을 연결해야 합니다.';
      syncAction.textContent = '안내';
    } else if (currentUser) {
      syncTitle.textContent = syncBusy ? '계정과 동기화 중…' : '계정에 동기화됨';
      syncText.textContent = currentUser.email || '로그인된 계정';
      syncAction.textContent = '내 계정';
    } else {
      syncTitle.textContent = '로그인 후 저장 가능';
      syncText.textContent = '저장한 기사와 메모를 여러 기기에서 이어볼 수 있어요.';
      syncAction.textContent = '로그인';
    }
  }

  function isVideo(item) {
    const type = String(item.contentType || '').toLowerCase();
    const link = String(item.link || '').toLowerCase();
    return type.includes('영상') || type.includes('video') || link.includes('youtube.com') || link.includes('youtu.be');
  }

  function fillThumbnail(container, item) {
    if (!container) return;
    const preservedLabel = container.querySelector('.media-label');
    container.replaceChildren();
    container.classList.add('noimg');
    container.classList.toggle('is-video', isVideo(item));
    container.dataset.initial = (item.source || 'S').slice(0,1);
    container.style.setProperty('--fallback', item.fallbackA || '#2d4a74');
    container.style.setProperty('--fallback-2', item.fallbackB || '#7699c8');
    if (item.image) {
      const image = new Image();
      image.alt = '';
      image.loading = 'lazy';
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('load', () => container.classList.remove('noimg'), {once:true});
      image.addEventListener('error', () => image.remove(), {once:true});
      image.src = item.image;
      container.append(image);
    }
    if (isVideo(item)) {
      const play = document.createElement('span');
      play.className = 'play-triangle';
      play.setAttribute('aria-hidden','true');
      container.append(play);
    }
    if (preservedLabel) container.append(preservedLabel);
  }

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderSaved() {
    const list = byId('savedList');
    if (!list) return;
    list.replaceChildren();
    updateSavedIndicators();
    updateAuthIndicators();
    if (!storageAvailable) {
      list.append(createElement('p','saved-empty','현재 브라우저의 저장 공간을 사용할 수 없어요.'));
      return;
    }
    if (!savedItems.length) {
      list.append(createElement('p','saved-empty',currentUser ? '아직 저장한 기사가 없어요.' : '저장함은 로그인 후 사용할 수 있어요.'));
      return;
    }
    const query = savedSearchQuery.trim().toLowerCase();
    const visibleItems = savedItems.filter(item => !query || [item.title,item.source,item.category,item.note,...item.tags].join(' ').toLowerCase().includes(query));
    const searchStatus = byId('savedSearchStatus');
    if (searchStatus) searchStatus.textContent = query ? `${visibleItems.length}개 검색됨` : `${savedItems.length}개 저장됨`;
    if (!visibleItems.length) {
      list.append(createElement('p','saved-empty','검색 조건에 맞는 저장 기사가 없어요.'));
      return;
    }
    visibleItems.forEach(item => {
      const article = createElement('article','saved-item');
      const preview = createElement('button','saved-preview-trigger');
      preview.type = 'button';
      preview.dataset.previewUrl = item.link;
      preview.setAttribute('aria-label',`${item.title || '저장한 기사'} 상세 보기`);
      const thumb = createElement('span','saved-thumb');
      fillThumbnail(thumb,item);
      const copy = createElement('span','saved-copy');
      copy.append(createElement('span','saved-meta',[item.briefingDate,item.source].filter(Boolean).join(' · ')),createElement('span','saved-title',item.title || '제목 없음'));
      if (item.tags.length) {
        const tags = createElement('span','saved-tags');
        item.tags.forEach(value => tags.append(createElement('span','saved-tag',`#${value}`)));
        copy.append(tags);
      }
      if (item.note.trim()) {
        const note = createElement('span','saved-note-preview');
        const strong = createElement('strong','', 'MY NOTE · ');
        note.append(strong,document.createTextNode(item.note.trim()));
        copy.append(note);
      }
      copy.append(createElement('span','saved-open-hint','카드로 다시 보기 →'));
      preview.append(thumb,copy);
      const actions = createElement('div','saved-actions');
      const detail = createElement('button','saved-action-button','상세 보기'); detail.type='button'; detail.dataset.previewUrl=item.link;
      const edit = createElement('button','saved-action-button',item.note.trim()?'메모 수정':'메모 추가'); edit.type='button'; edit.dataset.editNoteUrl=item.link;
      const remove = createElement('button','saved-action-button','삭제'); remove.type='button'; remove.dataset.removeUrl=item.link;
      actions.append(detail,edit,remove);
      article.append(preview,actions);
      list.append(article);
    });
  }

  const MIXPANEL_EVENT_MAP = {
    article_click:'article_opened',
    article_saved:'article_saved',
    article_unsaved:'article_unsaved',
    saved_drawer_open:'saved_drawer_opened',
    saved_detail_open:'saved_detail_opened',
    save_login_prompt:'login_prompt_shown',
    saved_login_prompt:'login_prompt_shown',
    auth_signup:'signup_completed',
    auth_login:'login_completed',
    password_reset_requested:'password_reset_requested',
    article_reported:'article_reported',
    briefing_feedback:'feedback_submitted',
    archive_open:'archive_opened',
  };

  async function trackEvent(eventName, article = null, metadata = {}, mixpanelEventName = undefined) {
    const mappedName = mixpanelEventName === undefined ? MIXPANEL_EVENT_MAP[eventName] : mixpanelEventName;
    if (mappedName) {
      captureMixpanelEvent(mappedName, article, metadata);
      if (mappedName === 'article_opened' || mappedName === 'article_saved') {
        markMeaningfulRead(mappedName, article, metadata);
      }
    }
    if (!supabaseClient || !authEnabled || analyticsOptedOut()) return;
    const payload = {
      event_name: eventName,
      session_id: anonymousSession(),
      briefing_date: pageConfig.briefingDate || '',
      page_context: pageConfig.context || 'home',
      article_url: article?.link || '',
      article_title: article?.title || '',
      article_source: article?.source || '',
      metadata,
    };
    try {
      const {error} = await supabaseClient.from('briefing_events').insert(payload);
      if (error) console.debug('analytics skipped', error.message);
    } catch (error) { console.debug('analytics skipped'); }
  }


  function requestLogin(intent, {saveUrl='',openSaved=false}={}) {
    pendingSaveUrl = saveUrl;
    pendingOpenSaved = openSaved;
    setAuthMode('login');
    byId('authIntent').textContent = intent;
    byId('authIntent').hidden = !intent;
    openAuthDialog();
  }

  function openDrawer() {
    if (!currentUser) {
      requestLogin('저장함은 로그인 후 사용할 수 있어요. 로그인하면 저장한 기사와 메모를 여러 기기에서 이어볼 수 있습니다.',{openSaved:true});
      void trackEvent('saved_login_prompt', null, {reason:'saved_drawer'});
      return;
    }
    renderSaved();
    openOverlay(drawer);
    void trackEvent('saved_drawer_open');
  }

  function openNote(url) {
    if (!currentUser) {
      requestLogin('기사를 저장하려면 먼저 로그인해 주세요. 로그인 후 스크랩 메모 화면으로 이어집니다.',{saveUrl:url});
      void trackEvent('save_login_prompt', currentByUrl.get(url), {reason:'save'});
      return;
    }
    const item = itemForUrl(url);
    if (!item) return;
    const existing = savedItems.find(entry => entry.link === url);
    activeNoteUrl = url;
    byId('noteArticleTitle').textContent = item.title || '제목 없음';
    byId('noteInput').value = existing?.note || '';
    byId('noteTagsInput').value = (existing?.tags || []).join(', ');
    byId('noteSaveButton').textContent = existing ? '메모 저장' : '스크랩 저장';
    updateNoteCount();
    openOverlay(noteDialog);
  }

  function updateNoteCount() { byId('noteCount').textContent = String(byId('noteInput').value.length); }

  function remoteRowToItem(row) {
    return normalizeItem({
      title:row.title,link:row.article_url,source:row.source,summary:row.summary,takeaway:row.takeaway,
      category:row.category,contentType:row.content_type,published:row.published,briefingDate:row.briefing_date,
      briefingSlug:row.briefing_slug,image:row.thumbnail_url,fallbackA:row.fallback_a,fallbackB:row.fallback_b,
      note:row.note,tags:row.tags || [],savedAt:row.saved_at,updatedAt:row.updated_at,pendingSync:false,
    });
  }

  function itemToRemote(item) {
    return {
      user_id:currentUser.id,article_url:item.link,title:item.title || '제목 없음',source:item.source || '기타',
      summary:item.summary || '',takeaway:item.takeaway || '',category:item.category || '생태계 업데이트',
      content_type:item.contentType || '기사',published:item.published || '',briefing_date:item.briefingDate || '',
      briefing_slug:item.briefingSlug || '',thumbnail_url:item.image || '',fallback_a:item.fallbackA || '#2d4a74',
      fallback_b:item.fallbackB || '#7699c8',note:item.note || '',tags:item.tags || [],saved_at:item.savedAt || new Date().toISOString(),
      updated_at:item.updatedAt || new Date().toISOString(),
    };
  }

  async function upsertCloud(items) {
    if (!supabaseClient || !currentUser || !items.length) return true;
    const {error} = await supabaseClient.from('saved_articles').upsert(items.map(itemToRemote),{onConflict:'user_id,article_url'});
    if (error) { console.error(error); return false; }
    return true;
  }

  async function syncSavedFromCloud() {
    if (!supabaseClient || !currentUser || syncBusy) return;
    syncBusy = true; updateAuthIndicators();
    const userKey = activeStorageKey();
    const local = readStorage(userKey);
    const guest = readStorage(GUEST_STORAGE_KEY);
    const {data,error} = await supabaseClient.from('saved_articles').select('*').eq('user_id',currentUser.id).order('saved_at',{ascending:false});
    if (error) {
      savedItems = dedupeItems([local,guest]);
      syncBusy = false; updateAuthIndicators(); renderSaved(); announce('계정 저장함을 불러오지 못했어요.'); return;
    }
    savedItems = dedupeItems([(data || []).map(remoteRowToItem),local,guest]).map(item => ({...item,pendingSync:true}));
    writeStorage(userKey,savedItems);
    const uploaded = await upsertCloud(savedItems);
    if (uploaded) {
      savedItems = savedItems.map(item => ({...item,pendingSync:false}));
      writeStorage(userKey,savedItems); clearStorage(GUEST_STORAGE_KEY);
    }
    syncBusy = false; updateAuthIndicators(); renderSaved();
  }

  async function saveNote() {
    if (!activeNoteUrl || !currentUser) return;
    const current = currentByUrl.get(activeNoteUrl);
    const index = savedItems.findIndex(item => item.link === activeNoteUrl);
    const existing = index >= 0 ? savedItems[index] : null;
    const base = current || existing;
    if (!base) return;
    const now = new Date().toISOString();
    const item = normalizeItem({...existing,...current,note:byId('noteInput').value.trim(),tags:normalizeTags(byId('noteTagsInput').value),savedAt:existing?.savedAt || now,updatedAt:now,pendingSync:true});
    if (index >= 0) savedItems.splice(index,1);
    savedItems.unshift(item); savedItems = dedupeItems([savedItems]);
    if (!persistActive()) { announce('이 브라우저에서는 저장할 수 없어요.'); return; }
    closeOverlay(noteDialog); activeNoteUrl=''; updateSavedIndicators(); renderSaved();
    const uploaded = await upsertCloud([item]);
    if (uploaded) {
      const saved = savedItems.find(row => row.link === item.link); if (saved) saved.pendingSync=false; persistActive();
      announce(item.note ? '메모와 함께 저장했어요.' : '기사를 저장했어요.');
      void trackEvent('article_saved',item,{has_note:Boolean(item.note),tag_count:item.tags.length});
    } else announce('기기에는 저장했지만 계정 동기화에 실패했어요.');
  }

  async function removeSaved(url) {
    const item = savedItems.find(row => row.link === url);
    savedItems = savedItems.filter(row => row.link !== url); persistActive(); updateSavedIndicators(); renderSaved();
    closeOverlay(previewDialog,false);
    if (currentUser && supabaseClient) await supabaseClient.from('saved_articles').delete().eq('user_id',currentUser.id).eq('article_url',url);
    announce('저장함에서 삭제했어요.');
    void trackEvent('article_unsaved',item);
  }

  function renderPreview(item) {
    fillThumbnail(byId('previewThumb'),item);
    byId('previewMediaLabel').textContent=item.contentType || '기사';
    byId('previewCategory').textContent=item.category || '생태계 업데이트';
    byId('previewSource').textContent=item.source || '기타';
    byId('previewTitle').textContent=item.title || '제목 없음';
    byId('previewSummary').textContent=item.summary || '';
    byId('previewTakeaway').textContent=item.takeaway || '';
    byId('previewFacts').textContent=[item.published,item.briefingDate].filter(Boolean).join(' · ');
    const noteWrap=byId('previewNoteWrap'); noteWrap.hidden=!item.note.trim(); byId('previewNote').textContent=item.note.trim();
    const tagWrap=byId('previewTags'); tagWrap.replaceChildren(); item.tags.forEach(value=>tagWrap.append(createElement('span','preview-tag',`#${value}`))); tagWrap.hidden=!item.tags.length;
    byId('previewReadLink').href=item.link; byId('previewEditButton').dataset.editNoteUrl=item.link; byId('previewDeleteButton').dataset.removeUrl=item.link;
  }

  function openPreview(url) {
    const item=itemForUrl(url); if(!item)return; activePreviewUrl=url; renderPreview(item); openOverlay(previewDialog); void trackEvent('saved_detail_open',item);
  }

  function setAuthMode(mode) {
    authMode = ['signup','login'].includes(mode) ? mode : 'login';
    recoveryMode = false;
    byId('authRecoveryView').hidden=true; byId('authGuestView').hidden=false;
    document.querySelectorAll('[data-auth-mode]').forEach(button=>{const active=button.dataset.authMode===authMode;button.classList.toggle('is-active',active);button.setAttribute('aria-selected',String(active));});
    byId('authSubmit').textContent=authMode==='signup'?'회원가입':'로그인';
    byId('authPassword').autocomplete=authMode==='signup'?'new-password':'current-password';
    setAuthMessage('');
  }

  function setAuthMessage(message,error=false){const node=byId('authMessage');node.textContent=message;node.classList.toggle('is-error',error);}
  function redirectUrl(){return authConfig.redirectUrl || new URL(authConfig.homeHref || './',window.location.href).href;}

  function updateAuthView() {
    byId('authSetupView').hidden=authEnabled;
    byId('authGuestView').hidden=!authEnabled||Boolean(currentUser)||recoveryMode;
    byId('authUserView').hidden=!authEnabled||!currentUser||recoveryMode;
    byId('authRecoveryView').hidden=!recoveryMode;
    byId('accountEmail').textContent=currentUser?.email || '';
  }

  function openAuthDialog(){updateAuthView();openOverlay(authDialog);}

  async function handleAuthSubmit(event){
    event.preventDefault(); if(!supabaseClient)return;
    const email=byId('authEmail').value.trim(); const password=byId('authPassword').value;
    if(!email||!password){setAuthMessage('이메일과 비밀번호를 모두 입력해 주세요.',true);return;}
    if(password.length<8){setAuthMessage('비밀번호는 8자 이상이어야 합니다.',true);return;}
    const button=byId('authSubmit');button.disabled=true;
    try{
      if(authMode==='signup'){
        const {data,error}=await supabaseClient.auth.signUp({email,password});if(error)throw error;
        if(!data?.session){
          setAuthMessage('회원가입은 완료됐지만 바로 로그인되지 않았어요. 운영자에게 알려주세요.',true);
          return;
        }
        setAuthMessage('회원가입과 로그인이 완료됐어요.');
        closeOverlay(authDialog,true);
        void trackEvent('auth_signup');
      }else{
        const {error}=await supabaseClient.auth.signInWithPassword({email,password});if(error)throw error;
        setAuthMessage('로그인했어요. 저장함을 동기화합니다.');closeOverlay(authDialog,true);void trackEvent('auth_login');
      }
    }catch(error){setAuthMessage(error?.message||'로그인 처리 중 오류가 발생했어요.',true);}finally{button.disabled=false;}
  }

  async function requestPasswordReset(){
    if(!supabaseClient)return; const email=byId('authEmail').value.trim();
    if(!email){setAuthMessage('비밀번호를 재설정할 이메일을 입력해 주세요.',true);return;}
    try{const {error}=await supabaseClient.auth.resetPasswordForEmail(email,{redirectTo:redirectUrl()});if(error)throw error;setAuthMessage('비밀번호 재설정 메일을 보냈어요. 메일의 링크를 눌러 주세요.');void trackEvent('password_reset_requested');}
    catch(error){setAuthMessage(error?.message||'재설정 메일을 보내지 못했어요.',true);}
  }

  async function updatePassword(event){
    event.preventDefault(); if(!supabaseClient)return; const password=byId('newPassword').value; const confirm=byId('newPasswordConfirm').value;
    if(password.length<8){byId('recoveryMessage').textContent='비밀번호는 8자 이상이어야 합니다.';return;}
    if(password!==confirm){byId('recoveryMessage').textContent='두 비밀번호가 일치하지 않습니다.';return;}
    const {error}=await supabaseClient.auth.updateUser({password});
    if(error){byId('recoveryMessage').textContent=error.message;return;}
    byId('recoveryMessage').textContent='비밀번호를 변경했어요. 다시 로그인해 주세요.'; await supabaseClient.auth.signOut(); recoveryMode=false;setAuthMode('login');updateAuthView();
  }

  async function handleSignOut(){if(!supabaseClient)return;await supabaseClient.auth.signOut();closeOverlay(authDialog);announce('로그아웃했어요.');}

  async function applySession(session){
    const previous=currentUser?.id||''; currentUser=session?.user||null; updateAuthView(); updateAuthIndicators();
    if(currentUser){
      identifyMixpanelUser(currentUser);
      if(previous!==currentUser.id||!savedItems.length)await syncSavedFromCloud();
      const saveUrl=pendingSaveUrl;const openSaved=pendingOpenSaved;pendingSaveUrl='';pendingOpenSaved=false;
      if(saveUrl)window.setTimeout(()=>openNote(saveUrl),30);else if(openSaved)window.setTimeout(openDrawer,30);
    }
    else{
      if(previous)resetMixpanelUser();
      else if(mixpanelEnabled && window.mixpanel && !analyticsOptedOut())window.mixpanel.register({is_logged_in:false});
      savedItems=[];updateSavedIndicators();renderSaved();
    }
  }

  function persistentAuthStorage(){
    try{
      const key='snaac-auth-storage-check';
      window.localStorage.setItem(key,'1');
      window.localStorage.removeItem(key);
      return window.localStorage;
    }catch(error){
      console.warn('로그인 상태를 브라우저에 저장할 수 없습니다.',error);
      return undefined;
    }
  }

  async function restoreSession(){
    if(!supabaseClient)return;
    const {data,error}=await supabaseClient.auth.getSession();
    if(error){console.warn('저장된 로그인 상태를 불러오지 못했습니다.',error);return;}
    await applySession(data?.session||null);
  }

  async function initSupabase(){
    updateAuthView();updateAuthIndicators();if(!authEnabled)return;
    if(!window.supabase?.createClient){console.error('Supabase library failed to load');return;}

    const authOptions={
      persistSession:true,
      autoRefreshToken:true,
      detectSessionInUrl:true
    };
    const storage=persistentAuthStorage();
    if(storage)authOptions.storage=storage;

    supabaseClient=window.supabase.createClient(
      authConfig.url,
      authConfig.publishableKey,
      {auth:authOptions}
    );

    await restoreSession();
    supabaseClient.auth.onAuthStateChange((event,session)=>{
      if(event==='PASSWORD_RECOVERY'){
        recoveryMode=true;
        openAuthDialog();
        updateAuthView();
      }
      window.setTimeout(()=>void applySession(session),0);
    });

    document.addEventListener('visibilitychange',()=>{
      if(document.visibilityState==='visible')window.setTimeout(()=>void restoreSession(),0);
    });

    void trackEvent('page_view', null, {}, null);
  }

  function openReport(url){const item=itemForUrl(url);if(!item)return;activeReportUrl=url;byId('reportArticleTitle').textContent=item.title;byId('reportForm').reset();byId('reportMessage').textContent='';openOverlay(reportDialog);}
  async function submitReport(event){
    event.preventDefault();if(!supabaseClient){byId('reportMessage').textContent='신고 접수 기능이 아직 연결되지 않았어요.';return;}
    const item=itemForUrl(activeReportUrl);const reason=new FormData(event.currentTarget).get('reason');if(!reason){byId('reportMessage').textContent='문제 유형을 선택해 주세요.';return;}
    const detail=byId('reportDetail').value.trim();const {error}=await supabaseClient.from('article_reports').insert({session_id:anonymousSession(),user_id:currentUser?.id||null,briefing_date:pageConfig.briefingDate||'',article_url:item?.link||activeReportUrl,article_title:item?.title||'',article_source:item?.source||'',reason,detail});
    if(error){byId('reportMessage').textContent=error.code==='23505'?'같은 문제는 이미 접수했어요. 운영팀이 확인할게요.':'접수하지 못했어요. 잠시 후 다시 시도해 주세요.';return;}
    byId('reportMessage').textContent='알려줘서 고마워요. 운영팀이 확인할게요.';void trackEvent('article_reported',item,{reason});window.setTimeout(()=>closeOverlay(reportDialog),900);
  }

  async function submitFeedback(helpful,button){
    document.querySelectorAll('.feedback-button').forEach(node=>node.classList.remove('is-selected'));button.classList.add('is-selected');
    const thanks=byId('feedbackThanks');thanks.hidden=false;thanks.textContent='피드백 고마워요!';
    if(supabaseClient){
      const {error}=await supabaseClient.from('briefing_feedback').insert({session_id:anonymousSession(),briefing_date:pageConfig.briefingDate||'',page_context:pageConfig.context||'home',helpful});
      if(error?.code==='23505'){thanks.textContent='이 회차에는 이미 피드백을 남겼어요.';return;}
      if(error){thanks.textContent='피드백을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.';return;}
    }
    void trackEvent('briefing_feedback',null,{helpful,feedback_value:helpful?'helpful':'needs_work'});
  }

  async function deleteAccount(){
    if(!supabaseClient||!currentUser)return;
    const expected=(currentUser.email||'').toLowerCase();
    const typed=byId('deleteConfirmEmail').value.trim().toLowerCase();
    const password=byId('deleteConfirmPassword').value;
    if(typed!==expected){byId('deleteMessage').textContent='로그인한 이메일 주소를 정확히 입력해 주세요.';return;}
    if(!password){byId('deleteMessage').textContent='현재 비밀번호를 입력해 주세요.';return;}
    byId('deleteAccountButton').disabled=true;byId('deleteMessage').textContent='본인 확인 중…';
    try{
      const {error:reauthError}=await supabaseClient.auth.signInWithPassword({email:expected,password});
      if(reauthError){byId('deleteMessage').textContent='비밀번호가 맞지 않아요.';return;}
      byId('deleteMessage').textContent='계정을 삭제하고 있어요…';
      const {error}=await supabaseClient.functions.invoke(authConfig.deleteAccountFunction||'delete-account',{body:{confirm:true}});if(error)throw error;
      clearStorage(activeStorageKey());savedItems=[];resetMixpanelUser();await supabaseClient.auth.signOut({scope:'local'});byId('deleteMessage').textContent='계정과 저장 데이터가 삭제됐어요.';window.setTimeout(()=>{closeOverlay(deleteDialog,false);closeOverlay(authDialog,false);},700);
    }catch(error){
      const {error:requestError}=await supabaseClient.from('account_deletion_requests').insert({user_id:currentUser.id,email:currentUser.email||'',status:'requested'});
      const alreadyRequested = requestError && requestError.code === '23505';
      byId('deleteMessage').textContent=(!requestError || alreadyRequested)?'자동 삭제에 실패해 탈퇴 요청을 접수했어요. 운영팀이 확인할게요.':'자동 삭제에 실패했어요. 운영팀에 문의해 주세요.';
    }finally{byId('deleteAccountButton').disabled=false;}
  }

  function filterArchive(){const query=byId('archiveSearch')?.value.trim().toLowerCase()||'';let visible=0;document.querySelectorAll('[data-archive-search]').forEach(row=>{const show=!query||row.dataset.archiveSearch.includes(query);row.hidden=!show;if(show)visible+=1;});const empty=byId('archiveNoResult');if(empty)empty.hidden=visible>0;}

  document.addEventListener('click',event=>{
    const save=event.target.closest('.save-button');if(save){const item=currentByUrl.get(save.dataset.url);const position=articlePositionFromElement(save);captureMixpanelEvent('save_clicked',item,{position,is_logged_in:Boolean(currentUser)});openNote(save.dataset.url);return;}
    const openSaved=event.target.closest('[data-open-saved]');if(openSaved){openDrawer();return;}
    const close=event.target.closest('[data-close-overlay]');if(close){closeOverlay(byId(close.dataset.closeOverlay));return;}
    const preview=event.target.closest('[data-preview-url]');if(preview){openPreview(preview.dataset.previewUrl);return;}
    const edit=event.target.closest('[data-edit-note-url]');if(edit){closeOverlay(previewDialog,false);openNote(edit.dataset.editNoteUrl);return;}
    const remove=event.target.closest('[data-remove-url]');if(remove){void removeSaved(remove.dataset.removeUrl);return;}
    const auth=event.target.closest('[data-open-auth]');if(auth){openAuthDialog();return;}
    const mode=event.target.closest('[data-auth-mode]');if(mode){setAuthMode(mode.dataset.authMode);return;}
    if(event.target.closest('[data-logout]')){void handleSignOut();return;}
    if(event.target.closest('[data-forgot-password]')){void requestPasswordReset();return;}
    const report=event.target.closest('[data-report-url]');if(report){openReport(report.dataset.reportUrl);return;}
    const feedback=event.target.closest('[data-feedback]');if(feedback){void submitFeedback(feedback.dataset.feedback==='yes',feedback);return;}
    if(event.target.closest('[data-open-privacy]')){updateAnalyticsPreferenceUi();openOverlay(privacyDialog);return;}
    if(event.target.closest('[data-toggle-analytics]')){toggleAnalyticsPreference();return;}
    if(event.target.closest('[data-open-delete]')){byId('deleteConfirmEmail').value='';byId('deleteConfirmPassword').value='';byId('deleteMessage').textContent='';openOverlay(deleteDialog);return;}
    if(event.target.closest('[data-delete-account]')){void deleteAccount();return;}
    const articleLink=event.target.closest('[data-article-link]');if(articleLink){const item=currentByUrl.get(articleLink.dataset.articleLink);void trackEvent('article_click',item,{position:articlePositionFromElement(articleLink),link_area:articleLink.classList.contains('read-link')?'button':articleLink.classList.contains('thumb')?'thumbnail':'title'});}
    const archiveLink=event.target.closest('[data-archive-link]');if(archiveLink){void trackEvent('archive_open',null,{slug:archiveLink.dataset.archiveLink});return;}
  });

  document.addEventListener('keydown',event=>{
    const opened=allOverlays.find(isOpen);if(opened)trapFocus(event,opened);
    if(event.key==='Escape'&&opened)closeOverlay(opened);
  });

  byId('noteInput')?.addEventListener('input',updateNoteCount);
  byId('savedSearch')?.addEventListener('input',event=>{savedSearchQuery=event.target.value;renderSaved();});
  byId('noteInput')?.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key==='Enter'){event.preventDefault();void saveNote();}});
  byId('noteSaveButton')?.addEventListener('click',()=>void saveNote());
  byId('authForm')?.addEventListener('submit',event=>void handleAuthSubmit(event));
  byId('recoveryForm')?.addEventListener('submit',event=>void updatePassword(event));
  byId('reportForm')?.addEventListener('submit',event=>void submitReport(event));
  const archiveSearch=byId('archiveSearch');
  let archiveSearchUserTyped=false;
  function clearArchiveAutofill(){
    if(!archiveSearch||archiveSearchUserTyped)return;
    if(archiveSearch.value){archiveSearch.value='';filterArchive();}
  }
  function activateArchiveSearch(event){
    if(!archiveSearch||!archiveSearch.hasAttribute('readonly'))return;
    if(event?.type==='pointerdown')event.preventDefault();
    archiveSearch.removeAttribute('readonly');
    archiveSearch.value='';
    window.setTimeout(()=>archiveSearch.focus({preventScroll:true}),0);
  }
  archiveSearch?.addEventListener('pointerdown',activateArchiveSearch);
  archiveSearch?.addEventListener('keydown',event=>{
    activateArchiveSearch(event);
    archiveSearchUserTyped=true;
  });
  archiveSearch?.addEventListener('input',event=>{
    if(event.isTrusted)archiveSearchUserTyped=true;
    filterArchive();
    window.clearTimeout(archiveSearchTimer);
    const queryLength=archiveSearch.value.trim().length;
    if(queryLength>=2){
      archiveSearchTimer=window.setTimeout(()=>{
        const resultCount=document.querySelectorAll('[data-archive-search]:not([hidden])').length;
        captureMixpanelEvent('archive_search_used',null,{query_length:queryLength,result_count:resultCount});
      },700);
    }
  });
  archiveSearch?.addEventListener('focus',()=>{
    [0,100,300].forEach(delay=>window.setTimeout(clearArchiveAutofill,delay));
  });
  byId('previewReadLink')?.addEventListener('click',()=>void trackEvent('article_click',itemForUrl(activePreviewUrl),{from:'saved_preview',link_area:'saved_preview'}));

  window.addEventListener('storage',()=>{savedItems=readStorage(activeStorageKey());updateSavedIndicators();renderSaved();});
  window.addEventListener('pageshow',()=>{
    archiveSearchUserTyped=false;
    [0,120,500,1000].forEach(delay=>window.setTimeout(clearArchiveAutofill,delay));
  });
  updateFreshness();updateAnalyticsPreferenceUi();setAuthMode('login');updateSavedIndicators();renderSaved();initializeProductAnalytics();void initSupabase();
})();
"""


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
    youtube_image = _youtube_thumbnail(url)
    if youtube_image:
        return youtube_image
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SNAACBriefingBot/6.0)",
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
            if match:
                image_url = urljoin(response.url or url, html.unescape(match.group(1).strip()))
                public_url = _public_image_url(image_url)
                if public_url:
                    return public_url
    except requests.RequestException as exc:
        print(f"[썸네일 스킵] {url}: {exc}")
    return None


def _source_gradient(source: str) -> tuple[str, str]:
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
    slug: str,
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
            "briefing_slug": slug,
            "quality_score": int(pick.get("quality_score", 0) or 0),
            "quality_reason": str(pick.get("quality_reason", "")).strip(),
        }
        fallback_a, fallback_b = _source_gradient(item["source"])
        item["fallback_a"] = fallback_a
        item["fallback_b"] = fallback_b
        supplied = _public_image_url(pick.get("image") or pick.get("thumbnail"))
        hinted = _public_image_url(hints.get(item["link"]))
        image = supplied or hinted or _youtube_thumbnail(item["link"])
        if not image and SHOW_THUMBNAILS and fetch_missing_images:
            image = fetch_og_image(item["link"])
        item["image"] = image
        prepared.append(item)
    return prepared


def _bookmark_icon() -> str:
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 4.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16l-5.5-3.2-5.5 3.2z"/></svg>'


def _is_video_pick(pick: dict) -> bool:
    content_type = str(pick.get("content_type", "")).lower()
    return "영상" in content_type or "video" in content_type or _youtube_video_id(str(pick.get("link", ""))) is not None


def _format_published(value: str) -> str:
    if not value or value == "unknown":
        return "발행일 미표기"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        parsed = parsed.astimezone(KST)
        return f"{parsed.month}월 {parsed.day}일 발행"
    except ValueError:
        return html.escape(value[:20])


def _card(index: int, total: int, pick: dict) -> str:
    title = html.escape(pick["title"])
    summary = html.escape(pick["summary"])
    takeaway = html.escape(pick["takeaway"] or "원문에서 이번 변화가 스타트업과 창업가에게 주는 의미를 확인해보세요.")
    source = html.escape(pick["source"])
    category = html.escape(pick["category"])
    content_type = html.escape(pick["content_type"])
    published = html.escape(_format_published(pick.get("published", "unknown")))
    link = html.escape(pick["link"], quote=True)
    initial = html.escape((pick["source"] or "S")[0])
    fallback_a = html.escape(pick.get("fallback_a", "#2d4a74"), quote=True)
    fallback_b = html.escape(pick.get("fallback_b", "#7699c8"), quote=True)
    thumb_classes = "thumb"
    thumb_inner = ""
    if pick.get("image"):
        image = html.escape(str(pick["image"]), quote=True)
        thumb_inner = f'<img src="{image}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.parentElement.classList.add(\'noimg\');this.remove()">'
    else:
        thumb_classes += " noimg"
    if _is_video_pick(pick):
        thumb_classes += " is-video"
        thumb_inner += '<span class="play-triangle" aria-hidden="true"></span>'
    return f"""
<article class="card" data-category="{category}" data-original-index="{index}" data-article-card data-article-url="{link}" data-article-position="{index}">
  <a class="{thumb_classes}" href="{link}" target="_blank" rel="noopener noreferrer" data-article-link="{link}" data-initial="{initial}" style="--fallback:{fallback_a};--fallback-2:{fallback_b}" aria-label="{title} 원문 열기">
    {thumb_inner}<span class="media-label">{content_type}</span>
  </a>
  <div class="card-body">
    <div class="card-meta"><div class="meta-left"><span class="category">{category}</span><span class="source">{source}</span></div><span class="card-index">{index:02d}/{total:02d}</span></div>
    <a class="title-link" href="{link}" target="_blank" rel="noopener noreferrer" data-article-link="{link}"><h2>{title}</h2></a>
    <p class="summary">{summary}</p>
    <div class="article-facts"><span>{published}</span><span>{content_type}</span></div>
    <div class="takeaway"><span class="takeaway-label">WHY IT MATTERS</span><p>{takeaway}</p></div>
    <div class="card-actions">
      <a class="read-link" href="{link}" target="_blank" rel="noopener noreferrer" data-article-link="{link}">원문 읽기</a>
      <button class="save-button" type="button" data-url="{link}" aria-pressed="false">{_bookmark_icon()}<span class="save-label">저장</span></button>
      <button class="report-button" type="button" data-report-url="{link}" aria-label="이 원문 문제 신고">!</button>
    </div>
  </div>
</article>"""


def _archive_entries(exclude_slug: str | None = None) -> list[dict]:
    archive_dir = DOCS_DIR / "archive"
    if not archive_dir.exists():
        return []
    entries: list[dict] = []
    for path in sorted(archive_dir.glob("????-??-??.html"), reverse=True):
        slug = path.stem
        if slug == exclude_slug:
            continue
        try:
            date = datetime.strptime(slug, "%Y-%m-%d")
        except ValueError:
            continue
        count = 0
        titles: list[str] = []
        sources: list[str] = []
        json_path = archive_dir / f"{slug}.json"
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                picks = data.get("picks", [])
                count = len(picks)
                titles = [str(item.get("title", "")) for item in picks]
                sources = [str(item.get("source", "")) for item in picks]
            except (OSError, json.JSONDecodeError):
                pass
        entries.append({
            "slug": slug,
            "label": f"{date.month}월 {date.day}일",
            "full_label": f"{date.year}년 {date.month}월 {date.day}일 {WEEKDAYS[date.weekday()]}요일",
            "month_label": f"{date.year}년 {date.month}월",
            "count": count or 5,
            "search": " ".join([slug, *titles, *sources]).lower(),
            "date": date,
        })
    return entries


def _archive_rows(entries: list[dict], prefix: str = "", searchable: bool = False) -> str:
    if not entries:
        return '<p class="empty-archive">지난 브리핑이 쌓이면 이곳에서 다시 볼 수 있어요.</p>'
    rows: list[str] = []
    previous_month = ""
    for entry in entries:
        if searchable and entry["month_label"] != previous_month:
            previous_month = entry["month_label"]
            rows.append(f'<p class="archive-month-label">{html.escape(previous_month)}</p>')
        search_attr = f' data-archive-search="{html.escape(entry["search"], quote=True)}"' if searchable else ""
        rows.append(
            f'<a class="archive-row" href="{prefix}{entry["slug"]}.html" data-archive-link="{entry["slug"]}"{search_attr}>'
            f'<span class="archive-date">{html.escape(entry["full_label"] if searchable else entry["label"])}</span>'
            f'<span class="archive-count">{entry["count"]}개의 큐레이션</span><span class="archive-arrow" aria-hidden="true">→</span></a>'
        )
    return "".join(rows)


def _archive_section(today_slug: str, context: str) -> str:
    entries = _archive_entries(exclude_slug=today_slug)[:ARCHIVE_KEEP]
    prefix = "archive/" if context == "home" else ""
    index_href = "archive/" if context == "home" else "./"
    return f"""
<section class="archive-section" id="archive">
  <div class="section-head"><h2>지난 브리핑</h2><a href="{index_href}">전체 보기 →</a></div>
  <div class="archive-list">{_archive_rows(entries, prefix)}</div>
</section>"""


def _about_snaac_section() -> str:
    return f"""
<section class="about-snaac-section" aria-label="SNAAC 소개">
  <a class="about-snaac-card" href="{html.escape(ABOUT_URL, quote=True)}" target="_blank" rel="noopener noreferrer">
    <span class="about-snaac-eyebrow">ABOUT SNAAC</span><span class="about-snaac-title">SNAAC을 더 알아보세요</span>
    <span class="about-snaac-copy">대학 스타트업 동아리 SNAAC의 활동과 소식을 공식 홈페이지에서 확인할 수 있어요.</span>
  </a>
</section>"""


def _logo_html(context: str) -> str:
    asset_prefix = "" if context == "home" else "../"
    home_href = "./" if context == "home" else "../"
    return f'<div class="logo-row"><a class="logo-link" href="{home_href}" aria-label="SNAAC 오늘 브리핑"><img class="site-logo" src="{asset_prefix}assets/{LOGO_ASSET_NAME}" alt="SNAAC" width="932" height="232" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="logo-fallback" hidden>SNAAC</span></a></div>'


def _header_html(context: str) -> str:
    if context == "home":
        archive_href, left_label, symbol = "archive/", "지난 회차", "↺"
    else:
        archive_href, left_label, symbol = "../", "오늘", "←"
    return f"""
{_logo_html(context)}
<div class="topline">
  <a class="utility-button" href="{archive_href}"><span>{left_label}</span><span aria-hidden="true">{symbol}</span></a>
  <button class="utility-button saved-vault" type="button" data-open-saved>{_bookmark_icon()}<span>저장함</span><span class="count-badge" data-saved-count>0</span></button>
  <button class="utility-button auth-control" type="button" data-open-auth><span aria-hidden="true">◎</span><span data-auth-label>로그인</span></button>
</div>"""


def _freshness_html() -> str:
    return """
<section class="freshness" id="freshness" aria-live="polite">
  <span class="freshness-dot" aria-hidden="true"></span>
  <div><p class="freshness-title" id="freshnessTitle">업데이트 상태 확인 중</p><p class="freshness-copy" id="freshnessCopy">잠시만 기다려 주세요.</p></div>
</section>"""


def _overlays_html() -> str:
    if PRIVACY_CONTACT_EMAIL:
        safe_email = html.escape(PRIVACY_CONTACT_EMAIL)
        contact = f'<a href="mailto:{html.escape(PRIVACY_CONTACT_EMAIL, quote=True)}">{safe_email}</a>'
    else:
        contact = "SNAAC Community Team"
    return f"""
<button class="floating-saved" type="button" data-open-saved>{_bookmark_icon()}<span>내 저장함</span><span class="count-badge" data-saved-count>0</span></button>

<div class="overlay mp-no-track mp-sensitive" id="savedDrawer" hidden><button class="overlay-backdrop" type="button" data-close-overlay="savedDrawer" aria-label="저장함 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="savedTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="savedTitle">내 저장함</h2><p id="savedDrawerSubtitle">좋았던 아티클을 저장해보세요.</p></div><button class="close-button" type="button" data-close-overlay="savedDrawer" aria-label="닫기">×</button></div><div class="sync-strip"><div><p class="sync-title" id="syncTitle">계정 저장함</p><p class="sync-text" id="syncText">로그인 후 사용할 수 있어요.</p></div><button class="sync-action" id="syncAction" type="button" data-open-auth>로그인</button></div><div class="saved-tools"><label class="sr-only" for="savedSearch">저장함 검색</label><input class="saved-search" id="savedSearch" type="search" placeholder="제목, 메모, 태그로 검색"><p class="saved-search-status" id="savedSearchStatus"></p></div><div class="saved-list" id="savedList"></div></section></div>

<div class="overlay mp-no-track mp-sensitive" id="noteDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="noteDialog" aria-label="메모 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="noteTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="noteTitle">스크랩 메모</h2><p id="noteArticleTitle"></p></div><button class="close-button" type="button" data-close-overlay="noteDialog" aria-label="닫기">×</button></div><label class="form-label" for="noteInput"><span>이 기사를 저장한 이유 · 선택</span><span><span id="noteCount">0</span>/500</span></label><textarea class="form-textarea" id="noteInput" maxlength="500" placeholder="예: 다음 기획 회의에서 리텐션 사례로 다시 보기"></textarea><label class="form-label" for="noteTagsInput">태그 · 선택</label><input class="tag-input" id="noteTagsInput" maxlength="120" placeholder="예: PMF, 조직, VC"><p class="tag-hint">쉼표로 구분해 최대 5개까지 저장할 수 있어요.</p><p class="form-help">메모와 태그를 비워둔 채 기사만 저장해도 됩니다.</p><div class="form-actions"><button class="secondary-button" type="button" data-close-overlay="noteDialog">취소</button><button class="primary-button" id="noteSaveButton" type="button">스크랩 저장</button></div></section></div>

<div class="overlay mp-no-track mp-sensitive" id="previewDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="previewDialog" aria-label="상세 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="previewDialogTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="previewDialogTitle">저장한 아티클</h2><p id="previewFacts"></p></div><button class="close-button" type="button" data-close-overlay="previewDialog" aria-label="닫기">×</button></div><article class="preview-card"><div class="preview-thumb noimg" id="previewThumb" data-initial="S"><span class="media-label" id="previewMediaLabel">기사</span></div><div class="preview-body"><div class="card-meta"><div class="meta-left"><span class="category" id="previewCategory">생태계 업데이트</span><span class="source" id="previewSource">SNAAC</span></div></div><h3 id="previewTitle">저장한 기사</h3><p class="preview-summary" id="previewSummary"></p><div class="takeaway"><span class="takeaway-label">WHY IT MATTERS</span><p id="previewTakeaway"></p></div><div class="preview-note" id="previewNoteWrap" hidden><strong>MY NOTE</strong><span id="previewNote"></span></div><div class="preview-tags" id="previewTags" hidden></div><div class="preview-actions"><a class="preview-read" id="previewReadLink" href="#" target="_blank" rel="noopener noreferrer">원문 읽기 ↗</a><button class="preview-secondary" id="previewEditButton" type="button">메모 수정</button></div><button class="preview-delete" id="previewDeleteButton" type="button">저장함에서 삭제</button></div></article></section></div>

<div class="overlay mp-no-track mp-sensitive" id="authDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="authDialog" aria-label="계정 창 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="authTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="authTitle">SNAAC 계정</h2><p>저장함과 메모를 여러 기기에서 이어보세요.</p></div><button class="close-button" type="button" data-close-overlay="authDialog" aria-label="닫기">×</button></div>
<div id="authGuestView"><p class="auth-intent" id="authIntent" hidden></p><div class="auth-tabs" role="tablist"><button class="auth-tab is-active" type="button" data-auth-mode="login" aria-selected="true">로그인</button><button class="auth-tab" type="button" data-auth-mode="signup" aria-selected="false">회원가입</button></div><form id="authForm" autocomplete="on"><label class="form-label" for="authEmail">이메일</label><input class="form-input" id="authEmail" name="email" type="email" autocomplete="email" required placeholder="name@example.com"><label class="form-label" for="authPassword">비밀번호</label><input class="form-input" id="authPassword" name="password" type="password" minlength="8" autocomplete="current-password" required placeholder="8자 이상"><button class="primary-button" id="authSubmit" type="submit" style="width:100%;margin-top:12px">로그인</button><p class="auth-message" id="authMessage" aria-live="polite"></p><div class="auth-link-row"><button class="text-button" type="button" data-forgot-password>비밀번호를 잊었나요?</button></div></form></div>
<div id="authRecoveryView" hidden><form id="recoveryForm"><h3>새 비밀번호 설정</h3><label class="form-label" for="newPassword">새 비밀번호</label><input class="form-input" id="newPassword" type="password" minlength="8" autocomplete="new-password" required><label class="form-label" for="newPasswordConfirm">새 비밀번호 확인</label><input class="form-input" id="newPasswordConfirm" type="password" minlength="8" autocomplete="new-password" required><button class="primary-button" type="submit" style="width:100%;margin-top:13px">비밀번호 변경</button><p class="auth-message is-error" id="recoveryMessage" aria-live="polite"></p></form></div>
<div id="authUserView" hidden><div class="account-card"><p class="account-eyebrow">SIGNED IN AS</p><p class="account-email" id="accountEmail"></p><p class="account-copy">저장한 기사와 메모, 태그가 이 계정에 동기화됩니다.</p></div><div class="account-actions"><button class="account-action" type="button" data-open-privacy>개인정보 안내</button><button class="account-action" type="button" data-logout>로그아웃</button><button class="account-action is-danger" type="button" data-open-delete>회원 탈퇴</button></div></div>
<div id="authSetupView" hidden><div class="account-card"><p class="account-email">로그인 연결 전이에요</p><p class="account-copy">Supabase 공개 설정을 연결한 뒤 사용할 수 있습니다.</p></div></div></section></div>

<div class="overlay mp-no-track mp-sensitive" id="reportDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="reportDialog" aria-label="신고 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="reportTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="reportTitle">원문 문제 알리기</h2><p id="reportArticleTitle"></p></div><button class="close-button" type="button" data-close-overlay="reportDialog" aria-label="닫기">×</button></div><form id="reportForm"><div class="report-options"><label class="report-option"><input type="radio" name="reason" value="broken_link">원문이 열리지 않아요</label><label class="report-option"><input type="radio" name="reason" value="paywall">구독이나 로그인이 필요해요</label><label class="report-option"><input type="radio" name="reason" value="summary_mismatch">요약이 원문과 달라요</label><label class="report-option"><input type="radio" name="reason" value="other">기타 문제</label></div><label class="form-label" for="reportDetail">추가 설명 · 선택</label><textarea class="form-textarea" id="reportDetail" maxlength="500"></textarea><button class="primary-button" type="submit" style="width:100%;margin-top:12px">운영팀에 알리기</button><p class="auth-message" id="reportMessage" aria-live="polite"></p></form></section></div>

<div class="overlay mp-no-track mp-sensitive" id="privacyDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="privacyDialog" aria-label="개인정보 안내 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="privacyTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="privacyTitle">개인정보 및 이용 안내</h2><p>수집 범위를 최소화해 운영합니다.</p></div><button class="close-button" type="button" data-close-overlay="privacyDialog" aria-label="닫기">×</button></div><div class="privacy-copy"><h3>계정과 저장함</h3><p>회원가입 시 이메일 주소와 Supabase가 발급한 사용자 식별자가 저장됩니다. 저장한 기사, 메모, 태그와 저장 시각은 계정별로 분리됩니다. 비밀번호는 SNAAC이 직접 보관하지 않습니다.</p><h3>서비스 개선 통계</h3><p>페이지 방문, 활성 체류 시간, 스크롤 깊이, 기사 카드 노출·클릭, 저장 퍼널과 피드백 같은 최소 이용 통계를 Supabase와 Mixpanel로 집계할 수 있습니다. 이메일, 비밀번호, 스크랩 메모와 태그 내용은 분석 도구로 보내지 않으며, Mixpanel의 IP 기반 위치 추정을 비활성화해 운영합니다. 주간 베스트는 최소 3개 브라우저의 반응이 모인 기사만 표시합니다.</p><p id="analyticsPreferenceStatus">현재 개인을 식별하지 않는 최소 이용 통계를 사용합니다.</p><button class="account-action" id="analyticsPreferenceButton" type="button" data-toggle-analytics>익명 통계 끄기</button><h3>보관과 삭제</h3><p>계정과 저장함은 회원 탈퇴 시 삭제됩니다. 익명 이용 통계와 피드백은 원칙적으로 90일 이내 보관하도록 운영자가 정기 정리하며, 해결된 기사 신고도 같은 기준으로 정리합니다. 미해결 신고는 확인이 끝날 때까지 보관할 수 있습니다.</p><h3>문의</h3><p>{contact}</p></div></section></div>

<div class="overlay mp-no-track mp-sensitive" id="deleteDialog" hidden><button class="overlay-backdrop" type="button" data-close-overlay="deleteDialog" aria-label="회원 탈퇴 닫기"></button><section class="panel" role="dialog" aria-modal="true" aria-labelledby="deleteTitle"><div class="drawer-handle"></div><div class="panel-head"><div><h2 id="deleteTitle">회원 탈퇴</h2><p>계정과 저장한 기사·메모가 삭제되며 되돌릴 수 없습니다.</p></div><button class="close-button" type="button" data-close-overlay="deleteDialog" aria-label="닫기">×</button></div><label class="form-label" for="deleteConfirmEmail">로그인 이메일</label><input class="form-input" id="deleteConfirmEmail" type="email" autocomplete="off"><label class="form-label" for="deleteConfirmPassword">현재 비밀번호</label><input class="form-input" id="deleteConfirmPassword" type="password" autocomplete="current-password"><p class="form-help">안전을 위해 탈퇴 직전에 비밀번호로 한 번 더 본인을 확인합니다.</p><button class="danger-button" id="deleteAccountButton" type="button" data-delete-account>계정과 저장 데이터 삭제</button><p class="auth-message is-error" id="deleteMessage" aria-live="polite"></p></section></div>

<p class="sr-only" id="liveStatus" aria-live="polite"></p>
"""


def _auth_config(context: str) -> dict:
    return {
        "url": SUPABASE_URL if AUTH_ENABLED else "",
        "publishableKey": SUPABASE_PUBLISHABLE_KEY if AUTH_ENABLED else "",
        "redirectUrl": SUPABASE_REDIRECT_URL,
        "homeHref": "./" if context == "home" else "../",
        "deleteAccountFunction": DELETE_ACCOUNT_FUNCTION or "delete-account",
    }


def _mixpanel_config() -> dict:
    return {
        "configured": MIXPANEL_CONFIGURED,
        "enabled": MIXPANEL_ENABLED,
        "token": MIXPANEL_PROJECT_TOKEN if MIXPANEL_CONFIGURED else "",
        "apiHost": MIXPANEL_API_HOST if MIXPANEL_CONFIGURED else "",
        "mode": BRIEFING_MODE or "deploy",
    }


def _scripts() -> str:
    scripts = []
    if AUTH_ENABLED:
        scripts.append('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>')
    if MIXPANEL_CONFIGURED:
        scripts.append(f'<script data-snaac-mixpanel="configured">{MIXPANEL_BOOTSTRAP_JS}</script>')
    return "\n".join(scripts)




def _feedback_html(context: str) -> str:
    if context != "home":
        return ""
    return """
<section class="feedback" aria-labelledby="feedbackTitle"><div class="feedback-copy"><h2 id="feedbackTitle">오늘 브리핑, 어땠나요?</h2><p>한 번만 눌러 알려주세요.</p></div><div class="feedback-actions"><button class="feedback-button" type="button" data-feedback="yes">👍 유용해요</button><button class="feedback-button" type="button" data-feedback="no">아쉬워요</button></div><p class="feedback-thanks" id="feedbackThanks" hidden>피드백 고마워요!</p></section>"""


def _page_html(picks: list[dict], now: datetime, context: str, generated_at: datetime) -> str:
    date_big = f"{now.month}.{now.day}."
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    slug = now.strftime("%Y-%m-%d")
    total = len(picks)
    cards = "".join(_card(index, total, pick) for index, pick in enumerate(picks, 1))
    og_image = (picks[0].get("image") if picks else "") or f"{SITE_URL}assets/{LOGO_ASSET_NAME}"
    storage_data = [
        {
            "title": pick["title"], "link": pick["link"], "source": pick["source"],
            "summary": pick["summary"], "takeaway": pick["takeaway"], "category": pick["category"],
            "contentType": pick["content_type"], "published": _format_published(pick.get("published", "unknown")),
            "briefingDate": date_label, "briefingSlug": slug, "image": pick.get("image") or "", "tags": [],
            "fallbackA": pick.get("fallback_a", "#2d4a74"), "fallbackB": pick.get("fallback_b", "#7699c8"),
        }
        for pick in picks
    ]
    page_config = {
        "briefingDate": slug,
        "briefingLabel": f"{now.month}월 {now.day}일",
        "generatedAt": generated_at.isoformat(),
        "context": context,
        "siteUrl": SITE_URL,
    }
    return f"""<!DOCTYPE html>
<html lang="ko" data-snaac-ui="6">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#f2f2f2">
<title>SNAAC 모닝 브리핑 · {html.escape(date_label)}</title><meta name="description" content="SNAAC이 고른 오늘의 스타트업 업데이트와 인사이트 {total}가지"><meta property="og:title" content="SNAAC 모닝 브리핑 · {now.month}/{now.day}"><meta property="og:description" content="스타트업 업데이트와 창업가·VC 인사이트"><meta property="og:image" content="{html.escape(og_image, quote=True)}"><meta property="og:url" content="{html.escape(SITE_URL, quote=True)}">
<link rel="preconnect" href="https://cdn.jsdelivr.net"><link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet"><style>{CSS}</style>
</head><body><div class="wrap"><header class="masthead">{_header_html(context)}<div class="date-lockup"><p class="kicker">Daily startup journal</p><h1 class="date-big">{date_big}</h1><div class="date-sub">{html.escape(date_label)}</div><div class="stamp">DAILY<strong>AM 9</strong>DROP</div></div></header>{_freshness_html()}
<section class="intro"><p>단순 투자 단신보다 오늘 스타트업을 이해하는 데 도움이 되는 업데이트와 인사이트를 골랐어요. 매일 4~5개의 콘텐츠를 소개합니다.</p><div class="editorial-rule"><span>핵심 업데이트</span><span>중복 최소화</span><span>인터뷰·영상 포함</span></div></section>
<main class="cards">{cards}</main>{_feedback_html(context)}{_archive_section(slug, context)}{_about_snaac_section()}<footer>매일 아침 자동 업데이트 · SNAAC Community Team<br>원문 링크와 자체 요약만 제공하며, 모든 콘텐츠의 저작권은 각 원저작자에게 있습니다.<div class="footer-links"><button class="footer-link" type="button" data-open-privacy>개인정보 안내</button><a class="footer-link" href="{html.escape(ABOUT_URL, quote=True)}" target="_blank" rel="noopener noreferrer">SNAAC 홈페이지</a></div></footer></div>
{_overlays_html()}<script id="briefingData" type="application/json">{_safe_json_for_script(storage_data)}</script><script id="pageConfig" type="application/json">{_safe_json_for_script(page_config)}</script><script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config(context))}</script><script id="mixpanelConfig" type="application/json">{_safe_json_for_script(_mixpanel_config())}</script>{_scripts()}<script>{JS}</script></body></html>"""


def _archive_index_html(entries: list[dict], generated_at: datetime) -> str:
    context = "archive"
    page_config = {"briefingDate": "", "briefingLabel": "지난 브리핑", "generatedAt": generated_at.isoformat(), "context": "archive-index", "siteUrl": SITE_URL}
    return f"""<!DOCTYPE html><html lang="ko" data-snaac-ui="6"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#f2f2f2"><title>SNAAC 지난 브리핑</title><meta name="description" content="SNAAC 모닝 브리핑 지난 회차 검색"><link rel="preconnect" href="https://cdn.jsdelivr.net"><link href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" rel="stylesheet"><style>{CSS}</style></head><body><div class="wrap"><header class="masthead">{_header_html(context)}</header><header class="archive-hero"><p class="kicker">SNAAC morning archive</p><h1>지난 브리핑</h1><p>날짜, 기사 제목, 매체 이름으로 과거 큐레이션을 찾아보세요.</p></header><div class="archive-tools" role="search"><label class="sr-only" for="archiveSearch">지난 브리핑 검색</label><input class="archive-search" id="archiveSearch" type="search" value="" placeholder="예: AI 에이전트, EO, 조직문화" autocomplete="off" aria-autocomplete="none" autocorrect="off" autocapitalize="none" spellcheck="false" inputmode="search" data-1p-ignore="true" data-lpignore="true" data-form-type="other" readonly></div><main class="archive-page-list"><div class="archive-list">{_archive_rows(entries, searchable=True)}</div><p class="archive-no-result" id="archiveNoResult" hidden>검색 결과가 없어요.</p></main>{_about_snaac_section()}<footer><div class="footer-links"><button class="footer-link" type="button" data-open-privacy>개인정보 안내</button></div></footer></div>{_overlays_html()}<script id="briefingData" type="application/json">[]</script><script id="pageConfig" type="application/json">{_safe_json_for_script(page_config)}</script><script id="authConfig" type="application/json">{_safe_json_for_script(_auth_config(context))}</script><script id="mixpanelConfig" type="application/json">{_safe_json_for_script(_mixpanel_config())}</script>{_scripts()}<script>{JS}</script></body></html>"""


def _existing_image_hints(html_path: Path) -> dict[str, str]:
    if not html_path.exists():
        return {}
    try:
        text = html_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    hints: dict[str, str] = {}
    pattern = re.compile(r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"', flags=re.I | re.S)
    for match in pattern.finditer(text):
        link, image = html.unescape(match.group(1)), html.unescape(match.group(2))
        if _public_image_url(image):
            hints[link] = image
    return hints


def _upgrade_existing_archives(current_slug: str, generated_at: datetime) -> int:
    archive_dir = DOCS_DIR / "archive"
    upgraded = 0
    for json_path in sorted(archive_dir.glob("????-??-??.json"), reverse=True):
        slug = json_path.stem
        if slug == current_slug:
            continue
        html_path = archive_dir / f"{slug}.html"
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            raw_picks = data.get("picks", [])
            day = datetime.strptime(slug, "%Y-%m-%d").replace(tzinfo=KST)
            raw_generated_at = str(data.get("generated_at", "")).strip()
            archive_generated_at = datetime.fromisoformat(raw_generated_at) if raw_generated_at else day
            if archive_generated_at.tzinfo is None:
                archive_generated_at = archive_generated_at.replace(tzinfo=KST)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(raw_picks, list) or not raw_picks:
            continue
        date_label = f"{day.year}년 {day.month}월 {day.day}일 {WEEKDAYS[day.weekday()]}요일"
        prepared = _prepare_picks(raw_picks, date_label, slug, image_hints=_existing_image_hints(html_path), fetch_missing_images=False)
        html_path.write_text(_page_html(prepared, day, "archive", archive_generated_at), encoding="utf-8")
        upgraded += 1
    return upgraded


def _write_logo_asset() -> None:
    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / LOGO_ASSET_NAME
    if SOURCE_ASSET.exists():
        shutil.copyfile(SOURCE_ASSET, target)
    elif not target.exists():
        print(f"[경고] 로고 원본이 없습니다: {SOURCE_ASSET}")


def build_page(picks: list[dict], output_dir: str | Path | None = None) -> None:
    global DOCS_DIR
    if output_dir is not None:
        DOCS_DIR = Path(output_dir)
    now = datetime.now(KST)
    generated_at = now
    slug = now.strftime("%Y-%m-%d")
    date_label = f"{now.year}년 {now.month}월 {now.day}일 {WEEKDAYS[now.weekday()]}요일"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    archive_dir = DOCS_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    _write_logo_asset()
    if MIXPANEL_ENABLED_REQUESTED and not MIXPANEL_CONFIGURED:
        print("[경고] Mixpanel이 요청됐지만 Project Token 또는 API Host 설정이 올바르지 않아 분석을 비활성화합니다.")
    elif MIXPANEL_CONFIGURED and BRIEFING_MODE == "preview":
        print("[안내] preview 모드에서는 Mixpanel 이벤트 전송을 비활성화합니다.")
    prepared = _prepare_picks(picks, date_label, slug)
    (DOCS_DIR / "index.html").write_text(_page_html(prepared, now, "home", generated_at), encoding="utf-8")
    (archive_dir / f"{slug}.html").write_text(_page_html(prepared, now, "archive", generated_at), encoding="utf-8")
    archive_data = {"date": slug, "date_label": date_label, "generated_at": generated_at.isoformat(), "picks": prepared}
    (archive_dir / f"{slug}.json").write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8")
    upgraded = _upgrade_existing_archives(slug, generated_at)
    (archive_dir / "index.html").write_text(_archive_index_html(_archive_entries(), generated_at), encoding="utf-8")
    print(
        f"[페이지 생성 완료] {DOCS_DIR}/index.html 외 아카이브 생성 "
        f"({len(prepared)}건, 과거 UI 갱신 {upgraded}건, "
        f"로그인 {'활성' if AUTH_ENABLED else '설정 대기'}, "
        f"Mixpanel {'활성' if MIXPANEL_ENABLED else ('미리보기 비활성' if MIXPANEL_CONFIGURED and BRIEFING_MODE == 'preview' else '비활성')})"
    )
