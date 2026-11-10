"""PawSOS Goa: the one FastAPI service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.channels import media, simulator
from app.config import get_settings
from app.jobs import scheduler


def create_app() -> FastAPI:
    settings = get_settings()

    # The simulator is always mounted: it is the demo fallback even when
    # real WhatsApp is the active channel (slice 9).
    sim_channel = simulator.SimulatorAdapter()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Runs when the server starts and stops (not during tests that skip startup).
        jobs = scheduler.start(sim_channel)
        yield
        jobs.shutdown(wait=False)

    app = FastAPI(title="PawSOS Goa", lifespan=lifespan)
    app.state.simulator = sim_channel
    app.include_router(simulator.build_router(sim_channel))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "channel": settings.channel}

    @app.get("/media/{name}")
    def get_media(name: str) -> FileResponse:
        path = media.path_for(name)
        if path is None:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path)

    return app


app = create_app()
