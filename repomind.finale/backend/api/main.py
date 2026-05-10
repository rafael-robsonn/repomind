"""
FastAPI - secure config, validation on startup, knowledge graph endpoint.
Serves frontend static files when bundled (EXE mode).
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import uuid
from queue import Queue, Empty
from threading import Thread

from config import validate_startup, mask_secrets, Config, ConfigError
from agents.indexer import index_repository, get_repo_meta, list_indexed_repos, load_vectorstore
from agents.pipeline import run_review_pipeline

def get_frontend_path() -> Optional[Path]:
    """Retorna path do frontend buildado. None se não existir."""
    if hasattr(sys, "_MEIPASS"):
        # Bundled mode (PyInstaller)
        candidate = Path(sys._MEIPASS) / "frontend_dist"
    else:
        # Dev mode
        candidate = Path(__file__).parent.parent.parent / "frontend" / "dist"

    return candidate if candidate.exists() else None


app = FastAPI(title="RepoMind API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        result = validate_startup()
        print(f"\n[RepoMind] Config OK")
        print(f"  Provider: {result['info']['provider']}")
        print(f"  Model:    {result['info']['model']}")
        print(f"  Host:     {result['info']['base_url_host']}")
        for w in result.get("warnings", []):
            print(f"  WARNING: {w}")
        print()
    except ConfigError as e:
        print(f"\n[RepoMind] CONFIG ERROR:\n{e}\n")
        raise



class JobManager:
    def __init__(self):
        self.jobs: dict[str, dict] = {}

    def create(self, kind: str) -> str:
        job_id = f"{kind}_{uuid.uuid4().hex[:8]}"
        self.jobs[job_id] = {
            "status": "running",
            "kind": kind,
            "events": [],
            "queue": Queue(),
            "result": None,
            "error": None,
        }
        return job_id

    def emit(self, job_id: str, event_type: str, data: dict):
        if job_id not in self.jobs:
            return
        safe_data = self._sanitize(data)
        evt = {"type": event_type, "data": safe_data}
        self.jobs[job_id]["events"].append(evt)
        self.jobs[job_id]["queue"].put(evt)

    def _sanitize(self, obj):
        if isinstance(obj, str):
            return mask_secrets(obj)
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        return obj

    def complete(self, job_id: str, result: dict):
        if job_id not in self.jobs:
            return
        safe = self._sanitize(result)
        self.jobs[job_id]["status"] = "done"
        self.jobs[job_id]["result"] = safe
        self.jobs[job_id]["queue"].put({"type": "complete", "data": safe})

    def fail(self, job_id: str, error: str):
        if job_id not in self.jobs:
            return
        safe_err = mask_secrets(error)
        self.jobs[job_id]["status"] = "error"
        self.jobs[job_id]["error"] = safe_err
        self.jobs[job_id]["queue"].put({"type": "error", "data": {"error": safe_err}})

    def get(self, job_id: str) -> Optional[dict]:
        j = self.jobs.get(job_id)
        if not j:
            return None
        return {k: v for k, v in j.items() if k != "queue"}


jobs = JobManager()


# ── Schemas ──────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    repo_path: str
    name: Optional[str] = None


class ReviewRequest(BaseModel):
    repo_id: str
    diff: str
    lang: Optional[str] = "en"


class PDFExportRequest(BaseModel):
    markdown: str
    title: Optional[str] = "RepoMind Review"


# ── API Endpoints (under /api prefix to avoid conflict with frontend) ────

@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "active_jobs": len([j for j in jobs.jobs.values() if j["status"] == "running"]),
    }


@app.get("/api/config")
@app.get("/config")
def get_config():
    return Config.public_info()


@app.get("/api/repos")
@app.get("/repos")
def list_repos():
    repos = list_indexed_repos()
    return {
        "repos": [{
            "id": r["collection"],
            "path": r["repo_path"],
            "files": r["files_indexed"],
            "code_files": r["code_files"],
            "chunks": r["chunks"],
            "profile": r["profile"],
            "graph": r["graph_info"],
        } for r in repos]
    }


@app.get("/api/repos/{repo_id}")
@app.get("/repos/{repo_id}")
def get_repo(repo_id: str):
    meta = get_repo_meta(repo_id)
    if not meta:
        raise HTTPException(404, "Repo não indexado")
    return meta


@app.get("/api/repos/{repo_id}/graph")
@app.get("/repos/{repo_id}/graph")
def get_repo_graph(repo_id: str):
    meta = get_repo_meta(repo_id)
    if not meta:
        raise HTTPException(404, "Repo não indexado")

    graph_data = meta.get("graph_full")
    if graph_data:
        return graph_data

    return {"nodes": [], "edges": [], "stats": meta.get("graph_info", {})}


@app.post("/api/repos/index")
@app.post("/repos/index")
async def index_repo(req: IndexRequest):
    job_id = jobs.create("index")

    def do_index():
        import traceback
        try:
            def emitter(stage: str, data: dict):
                # Print + emit pro WS - garante que aparece no terminal
                msg = data.get("message", "")
                print(f"[INDEX:{stage}] {msg}")
                jobs.emit(job_id, f"index:{stage}", data)

            print(f"[INDEX] Iniciando job {job_id} para: {req.repo_path}")
            result = index_repository(
                req.repo_path,
                collection_name=req.name,
                on_progress=emitter,
            )
            print(f"[INDEX] Job {job_id} completo: {result.get('files_indexed')} arquivos")
            jobs.complete(job_id, result)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"\n[INDEX ERROR] Job {job_id} falhou:")
            print(tb)
            print()
            jobs.fail(job_id, f"{type(e).__name__}: {str(e)}\n\nVer traceback no terminal do backend.")

    Thread(target=do_index, daemon=True).start()
    return {"job_id": job_id}


@app.post("/api/review")
@app.post("/review")
async def review(req: ReviewRequest):
    meta = get_repo_meta(req.repo_id)
    if not meta:
        raise HTTPException(404, "Repo não indexado")

    job_id = jobs.create("review")

    def do_review():
        import traceback
        try:
            def emitter(stage: str, data: dict):
                print(f"[REVIEW:{stage}] {data}")
                jobs.emit(job_id, stage, data)

            print(f"[REVIEW] Iniciando job {job_id} para repo: {req.repo_id} (lang={req.lang})")
            result = run_review_pipeline(
                diff=req.diff,
                collection_name=meta["collection"],
                project_profile=meta["profile"],
                emitter=emitter,
                lang=req.lang or "en",
            )
            if "error" in result:
                print(f"[REVIEW ERROR] {result['error']}")
                jobs.fail(job_id, result["error"])
            else:
                print(f"[REVIEW] Job {job_id} completo")
                jobs.complete(job_id, result)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"\n[REVIEW ERROR] Job {job_id} falhou:")
            print(tb)
            print()
            jobs.fail(job_id, f"{type(e).__name__}: {str(e)}\n\nVer traceback no terminal do backend.")

    Thread(target=do_review, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return job


# ── PDF Export ───────────────────────────────────────────────────────────

@app.post("/api/export/pdf")
@app.post("/export/pdf")
def export_pdf(req: PDFExportRequest):
    try:
        from agents.pdf_export import render_to_pdf
        pdf_bytes = render_to_pdf(req.markdown, req.title or "RepoMind Review")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="review.pdf"'},
        )
    except RuntimeError as e:
        raise HTTPException(501, f"PDF generation not available: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"PDF generation failed: {e}")


# ── WebSocket ────────────────────────────────────────────────────────────

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job(ws: WebSocket, job_id: str):
    await ws.accept()

    job = jobs.jobs.get(job_id)
    if not job:
        await ws.send_json({"type": "error", "data": {"error": "Job não encontrado"}})
        await ws.close()
        return

    for evt in job["events"]:
        await ws.send_json(evt)

    if job["status"] != "running":
        await ws.send_json({
            "type": "complete",
            "data": job.get("result") or {"error": job.get("error")}
        })
        await ws.close()
        return

    queue = job["queue"]

    try:
        while True:
            try:
                evt = queue.get(timeout=0.5)
                await ws.send_json(evt)
                if evt["type"] in ("complete", "error"):
                    break
            except Empty:
                if job["status"] in ("done", "error"):
                    final_evt = {
                        "type": "complete" if job["status"] == "done" else "error",
                        "data": job.get("result") or {"error": job.get("error", "")}
                    }
                    await ws.send_json(final_evt)
                    break
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS ERROR] {type(e).__name__}: {e}")
    finally:
        try:
            await ws.close()
        except Exception:
            pass


# ── Frontend static serving (deve ficar POR ÚLTIMO) ──────────────────────

_frontend_path = get_frontend_path()
if _frontend_path:
    print(f"[RepoMind] Servindo frontend de: {_frontend_path}")
    app.mount("/", StaticFiles(directory=str(_frontend_path), html=True), name="frontend")
