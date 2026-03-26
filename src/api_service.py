"""FastAPI service for dedao-notebooklm."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

SRC_DIR = Path(__file__).resolve().parent
SRC_DIR_STR = str(SRC_DIR)
if sys.path[:1] != [SRC_DIR_STR]:
    try:
        sys.path.remove(SRC_DIR_STR)
    except ValueError:
        pass
    sys.path.insert(0, SRC_DIR_STR)

from course_sync import CourseSyncService
from dedao.client import DedaoClient
from notebooklm.api_client import NotebookLMAPIClient
from utils import get_config, load_config

app = FastAPI(title="dedao-notebooklm API", version="v1")


class SyncCourseRequest(BaseModel):
    course_id: str = Field(..., description="课程 ID")
    output_dir: Optional[str] = Field(None, description="输出目录；默认使用配置中的 download_dir")
    include_audio: bool = False
    output_format: str = "md"
    workers: int = 5
    upload_to_notebooklm: bool = False
    notebook_id: Optional[str] = None


class UploadRequest(BaseModel):
    notebook_id: str
    files: list[str]
    storage_state: Optional[str] = None


def _build_client() -> DedaoClient:
    load_config()
    cfg = get_config()
    if not cfg.dedao_cookie:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_required", "message": "dedao_cookie 未配置"},
        )
    return DedaoClient(cookie=cfg.dedao_cookie)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "dedao-notebooklm", "version": "v1"}


@app.post("/courses/sync")
def sync_course(req: SyncCourseRequest) -> dict[str, object]:
    cfg = get_config()
    client = _build_client()
    service = CourseSyncService(
        client=client,
        output_root=Path(req.output_dir or cfg.download_dir),
        workers=req.workers,
    )
    result = service.sync_course(
        course_id=req.course_id,
        include_audio=req.include_audio,
        output_format=req.output_format,
        upload_to_notebooklm=req.upload_to_notebooklm,
        notebook_id=req.notebook_id,
    )
    return {
        "ok": result.failed == 0,
        "course_id": result.course_id,
        "course_title": result.course_title,
        "course_dir": str(result.course_dir),
        "manifest_path": str(result.manifest_path),
        "chapter_state_path": str(result.chapter_state_path),
        "downloaded": result.downloaded,
        "skipped": result.skipped,
        "failed": result.failed,
        "uploaded_files": result.uploaded_files,
        "notebook_id": result.notebook_id,
        "notebook_url": result.notebook_url,
        "ai_pack": result.ai_pack,
    }


@app.get("/courses/{course_id}/manifest")
def get_manifest(course_id: str, output_dir: Optional[str] = None) -> dict[str, object]:
    root = Path(output_dir or get_config().download_dir)
    if not root.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "输出目录不存在"},
        )

    for manifest_path in root.glob("*/manifest.json"):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("course_id") == course_id:
            return {"ok": True, "manifest": payload}

    raise HTTPException(
        status_code=404,
        detail={"code": "not_found", "message": "manifest 不存在"},
    )


@app.post("/notebooks/upload")
def upload_files(req: UploadRequest) -> dict[str, object]:
    client = NotebookLMAPIClient(storage_state=req.storage_state)
    success = 0
    failed = 0
    try:
        for file_path in req.files:
            if client.upload_file(req.notebook_id, file_path):
                success += 1
            else:
                failed += 1
    finally:
        client.close()

    return {"ok": failed == 0, "success": success, "failed": failed, "total": len(req.files)}


def main() -> None:
    import uvicorn

    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=False)
