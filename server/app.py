"""
FastAPI application for the Email Triage Assistant environment.

Usage:
    python -m server.app
"""

from pathlib import Path

try:
    from openenv.core.env_server.http_server import create_app
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "openenv-core is required for the web interface. Install project dependencies first."
    ) from exc
from fastapi.staticfiles import StaticFiles

from .email_triage_environment import OpenEnvEmailTriageEnvironment
from .models import EmailTriageAction, EmailTriageObservation
from .ui import router as ui_router

app = create_app(
    OpenEnvEmailTriageEnvironment,
    EmailTriageAction,
    EmailTriageObservation,
    env_name="email-triage-assistant",
    max_concurrent_envs=4,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
app.include_router(ui_router)


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
