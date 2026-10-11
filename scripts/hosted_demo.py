"""Self-contained, ephemeral Render demo. Never a production deployment."""
import os
import secrets
import signal
import subprocess
import sys
import time
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet

PG = '/usr/lib/postgresql/15/bin/'
processes = []

def run(args, **kwargs):
    subprocess.run(args, check=True, **kwargs)

def start(args):
    p = subprocess.Popen(args)
    processes.append(p)
    return p

def stop(*_):
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
    for p in reversed(processes):
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

try:
    password = os.getenv('DEMO_STAFF_PASSWORD', '')
    if len(password) < 16:
        raise RuntimeError('Impostare DEMO_STAFF_PASSWORD con almeno 16 caratteri nelle variabili Render.')
    hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', '')
    base = os.getenv('APP_BASE_URL') or ('https://' + hostname if hostname else '')
    if not base.startswith('https://'):
        raise RuntimeError('La demo online richiede APP_BASE_URL HTTPS o RENDER_EXTERNAL_HOSTNAME.')
    owner = secrets.token_hex(24)
    app_password = secrets.token_hex(24)
    os.environ.update({
        'APP_ENV': 'demo', 'DEMO_MODE': 'true', 'HOSTED_DEMO': 'true',
        'SEND_REAL_MESSAGES': 'false', 'APP_BASE_URL': base.rstrip('/'),
        'ALLOWED_WIDGET_ORIGINS': base.rstrip('/'),
        'DATABASE_URL': f'postgresql+psycopg://tavolo_app:{app_password}@127.0.0.1:5432/tavolo_demo',
        'MIGRATION_DATABASE_URL': f'postgresql+psycopg://accomodo_owner:{owner}@127.0.0.1:5432/tavolo_demo',
        'REDIS_URL': 'redis://127.0.0.1:6379/0',
        'SESSION_SECRET': secrets.token_urlsafe(48),
        'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'DEMO_ACCESS_PATH': '/work/demo-access.json',
        'DEMO_EMAIL_DOMAIN': 'accomodo.test',
    })
    data = Path(tempfile.mkdtemp(prefix='postgres-demo-', dir='/work'))
    pwfile = Path('/work/pg-password')
    pwfile.write_text(owner)
    pwfile.chmod(0o600)
    run([PG+'initdb', '-D', str(data), '-U', 'accomodo_owner', '-A', 'scram-sha-256', '--pwfile', str(pwfile)], stdout=subprocess.DEVNULL)
    pwfile.unlink()
    start([PG+'postgres', '-D', str(data), '-h', '127.0.0.1', '-k', '/work',
           '-c', 'shared_buffers=16MB', '-c', 'max_connections=40', '-c', 'work_mem=1MB',
           '-c', 'maintenance_work_mem=16MB', '-c', 'max_wal_size=64MB'])
    os.environ['PGPASSWORD'] = owner
    for _ in range(60):
        if subprocess.run([PG+'pg_isready', '-h', '127.0.0.1', '-U', 'accomodo_owner'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Database demo non pronto.')
    sql = f"CREATE ROLE tavolo_app LOGIN PASSWORD '{app_password}' NOSUPERUSER NOBYPASSRLS; CREATE DATABASE tavolo_demo;"
    run([PG+'psql', '-h', '127.0.0.1', '-U', 'accomodo_owner', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1'], input=sql, text=True, stdout=subprocess.DEVNULL)
    os.environ.pop('PGPASSWORD', None)
    start(['redis-server', '--bind', '127.0.0.1', '--save', '', '--appendonly', 'no', '--maxmemory', '24mb', '--maxmemory-policy', 'noeviction'])
    run([sys.executable, '-m', 'alembic', 'upgrade', 'head'])
    run([sys.executable, '-m', 'app.seed'])
    start([sys.executable, '/app/hosting/hosted_worker.py'])
    start([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0',
           '--port', os.getenv('PORT', '10000'), '--no-access-log', '--proxy-headers', '--forwarded-allow-ips', '*'])
    print('Accomodo DEMO pronta: staff1@accomodo.test e staff2@accomodo.test. Password dalla variabile privata Render. Dati temporanei.', flush=True)
    while True:
        time.sleep(1)
        if any(p.poll() is not None for p in processes):
            raise RuntimeError('Un processo demo si è arrestato; il servizio deve essere ricreato.')
except Exception as exc:
    print(f'Avvio demo fallito: {exc}', file=sys.stderr, flush=True)
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
    sys.exit(1)
