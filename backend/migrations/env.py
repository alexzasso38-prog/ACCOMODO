from alembic import context
from sqlalchemy import create_engine
from app.domain.models import Base
from app.config import settings
import os
url = os.getenv('MIGRATION_DATABASE_URL', settings.db_url)
with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction(): context.run_migrations()
