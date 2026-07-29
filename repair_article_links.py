"""생성된 브리핑의 기사 URL에서 추적 파라미터를 제거합니다.

이 스크립트는 현재 페이지와 과거 아카이브 JSON/HTML을 함께 정리합니다.
매일 실행해도 이미 정리된 파일은 변경하지 않습니다.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

from link_utils import clean_public_link


def _safe_json_url(url: str) -> str:
    """page.py의 script JSON 이스케이프 방식과 동일하게 변환합니다."""
    return url.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _clean_links_in_value(value: Any, replacements: dict[str, str]) -> int:
    changed = 0
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if key == "link" and isinstance(child, str):
                cleaned = clean_public_link(child)
                if cleaned and cleaned != child:
                    value[key] = cleaned
                    replacements[child] = cleaned
                    changed += 1
            else:
                changed += _clean_links_in_value(child, replacements)
    elif isinstance(value, list):
        for child in value:
            changed += _clean_links_in_value(child, replacements)
    return changed


def _repair_json_files(root: Path) -> tuple[int, dict[str, str]]:
    changed_links = 0
    replacements: dict[str, str] = {}
    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"JSON 파일을 읽을 수 없습니다: {path}: {exc}") from exc
        count = _clean_links_in_value(data, replacements)
        if not count:
            continue
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        changed_links += count
        print(f"[아카이브 링크 정리] {path}: {count}건")
    return changed_links, replacements


def _repair_html_files(root: Path, replacements: dict[str, str]) -> int:
    changed_files = 0
    if not replacements:
        return changed_files
    for path in sorted(root.rglob("*.html")):
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"HTML 파일을 읽을 수 없습니다: {path}: {exc}") from exc
        updated = original
        for old, new in replacements.items():
            variants = (
                (old, new),
                (html.escape(old, quote=True), html.escape(new, quote=True)),
                (_safe_json_url(old), _safe_json_url(new)),
            )
            for old_variant, new_variant in variants:
                updated = updated.replace(old_variant, new_variant)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files += 1
            print(f"[HTML 링크 정리] {path}")
    return changed_files


def _assert_json_links_clean(root: Path) -> None:
    leftovers: list[str] = []
    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "link" and isinstance(child, str):
                        cleaned = clean_public_link(child)
                        if cleaned != child:
                            leftovers.append(f"{path}: {child}")
                    else:
                        visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(data)
    if leftovers:
        sample = "\n".join(leftovers[:10])
        raise RuntimeError(f"정리되지 않은 기사 링크가 남아 있습니다:\n{sample}")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "docs")
    if not root.exists():
        print(f"[링크 정리 건너뜀] 출력 폴더가 없습니다: {root}")
        return 0

    changed_links, replacements = _repair_json_files(root)
    changed_html_files = _repair_html_files(root, replacements)
    _assert_json_links_clean(root)
    print(
        f"[기사 링크 정리 완료] JSON 링크 {changed_links}건, "
        f"HTML 파일 {changed_html_files}개 수정"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
