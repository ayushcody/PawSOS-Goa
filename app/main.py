"""PawSOS Goa: the one FastAPI service."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.channels import media, simulator
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="PawSOS Goa")

    # The simulator is always mounted: it is the demo fallback even when
    # real WhatsApp is the active channel (slice 9).
    sim_channel = simulator.SimulatorAdapter()
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
