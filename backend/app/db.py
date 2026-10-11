import os
from contextlib import contextmanager
from uuid import UUID
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
engine = create_engine(settings.db_url, pool_size=4 if settings.demo and os.getenv('HOSTED_DEMO')=='true' else 15, max_overflow=6 if os.getenv('HOSTED_DEMO')=='true' else 50, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

@contextmanager
def transaction(tenant_id=None):
    with SessionLocal.begin() as db:
        if tenant_id:
            tenant = str(UUID(str(tenant_id)))
            db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {'tenant': tenant})
        yield db

def tenant_lock(db, venue_id):
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': str(venue_id)})
