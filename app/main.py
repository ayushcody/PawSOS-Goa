"""PawSOS Goa: the one FastAPI service."""

from fastapi import FastAPI

from app.channels import simulator
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

    return app


app = create_app()
