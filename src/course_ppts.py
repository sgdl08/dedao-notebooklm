"""NotebookLM course-to-PPT workflow."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from utils import get_config


DEFAULT_PROMPT = (
    "全部标题、正文、图注、演讲备注必须使用简体中文。"
    "版式适合 16:9 演讲场景，优先输出结构清晰、适合讲解的页面。"
)
DEFAULT_EXCLUDE_KEYWORDS = ("发刊词", "特别放送", "问答")
DEFAULT_LANGUAGE = "zh_Hans"
NOTEBOOKLM_STORAGE = Path.home() / ".notebooklm" / "storage_state.json"
LEGACY_STORAGE = Path.home() / ".dedao-notebooklm" / "storage_state.json"


@dataclass
class SourceRecord:
    id: str
    title: str
    status: str


def sanitize_filename(name: str) -> str:
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name.strip().rstrip(".")


def sanitize_wrapped_json(text: str) -> str:
    """Repair JSON strings wrapped by the Windows console."""
    out: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string and char in "\r\n":
            continue
        out.append(char)
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string

    return "".join(out)


def resolve_storage_path(explicit: str | Path | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"NotebookLM storage file does not exist: {path}")
        return path

    candidates = [path for path in (NOTEBOOKLM_STORAGE, LEGACY_STORAGE) if path.exists()]
    if not candidates:
        raise FileNotFoundError(
            "No NotebookLM storage_state.json found. Run 'notebooklm login' first."
        )

    return max(candidates, key=lambda path: path.stat().st_mtime)


def run_notebooklm(
    storage: Path,
    args: list[str],
    *,
    expect_json: bool = True,
    timeout: int = 600,
) -> Any:
    cmd = ["notebooklm", "--storage", str(storage), *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    stdout = result.stdout.strip()
    if expect_json:
        try:
            return json.loads(stdout or "{}")
        except json.JSONDecodeError as exc:
            sanitized = sanitize_wrapped_json(stdout)
            try:
                return json.loads(sanitized or "{}")
            except json.JSONDecodeError:
                pass
            raise RuntimeError(
                f"Invalid JSON from command: {' '.join(cmd)}\nSTDOUT:\n{stdout}\nSTDERR:\n{result.stderr}"
            ) from exc
    return stdout


def list_notebooks(storage: Path) -> list[dict[str, Any]]:
    payload = run_notebooklm(storage, ["list", "--json"])
    return payload.get("notebooks", [])


def find_or_create_notebook(storage: Path, title: str) -> str:
    for notebook in list_notebooks(storage):
        if notebook.get("title") == title:
            return notebook["id"]

    payload = run_notebooklm(storage, ["create", title, "--json"])
    notebook_id = payload.get("id")
    if not notebook_id:
        raise RuntimeError(f"Notebook creation returned no id for title: {title}")
    return notebook_id


def list_sources(storage: Path, notebook_id: str) -> list[SourceRecord]:
    payload = run_notebooklm(storage, ["source", "list", "-n", notebook_id, "--json"])
    sources = []
    for item in payload.get("sources", []):
        source_id = item.get("id")
        title = item.get("title")
        status = item.get("status", "")
        if source_id and title:
            sources.append(SourceRecord(id=source_id, title=title, status=status))
    return sources


def chapter_files(course_dir: Path) -> list[Path]:
    files = []
    for path in sorted(course_dir.glob("*.md")):
        if re.match(r"^\d+_.+\.md$", path.name):
            files.append(path)
    return files


def upload_missing_sources(storage: Path, notebook_id: str, files: list[Path]) -> None:
    existing_titles = {source.title for source in list_sources(storage, notebook_id)}
    for file_path in files:
        if file_path.name in existing_titles:
            continue
        run_notebooklm(
            storage,
            ["source", "add", "-n", notebook_id, str(file_path), "--json"],
            timeout=900,
        )


def wait_until_sources_ready(
    storage: Path,
    notebook_id: str,
    expected_titles: set[str],
    *,
    timeout_seconds: int = 900,
    poll_seconds: int = 5,
) -> list[SourceRecord]:
    deadline = time.time() + timeout_seconds
    last_sources: list[SourceRecord] = []

    while time.time() < deadline:
        last_sources = list_sources(storage, notebook_id)
        ready_titles = {source.title for source in last_sources if source.status == "ready"}
        if expected_titles.issubset(ready_titles):
            return last_sources
        time.sleep(poll_seconds)

    missing = sorted(
        expected_titles - {source.title for source in last_sources if source.status == "ready"}
    )
    raise TimeoutError(f"Timed out waiting for sources to become ready: {missing}")


def should_exclude(title: str, exclude_keywords: tuple[str, ...]) -> bool:
    return any(keyword in title for keyword in exclude_keywords)


def generate_slide_deck(
    storage: Path,
    notebook_id: str,
    source_id: str,
    prompt: str,
    language: str,
) -> dict[str, Any]:
    return run_notebooklm(
        storage,
        [
            "generate",
            "slide-deck",
            prompt,
            "-n",
            notebook_id,
            "-s",
            source_id,
            "--language",
            language,
            "--json",
        ],
        timeout=300,
    )


def download_slide_deck(
    storage: Path,
    notebook_id: str,
    output_path: Path,
    artifact_id: str | None,
) -> dict[str, Any]:
    if not artifact_id:
        raise RuntimeError(f"Artifact id is required to download {output_path.name}")

    tmp_path = Path(tempfile.gettempdir()) / f"notebooklm_{artifact_id}.pptx"
    if tmp_path.exists():
        tmp_path.unlink()

    args = [
        "download",
        "slide-deck",
        str(tmp_path),
        "-n",
        notebook_id,
        "--format",
        "pptx",
        "--force",
        "--json",
        "-a",
        artifact_id,
    ]
    last_error: RuntimeError | None = None
    for _ in range(3):
        try:
            payload = run_notebooklm(storage, args, timeout=900)
            if not tmp_path.exists():
                raise RuntimeError(f"Downloaded file missing: {tmp_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.replace(output_path)
            payload["output_path"] = str(output_path)
            return payload
        except RuntimeError as exc:
            last_error = exc
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            time.sleep(5)

    assert last_error is not None
    raise last_error


def wait_for_artifact(
    storage: Path,
    notebook_id: str,
    artifact_id: str,
    *,
    timeout_seconds: int = 1800,
    interval_seconds: int = 5,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_error: RuntimeError | None = None

    while time.time() < deadline:
        remaining = max(30, int(deadline - time.time()))
        try:
            return run_notebooklm(
                storage,
                [
                    "artifact",
                    "wait",
                    artifact_id,
                    "-n",
                    notebook_id,
                    "--timeout",
                    str(remaining),
                    "--interval",
                    str(interval_seconds),
                    "--json",
                ],
                timeout=remaining + 120,
            )
        except RuntimeError as exc:
            last_error = exc
            message = str(exc)
            if "Connection failed" not in message and "LIST_ARTIFACTS" not in message:
                raise
            time.sleep(interval_seconds)

    assert last_error is not None
    raise last_error


def default_output_dir(notebook_title: str) -> Path:
    return Path(get_config().ppt_dir).expanduser().resolve() / sanitize_filename(notebook_title)


def run_course_ppts(
    course_dir: str | Path,
    *,
    storage: str | Path | None = None,
    notebook_title: str = "",
    prompt: str = DEFAULT_PROMPT,
    language: str = DEFAULT_LANGUAGE,
    output_dir: str | Path | None = None,
    force: bool = False,
    exclude_keywords: Sequence[str] = DEFAULT_EXCLUDE_KEYWORDS,
) -> dict[str, Any]:
    course_dir_path = Path(course_dir).expanduser().resolve()
    if not course_dir_path.exists():
        raise FileNotFoundError(f"Course directory does not exist: {course_dir_path}")

    resolved_notebook_title = notebook_title or course_dir_path.name
    resolved_output_dir = (
        Path(output_dir).expanduser().resolve()
        if output_dir
        else default_output_dir(resolved_notebook_title)
    )
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    files = chapter_files(course_dir_path)
    if not files:
        raise FileNotFoundError(f"No chapter markdown files found in {course_dir_path}")

    exclude_tuple = tuple(exclude_keywords)
    eligible_files = [file for file in files if not should_exclude(file.name, exclude_tuple)]
    if eligible_files and not force:
        existing_items: list[dict[str, Any]] = []
        for file in eligible_files:
            output_path = resolved_output_dir / f"{sanitize_filename(file.stem)}.pptx"
            if not output_path.exists():
                existing_items = []
                break
            existing_items.append(
                {
                    "source_id": "",
                    "source_title": file.name,
                    "artifact_id": "",
                    "output_path": str(output_path),
                    "generation": {"status": "skipped_existing"},
                    "download": {"status": "skipped_existing"},
                }
            )
        if existing_items:
            manifest = {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "course_dir": str(course_dir_path),
                "storage_path": "",
                "notebook_id": "",
                "notebook_title": resolved_notebook_title,
                "prompt": prompt,
                "language": language,
                "exclude_keywords": list(exclude_tuple),
                "total_sources": len(files),
                "generated_count": len(existing_items),
                "output_dir": str(resolved_output_dir),
                "items": existing_items,
                "local_only": True,
            }
            manifest_path = resolved_output_dir / "ppt_manifest.json"
            manifest["manifest_path"] = str(manifest_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return manifest

    storage_path = resolve_storage_path(storage)
    notebook_id = find_or_create_notebook(storage_path, resolved_notebook_title)
    upload_missing_sources(storage_path, notebook_id, files)
    sources = wait_until_sources_ready(storage_path, notebook_id, {file.name for file in files})

    eligible_sources = [source for source in sources if not should_exclude(source.title, exclude_tuple)]
    eligible_sources.sort(key=lambda source: source.title)

    generated: list[dict[str, Any]] = []
    for source in eligible_sources:
        stem = Path(source.title).stem
        output_path = resolved_output_dir / f"{sanitize_filename(stem)}.pptx"
        if output_path.exists() and not force:
            generated.append(
                {
                    "source_id": source.id,
                    "source_title": source.title,
                    "artifact_id": "",
                    "output_path": str(output_path),
                    "generation": {"status": "skipped_existing"},
                    "download": {"status": "skipped_existing"},
                }
            )
            continue

        generation_request = generate_slide_deck(
            storage_path, notebook_id, source.id, prompt, language
        )
        artifact_id = generation_request.get("artifact_id") or generation_request.get("task_id")
        if not artifact_id:
            raise RuntimeError(f"No artifact id returned for source: {source.title}")
        generation = wait_for_artifact(storage_path, notebook_id, artifact_id)
        download = download_slide_deck(storage_path, notebook_id, output_path, artifact_id)
        generated.append(
            {
                "source_id": source.id,
                "source_title": source.title,
                "artifact_id": artifact_id,
                "output_path": str(output_path),
                "generation": generation,
                "download": download,
            }
        )

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "course_dir": str(course_dir_path),
        "storage_path": str(storage_path),
        "notebook_id": notebook_id,
        "notebook_title": resolved_notebook_title,
        "prompt": prompt,
        "language": language,
        "exclude_keywords": list(exclude_tuple),
        "total_sources": len(sources),
        "generated_count": len(generated),
        "output_dir": str(resolved_output_dir),
        "items": generated,
    }
    manifest_path = resolved_output_dir / "ppt_manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload course chapters and generate PPTX from NotebookLM.")
    parser.add_argument("course_dir", help="Course directory containing chapter markdown files")
    parser.add_argument("--storage", default="", help="NotebookLM storage_state.json path; auto-picks newest if omitted")
    parser.add_argument("--notebook-title", default="", help="Notebook title; defaults to course directory name")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Slide deck generation prompt")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="NotebookLM output language code")
    parser.add_argument("--output-dir", default="", help="Output directory for PPTX files")
    parser.add_argument("--force", action="store_true", help="Regenerate even if output PPTX already exists")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=list(DEFAULT_EXCLUDE_KEYWORDS),
        help="Keywords to exclude from PPT generation",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = run_course_ppts(
        args.course_dir,
        storage=args.storage or None,
        notebook_title=args.notebook_title,
        prompt=args.prompt,
        language=args.language,
        output_dir=args.output_dir or None,
        force=args.force,
        exclude_keywords=args.exclude,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
