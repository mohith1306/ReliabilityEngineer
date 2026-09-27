from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.routes import approvals, demo, incidents, insights, investigations, loop, risk
from apps.api.database import init_db

WEB = Path(__file__).resolve().parents[1] / "web"
WALKTHROUGH = Path(__file__).resolve().parents[2] / "docs" / "submission" / "demo_walkthrough.html"

app = FastAPI(
    title="Bob Reliability Engineer",
    description="Software Reliability Intelligence Layer for IBM Bob",
    version="0.2.0",
)

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(loop.router, prefix="/api/incidents", tags=["loop"])
app.include_router(approvals.router, prefix="/api/incidents", tags=["approvals"])
app.include_router(risk.router, prefix="/api/incidents", tags=["risk"])
app.include_router(investigations.router, prefix="/api/investigations", tags=["investigations"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(demo.router, prefix="/api/demo", tags=["demo"])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", include_in_schema=False)
def dashboard():
    """The dashboard. The JSON API lives under /api and is documented at /docs."""
    # no-cache: a browser that kept an older copy ran stale JavaScript after the approve-call fix and showed the old bug
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/walkthrough", include_in_schema=False)
def walkthrough():
    """The video script beside the real dashboard. Served from the same origin as `/` so the page can embed the dashboard
    and read /api/system to warn when its LIVE/SIMULATED wording disagrees with what this server is running."""
    return FileResponse(WALKTHROUGH, headers={"Cache-Control": "no-cache"})


if (WEB / "static").is_dir():
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


@app.get("/health")
def health():
    return {"status": "healthy"}
