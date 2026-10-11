import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

class Settings:
    env = os.getenv('APP_ENV', 'demo')
    demo = os.getenv('DEMO_MODE', 'true').lower() == 'true'
    real_messages = os.getenv('SEND_REAL_MESSAGES', 'false').lower() == 'true'
    db_url = os.getenv('DATABASE_URL', 'postgresql+psycopg://tavolo_app:local-demo-app@127.0.0.1:55432/tavolo_demo')
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:56379/0')
    base_url = os.getenv('APP_BASE_URL', 'http://localhost:5174')
    secret = os.getenv('SESSION_SECRET', '')
    encryption_key = os.getenv('ENCRYPTION_KEY', '')
    origins = os.getenv('ALLOWED_WIDGET_ORIGINS', 'http://localhost:5174').split(',')

    def validate(self):
        if not self.db_url.startswith('postgresql'):
            raise RuntimeError('Accomodo richiede PostgreSQL; SQLite non è supportato.')
        if self.demo and self.real_messages:
            raise RuntimeError('La demo non può inviare messaggi reali.')
        if self.env != 'demo':
            if self.demo or len(self.secret) < 40 or not self.encryption_key or not self.base_url.startswith('https://'):
                raise RuntimeError('Produzione: HTTPS, segreti robusti e DEMO_MODE=false obbligatori.')
            # Operational enablement requires the remaining acceptance checks, not just credentials.
            raise RuntimeError('Attivazione produzione bloccata: completare docs/ACCEPTANCE.md prima di rimuovere questo gate.')
settings = Settings()
settings.validate()
