from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.config.settings import FRONTEND_DIST_DIR
from backend.logging_setup import logger
from backend.services.job_manager import job_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager.start()
    logger.info("AI Voice Studio backend started (CPU mode).")
    yield
    logger.info("AI Voice Studio backend shutting down.")


app = FastAPI(title="AI Voice Studio", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Check logs/app.log for details."},
    )


app.include_router(api_router)

if FRONTEND_DIST_DIR.exists():
    app.mount(
        "/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend"
    )
else:
    logger.warning(
        "Frontend build not found at %s - run `npm run build` in frontend/ "
        "or use `npm run dev` for local development.",
        FRONTEND_DIST_DIR,
    )
