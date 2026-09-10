from fastapi import FastAPI
from apps.api.routes import incidents, investigations
from apps.api.database import init_db

app = FastAPI(
    title="Bob Reliability Engineer",
    description="Software Reliability Intelligence Layer for IBM Bob",
    version="0.1.0",
)

app.include_router(incidents.router, prefix="/api/incidents", tags=["incidents"])
app.include_router(investigations.router, prefix="/api/investigations", tags=["investigations"])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {"message": "Bob Reliability Engineer API", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
