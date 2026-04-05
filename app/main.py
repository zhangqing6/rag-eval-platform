from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import compare, datasets, playground, runs

_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "data").mkdir(parents=True, exist_ok=True)
init_db()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RAG Eval Platform",
    description="Offline evaluation and regression for RAG / Agent HTTP endpoints",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(runs.router)
app.include_router(compare.router)
app.include_router(playground.router)

static_dir = _ROOT / "static"
if static_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/classic.html")
def classic_page():
    p = static_dir / "classic.html"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="classic.html not found")
    return FileResponse(p)


@app.get("/")
def root():
    index = static_dir / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {
        "service": "rag-eval-platform",
        "docs": "/docs",
        "ui": "/ui/" if static_dir.is_dir() else None,
    }
