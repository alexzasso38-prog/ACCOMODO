"""Periodic simulation dispatcher and explicitly enabled Meta test outbox."""
import time
import logging
from sqlalchemy import select
from app.db import transaction
from app.domain.models import VenueRoute
from app.workers.tasks import process_tenant
from app.providers.meta_demo import process_outbox
next_simulation = 0
while True:
    try:
        if time.monotonic() >= next_simulation:
            with transaction() as db:
                tenants = set(db.scalars(select(VenueRoute.tenant_id)).all())
            for tenant in tenants:
                process_tenant(tenant)
            next_simulation = time.monotonic() + 30
        process_outbox()
    except Exception as exc:
        # No exception strings or SQL parameters in logs.
        logging.error('Elaborazione demo da riprovare: %s', type(exc).__name__)
    time.sleep(2)
