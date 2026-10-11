"""Encrypted local backup/restore drill into a new, dedicated disposable database."""
import os,subprocess,hashlib,json
from pathlib import Path
from cryptography.fernet import Fernet
root=Path(__file__).resolve().parents[1]
work=root/'work';work.mkdir(exist_ok=True)
cmd=['docker','--host=unix:///var/run/docker.sock']
# Fixed local development container; never accepts a production connection string.
def run(args,input=None):return subprocess.run(cmd+args,input=input,check=True,capture_output=True).stdout
raw=run(['exec','tavolo-postgres','pg_dump','-U','tavolo_owner','-d','tavolo_demo','-Fc'])
key=Fernet.generate_key();encrypted=Fernet(key).encrypt(raw);(work/'backup-demo.dump.enc').write_bytes(encrypted);(work/'backup-demo.key').write_bytes(key);(work/'backup-demo.key').chmod(0o600)
run(['exec','tavolo-postgres','createdb','-U','tavolo_owner','tavolo_demo_restore'])
run(['exec','-i','tavolo-postgres','pg_restore','-U','tavolo_owner','-d','tavolo_demo_restore'],input=Fernet(key).decrypt(encrypted))
q='SELECT count(*) FROM reservations;'
a=run(['exec','tavolo-postgres','psql','-U','tavolo_owner','-d','tavolo_demo','-tAc',q]).decode().strip()
b=run(['exec','tavolo-postgres','psql','-U','tavolo_owner','-d','tavolo_demo_restore','-tAc',q]).decode().strip()
assert a==b
print(json.dumps({'encrypted':True,'restore_database':'tavolo_demo_restore','reservation_count_matches':True,'reservation_count':int(a),'sha256_plaintext':hashlib.sha256(raw).hexdigest()}))
