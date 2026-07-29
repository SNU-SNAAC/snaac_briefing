"""생성된 SNAAC 정적 페이지의 최소 배포 요건을 검사합니다.

GitHub Actions에서 main.py 실행 직후 호출합니다. 품질 보류로 기존 페이지를
유지한 경우에는 기존 페이지가 실제로 존재하는지만 확인하고, 새 회차를 생성한
경우에는 v6 핵심 UI와 데이터, 인라인 JavaScript 문법까지 검사합니다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REQUIRED_MARKERS = (
    'data-snaac-ui="6"',
    'id="freshness"',
    'data-open-saved',
    'data-open-auth',
    'data-report-url',
    'data-open-privacy',
    'data-open-preferences',
    'id="noteTagsInput"',
    'id="savedSearch"',
    'id="weeklyBest"',
    'id="archiveSearch"',
)


def fail(message: str) -> None:
    print(f"[생성 결과 검사 실패] {message}", file=sys.stderr)
    raise SystemExit(1)


def extract_json(html: str, element_id: str) -> object:
    match = re.search(
        rf'<script[^>]+id=["\']{re.escape(element_id)}["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        fail(f"{element_id} JSON 블록이 없습니다.")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        fail(f"{element_id} JSON이 올바르지 않습니다: {exc}")


def check_inline_javascript(html: str) -> None:
    node = shutil.which("node")
    if not node:
        print("[생성 결과 검사] Node.js가 없어 JavaScript 문법 검사를 건너뜁니다.")
        return

    scripts = re.findall(
        r'<script(?![^>]+(?:src=|type=["\']application/json["\']))[^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not scripts:
        fail("검사할 인라인 JavaScript가 없습니다.")

    source = "\n".join(scripts)
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(source)
        temp_path = Path(handle.name)
    try:
        result = subprocess.run(
            [node, "--check", str(temp_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            fail(f"JavaScript 문법 오류:\n{result.stderr.strip()}")
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> None:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BRIEFING_OUTPUT_DIR", "docs"))
    index_path = output_dir / "index.html"
    archive_index_path = output_dir / "archive" / "index.html"
    hold_path = Path("briefing_quality_hold.txt")

    if not index_path.exists():
        fail(f"{index_path}가 없습니다.")
    if not archive_index_path.exists():
        fail(f"{archive_index_path}가 없습니다.")

    index_html = index_path.read_text(encoding="utf-8")
    archive_html = archive_index_path.read_text(encoding="utf-8")

    if hold_path.exists():
        print(f"[생성 결과 검사] 품질 보류 상태 — 기존 페이지 유지 확인: {hold_path.read_text(encoding='utf-8').strip()}")
        return

    missing = [marker for marker in REQUIRED_MARKERS[:-1] if marker not in index_html]
    if REQUIRED_MARKERS[-1] not in archive_html:
        missing.append(REQUIRED_MARKERS[-1])
    if missing:
        fail("핵심 UI 마커 누락: " + ", ".join(missing))

    items = extract_json(index_html, "briefingData")
    page_config = extract_json(index_html, "pageConfig")
    if not isinstance(items, list) or not (3 <= len(items) <= 5):
        fail(f"기사 수가 3~5개가 아닙니다: {len(items) if isinstance(items, list) else '목록 아님'}")
    if not isinstance(page_config, dict) or not page_config.get("generatedAt"):
        fail("pageConfig.generatedAt이 없습니다.")

    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            fail(f"{index}번 기사가 객체가 아닙니다.")
        for key in ("title", "link", "source", "summary", "takeaway"):
            if not str(item.get(key, "")).strip():
                fail(f"{index}번 기사에 {key} 값이 없습니다.")

    check_inline_javascript(index_html)
    print(f"[생성 결과 검사 완료] {len(items)}개 기사 · v6 UI · 관심 분야·태그·주간 베스트 · 아카이브 검색 · JavaScript 정상")


if __name__ == "__main__":
    main()
