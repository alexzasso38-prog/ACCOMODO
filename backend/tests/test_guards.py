import subprocess,os
from pathlib import Path
from conftest import payload,sign_in

def test_staff_does_not_need_to_invent_a_guest_contact(client,tenants):
    h=sign_in(client)
    b=payload(email=None,phone=None)
    r=client.post('/api/admin/reservations',json=b,headers=h)
    assert r.status_code==201,r.text
    assert r.json()['reservation']['status']=='CONFIRMED'
    from app.db import transaction
    from app.domain.models import OutboxEvent
    from sqlalchemy import select
    with transaction(tenants[0]['tenant']) as db:assert db.scalar(select(OutboxEvent)) is None

def test_production_fail_fast_and_reset_guard(tmp_path):
    env=os.environ.copy();env.update(APP_ENV='production',DEMO_MODE='false',SESSION_SECRET='short')
    result=subprocess.run([os.sys.executable,'-c','from app.config import settings'],capture_output=True,text=True,env=env)
    assert result.returncode!=0 and 'Produzione' in result.stderr
    source=Path(__file__).resolve().parents[2]/'scripts/reset_demo.py'
    if not source.exists():source=Path('/scripts/reset_demo.py')
    scripts=tmp_path/'scripts';scripts.mkdir();(scripts/'reset_demo.py').write_text(source.read_text())
    (tmp_path/'.env').write_text('APP_ENV=production\nDEMO_MODE=false\nSEND_REAL_MESSAGES=true\n')
    result=subprocess.run([os.sys.executable,str(scripts/'reset_demo.py')],capture_output=True,text=True)
    assert result.returncode!=0 and 'Reset rifiutato' in result.stderr
