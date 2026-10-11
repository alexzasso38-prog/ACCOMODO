"""Only the exact local Compose demo; no arbitrary URL or volume removal."""
import subprocess,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
if env.get('APP_ENV')!='demo' or env.get('DEMO_MODE')!='true' or env.get('SEND_REAL_MESSAGES')!='false':raise SystemExit('Reset rifiutato: ambiente non demo.')
expected='postgresql+psycopg://tavolo_app:local-demo-app@127.0.0.1:55432/tavolo_demo'
if env.get('DATABASE_URL')!=expected:raise SystemExit('Reset rifiutato: configurazione database diversa dalla demo prevista.')
# Only the fixed Compose db service and database; existing Agro Sales AI is never touched.
safe_env={k:v for k,v in os.environ.items() if k not in {'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH','COMPOSE_FILE','COMPOSE_PROJECT_NAME'}}
compose=['docker','--host=unix:///var/run/docker.sock','compose','-f',str(root/'compose.yaml'),'-p','tavolo-demo']
def run(args):subprocess.run(compose+args,cwd=root,env=safe_env,check=True)
run(['stop','api','worker','scheduler','frontend'])
run(['exec','-T','db','psql','-U','tavolo_owner','-d','postgres','-c','DROP DATABASE tavolo_demo WITH (FORCE)'])
run(['exec','-T','db','createdb','-U','tavolo_owner','tavolo_demo'])
(root/'work/demo-access.json').unlink(missing_ok=True)
run(['run','--rm','migrate'])
run(['run','--rm','--user',f'{os.getuid()}:{os.getgid()}','seed'])
run(['up','-d','db','redis','migrate','api','worker','scheduler','frontend'])
