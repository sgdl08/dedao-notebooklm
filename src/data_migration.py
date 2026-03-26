"""Project data migration helpers."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from utils import get_config


def _rewrite_path_value(value: str, project_root: Path, download_root: Path, ppt_root: Path) -> str:
    normalized = value.replace("/", "\\")
    project_root_str = str(project_root).replace("/", "\\")
    project_downloads = f"{project_root_str}\\downloads"
    project_ppts = f"{project_root_str}\\ppts"

    if normalized.startswith(project_downloads):
        suffix = normalized[len(project_downloads):].lstrip("\\")
        return str(download_root / Path(suffix))
    if normalized.startswith(project_ppts):
        suffix = normalized[len(project_ppts):].lstrip("\\")
        return str(ppt_root / Path(suffix))
    if normalized.startswith("downloads\\"):
        suffix = normalized[len("downloads\\"):]
        return str(download_root / Path(suffix))
    if normalized.startswith("ppts\\"):
        suffix = normalized[len("ppts\\"):]
        return str(ppt_root / Path(suffix))
    return value


def _rewrite_json_paths(obj: Any, project_root: Path, download_root: Path, ppt_root: Path) -> Any:
    if isinstance(obj, dict):
        return {
            key: _rewrite_json_paths(value, project_root, download_root, ppt_root)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_rewrite_json_paths(value, project_root, download_root, ppt_root) for value in obj]
    if isinstance(obj, str):
        return _rewrite_path_value(obj, project_root, download_root, ppt_root)
    return obj


def _merge_move(source: Path, target: Path) -> int:
    moved = 0
    if not source.exists():
        return moved

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.move(str(source), str(target))
        return sum(1 for _ in target.rglob("*"))

    for item in source.iterdir():
        dest = target / item.name
        if item.is_dir():
            moved += _merge_move(item, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(dest))
            moved += 1

    if source.exists() and not any(source.iterdir()):
        source.rmdir()
    return moved


def _normalize_json_tree(root: Path, project_root: Path, download_root: Path, ppt_root: Path) -> int:
    updated = 0
    if not root.exists():
        return updated

    for path in root.rglob("*.json"):
        try:
            original = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rewritten = _rewrite_json_paths(original, project_root, download_root, ppt_root)
        if rewritten != original:
            path.write_text(json.dumps(rewritten, ensure_ascii=False, indent=2), encoding="utf-8")
            updated += 1
    return updated


def migrate_project_data(
    *,
    project_root: Path,
    download_root: Path,
    ppt_root: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_project_root = project_root.expanduser().resolve()
    resolved_download_root = download_root.expanduser().resolve()
    resolved_ppt_root = ppt_root.expanduser().resolve()

    source_downloads = resolved_project_root / "downloads"
    source_ppts = resolved_project_root / "ppts"

    plan = {
        "project_root": str(resolved_project_root),
        "download_root": str(resolved_download_root),
        "ppt_root": str(resolved_ppt_root),
        "source_downloads_exists": source_downloads.exists(),
        "source_ppts_exists": source_ppts.exists(),
        "dry_run": dry_run,
    }

    if dry_run:
        return {
            **plan,
            "downloads_moved_entries": 0,
            "ppts_moved_entries": 0,
            "normalized_json_files": 0,
        }

    resolved_download_root.parent.mkdir(parents=True, exist_ok=True)
    resolved_ppt_root.parent.mkdir(parents=True, exist_ok=True)

    downloads_moved_entries = _merge_move(source_downloads, resolved_download_root)
    ppts_moved_entries = _merge_move(source_ppts, resolved_ppt_root)
    normalized_json_files = (
        _normalize_json_tree(
            resolved_download_root,
            resolved_project_root,
            resolved_download_root,
            resolved_ppt_root,
        )
        + _normalize_json_tree(
            resolved_ppt_root,
            resolved_project_root,
            resolved_download_root,
            resolved_ppt_root,
        )
    )

    return {
        **plan,
        "downloads_moved_entries": downloads_moved_entries,
        "ppts_moved_entries": ppts_moved_entries,
        "normalized_json_files": normalized_json_files,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Move project-local downloads/ppts outside the repository.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--download-root", default="", help="External download root; defaults to config download_dir")
    parser.add_argument("--ppt-root", default="", help="External PPT root; defaults to config ppt_dir")
    parser.add_argument("--dry-run", action="store_true", help="Print the migration plan without executing it")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = get_config()
    result = migrate_project_data(
        project_root=Path(args.project_root),
        download_root=Path(args.download_root or config.download_dir),
        ppt_root=Path(args.ppt_root or config.ppt_dir),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
