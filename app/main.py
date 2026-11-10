"""PawSOS Goa: the one FastAPI service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import models  # noqa: F401  (registers every table)
from app.channels import media, simulator, whatsapp
from app.channels.routed import RoutedChannel
from app.config import get_settings
from app.dashboard import routes as dashboard
from app.jobs import scheduler


def create_app() -> FastAPI:
    settings = get_settings()

    # The simulator is always there: it plays the placeholder teams, and it is
    # the demo fallback. Real WhatsApp is added when CHANNEL=whatsapp and its
    # four settings are filled in. `channel` sends each reply the right way.
    sim_channel = simulator.SimulatorAdapter()
    wa_channel = whatsapp.from_settings()
    channel = RoutedChannel(sim_channel, wa_channel)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Runs when the server starts and stops (not during tests that skip startup).
        jobs = scheduler.start(channel)
        yield
        jobs.shutdown(wait=False)
        if wa_channel is not None:
            await wa_channel.close()

    app = FastAPI(title="PawSOS Goa", lifespan=lifespan)
    app.state.simulator = sim_channel
    app.state.whatsapp = wa_channel
    app.state.channel = channel
    app.include_router(simulator.build_router(sim_channel, channel))
    app.include_router(whatsapp.build_router(wa_channel, channel))
    app.include_router(dashboard.build_router())

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {"status": "ok", "channel": settings.channel, "whatsapp_ready": wa_channel is not None}

    @app.get("/media/{name}")
    def get_media(name: str) -> FileResponse:
        path = media.path_for(name)
        if path is None:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path)

    return app


app = create_app()
