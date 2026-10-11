from pathlib import Path
import secrets
import base64
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if not path.exists():
    content=(root/'.env.example').read_text().replace('GENERATE_SESSION_SECRET',secrets.token_urlsafe(48)).replace('GENERATE_ENCRYPTION_KEY',base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    path.write_text(content); path.chmod(0o600)
print('Configurazione locale pronta. Credenziali provider non configurate; invii reali disattivati.')
