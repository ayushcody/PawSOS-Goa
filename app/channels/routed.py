"""Send each message down the right channel.

Invented numbers (the simulator's citizens, the placeholder teams, demo
reporters) all start with +91000000, which no real Indian number does. Those
always go to the simulator. Every other number is a real phone and goes to
WhatsApp, when WhatsApp is set up.

This is what lets one demo mix both: a real phone reports on WhatsApp, a
placeholder team accepts in the simulator, and the status update goes back
to the real phone.

A Telegram person has no number: their address is "tg:<chat id>", and it goes
to Telegram when Telegram is set up.
"""

from app.channels.base import Button, ChannelAdapter, Outbound

SIMULATED_PREFIX = "+91000000"
TELEGRAM_PREFIX = "tg:"


def is_simulated(number: str) -> bool:
    return number.startswith(SIMULATED_PREFIX)


class RoutedChannel(ChannelAdapter):
    name = "routed"

    def __init__(
        self,
        simulator: ChannelAdapter,
        whatsapp: ChannelAdapter | None = None,
        telegram: ChannelAdapter | None = None,
    ) -> None:
        self.simulator = simulator
        self.whatsapp = whatsapp
        self.telegram = telegram

    def channel_for(self, number: str) -> ChannelAdapter:
        if number.startswith(TELEGRAM_PREFIX):
            # Never WhatsApp: a chat id is not a phone number.
            return self.telegram or self.simulator
        if self.whatsapp is None or is_simulated(number):
            return self.simulator
        return self.whatsapp

    async def send_text(self, to_number: str, text: str) -> None:
        await self.channel_for(to_number).send_text(to_number, text)

    async def send_buttons(self, to_number: str, text: str, buttons: list[Button]) -> None:
        await self.channel_for(to_number).send_buttons(to_number, text, buttons)

    async def send_image(self, to_number: str, media_name: str) -> None:
        await self.channel_for(to_number).send_image(to_number, media_name)

    async def send_location_request(self, to_number: str, text: str) -> None:
        await self.channel_for(to_number).send_location_request(to_number, text)

    async def send(self, message: Outbound) -> None:
        # Whole messages go to one channel, so WhatsApp can fall back to a template.
        await self.channel_for(message.to).send(message)
