"""One periodic dispatcher for the small hosted demo; no real sending."""
import time
import logging
from sqlalchemy import select
from app.db import transaction
from app.domain.models import VenueRoute
from app.workers.tasks import process_tenant
while True:
    try:
        with transaction() as db:
            tenants = set(db.scalars(select(VenueRoute.tenant_id)).all())
        for tenant in tenants:
            process_tenant(tenant)
    except Exception:
        logging.exception('Elaborazione demo da riprovare')
    time.sleep(30)
