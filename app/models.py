"""Every database table, registered in one import.

Tables point at each other across modules (a case has a zone, a camp has a
zone), so SQLAlchemy must know about all of them before any is used. Anything
that starts the app, runs migrations or loads seed data imports this module.
"""

from app import contacts
from app.booking import models as booking_models
from app.cases import bites, models
from app.routing import models as routing_models

__all__ = ["bites", "booking_models", "contacts", "models", "routing_models"]
