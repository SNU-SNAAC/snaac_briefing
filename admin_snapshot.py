"""SNAAC 운영자 통합 대시보드용 일일 스냅샷 생성기.

Supabase(서비스 롤 키)로 피드백·신고·저장 통계를 모으고, Mixpanel Service
Account가 설정돼 있으면 핵심 이용 지표까지 합쳐 하나의 JSON으로 만든 뒤
public.admin_dashboard_snapshot(단일 행)에 저장합니다.

운영자는 docs/admin/index.html에 로그인해서 이 스냅샷을 봅니다. 이 스크립트는
service_role 키를 사용하므로 반드시 GitHub Actions Secrets에서만 주입하고,
로그나 커밋에 남기지 않습니다.
"""

from __future__ import annotations

import base64
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

MIXPANEL_SERVICE_ACCOUNT_USERNAME = os.environ.get("MIXPANEL_SERVICE_ACCOUNT_USERNAME", "").strip()
MIXPANEL_SERVICE_ACCOUNT_SECRET = os.environ.get("MIXPANEL_SERVICE_ACCOUNT_SECRET", "").strip()
MIXPANEL_PROJECT_ID = os.environ.get("MIXPANEL_PROJECT_ID", "").strip()

REST_BASE = f"{SUPABASE_URL}/rest/v1"
REST_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def _rest_get(path: str, params: dict) -> list[dict]:
    resp = requests.get(f"{REST_BASE}/{path}", headers=REST_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _rest_count(table: str, params: dict) -> int:
    # 테이블마다 id 컬럼이 있다고 가정할 수 없어(예: saved_articles는 복합 기본키) select=*를 씁니다.
    headers = {**REST_HEADERS, "Prefer": "count=exact"}
    params = {**params, "select": "*"}
    resp = requests.head(f"{REST_BASE}/{table}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    content_range = resp.headers.get("Content-Range", "*/0")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0


def collect_supabase_section() -> dict:
    now = datetime.now(KST)
    since_7d = (now - timedelta(days=7)).isoformat()

    feedback_by_date = _rest_get(
        "briefing_feedback_metrics",
        {"select": "briefing_date,responses,helpful_count,helpful_percent", "order": "briefing_date.desc", "limit": "30"},
    )
    feedback_7d = [r for r in feedback_by_date if r.get("briefing_date", "") >= (now - timedelta(days=7)).strftime("%Y-%m-%d")]
    responses_7d = sum(r["responses"] for r in feedback_7d)
    helpful_7d = sum(r["helpful_count"] for r in feedback_7d)

    report_rows = _rest_get(
        "article_reports",
        {
            "select": "id,created_at,briefing_date,article_title,article_source,article_url,reason,detail,status",
            "order": "created_at.desc",
            "limit": "100",
        },
    )
    open_reports = [r for r in report_rows if r.get("status") in ("open", "checking")]

    saved_total = _rest_count("saved_articles", {})
    saved_7d = _rest_count("saved_articles", {"saved_at": f"gte.{since_7d}"})

    top_articles = _rest_get(
        "article_engagement_metrics",
        {"select": "*", "order": "briefing_date.desc,clicks.desc", "limit": "10"},
    )

    return {
        "feedback": {
            "responses_7d": responses_7d,
            "helpful_7d": helpful_7d,
            "helpful_rate_7d": round(100.0 * helpful_7d / responses_7d, 1) if responses_7d else None,
            "by_date": feedback_by_date,
        },
        "reports": {
            "open_count": len(open_reports),
            "recent": report_rows[:30],
        },
        "saved_articles": {
            "total": saved_total,
            "last_7d": saved_7d,
        },
        "top_articles_recent": top_articles,
    }


def _mixpanel_auth_header() -> str:
    token = base64.b64encode(
        f"{MIXPANEL_SERVICE_ACCOUNT_USERNAME}:{MIXPANEL_SERVICE_ACCOUNT_SECRET}".encode("utf-8")
    ).decode("ascii")
    return f"Basic {token}"


def _mixpanel_daily_unique(event: str, from_date: str, to_date: str) -> dict:
    resp = requests.get(
        "https://mixpanel.com/api/2.0/segmentation",
        headers={"Authorization": _mixpanel_auth_header()},
        params={
            "project_id": MIXPANEL_PROJECT_ID,
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "type": "unique",
            "unit": "day",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {}).get("values", {})
    # values 형태: {"이벤트명": {"YYYY-MM-DD": 값, ...}}
    series = next(iter(data.values()), {}) if data else {}
    return series


def collect_mixpanel_section() -> dict:
    if not (MIXPANEL_SERVICE_ACCOUNT_USERNAME and MIXPANEL_SERVICE_ACCOUNT_SECRET and MIXPANEL_PROJECT_ID):
        return {"configured": False}

    now = datetime.now(KST)
    from_date = (now - timedelta(days=13)).strftime("%Y-%m-%d")
    to_date = now.strftime("%Y-%m-%d")

    try:
        visitors = _mixpanel_daily_unique("briefing_viewed", from_date, to_date)
        meaningful = _mixpanel_daily_unique("meaningful_read", from_date, to_date)
        save_clicked = _mixpanel_daily_unique("save_clicked", from_date, to_date)
        article_saved = _mixpanel_daily_unique("article_saved", from_date, to_date)

        last7_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        visitors_7d = sum(visitors.get(d, 0) for d in last7_dates)
        meaningful_7d = sum(meaningful.get(d, 0) for d in last7_dates)
        save_clicked_7d = sum(save_clicked.get(d, 0) for d in last7_dates)
        article_saved_7d = sum(article_saved.get(d, 0) for d in last7_dates)

        return {
            "configured": True,
            "range": {"from": from_date, "to": to_date},
            "daily_visitors": visitors,
            "meaningful_read_rate_7d": round(100.0 * meaningful_7d / visitors_7d, 1) if visitors_7d else None,
            "save_completion_rate_7d": round(100.0 * article_saved_7d / save_clicked_7d, 1) if save_clicked_7d else None,
            "visitors_7d_total": visitors_7d,
        }
    except Exception as error:  # noqa: BLE001 - Mixpanel 실패는 스냅샷 전체를 막지 않습니다.
        return {"configured": True, "error": str(error)}


def upsert_snapshot(payload: dict) -> None:
    resp = requests.post(
        f"{REST_BASE}/admin_dashboard_snapshot",
        headers={**REST_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json={"id": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "payload": payload},
        timeout=30,
    )
    resp.raise_for_status()


def main() -> None:
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY가 필요합니다.", file=sys.stderr)
        raise SystemExit(1)

    payload = {
        "supabase": collect_supabase_section(),
        "mixpanel": collect_mixpanel_section(),
    }
    upsert_snapshot(payload)
    print("[admin_snapshot] 스냅샷 저장 완료")


if __name__ == "__main__":
    main()
