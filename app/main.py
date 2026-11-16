"""PawSOS Goa: the one FastAPI service."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import models  # noqa: F401  (registers every table)
from app.channels import media, simulator, telegram, whatsapp
from app.channels.routed import RoutedChannel
from app.config import get_settings
from app.dashboard import routes as dashboard
from app.jobs import scheduler


def create_app() -> FastAPI:
    settings = get_settings()

    # The simulator is always there: it plays the placeholder teams, and it is
    # the demo fallback. Real WhatsApp is added when CHANNEL=whatsapp and its
    # four settings are filled in; Telegram when CHANNEL=telegram and its bot
    # token is set. `channel` sends each reply the right way.
    sim_channel = simulator.SimulatorAdapter()
    wa_channel = whatsapp.from_settings()
    tg_channel = telegram.from_settings()
    channel = RoutedChannel(sim_channel, wa_channel, tg_channel)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Runs when the server starts and stops (not during tests that skip startup).
        jobs = scheduler.start(channel)
        # Telegram has no webhook here: one background task keeps asking it for messages.
        poller = None
        if tg_channel is not None:
            poller = asyncio.create_task(telegram.TelegramReceiver(tg_channel, channel).run())
        yield
        if poller is not None:
            poller.cancel()
            await tg_channel.close()
        jobs.shutdown(wait=False)
        if wa_channel is not None:
            await wa_channel.close()

    app = FastAPI(title="PawSOS Goa", lifespan=lifespan)
    app.state.simulator = sim_channel
    app.state.whatsapp = wa_channel
    app.state.telegram = tg_channel
    app.state.channel = channel
    app.include_router(simulator.build_router(sim_channel, channel))
    app.include_router(whatsapp.build_router(wa_channel, channel))
    app.include_router(dashboard.build_router(channel))

    @app.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "channel": settings.channel,
            "whatsapp_ready": wa_channel is not None,
            "telegram_ready": tg_channel is not None,
        }

    @app.get("/media/{name}")
    def get_media(name: str) -> FileResponse:
        path = media.path_for(name)
        if path is None:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path)

    return app


app = create_app()
