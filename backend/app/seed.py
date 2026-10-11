"""Idempotent seed for a database labelled as demo; never used in production."""
import os,json,secrets
from pathlib import Path
from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session as DBSession
from app.domain.models import *
from app.config import settings
from app.auth.security import hasher,crypt
from app.services.reservations import create
from app.api.schemas import Booking
import pyotp

def main():
    if not settings.demo or settings.env!='demo': raise RuntimeError('Seed consentito soltanto in demo.')
    url=os.getenv('MIGRATION_DATABASE_URL','')
    if 'tavolo_demo' not in url: raise RuntimeError('Usare il DB tavolo_demo esplicitamente selezionato.')
    output=Path(os.getenv('DEMO_ACCESS_PATH',str(Path(__file__).resolve().parents[2]/'work/demo-access.json'))); output.parent.mkdir(exist_ok=True)
    with DBSession(create_engine(url)) as db,db.begin():
        for code,setup,monthly,whatsapp,minutes in [('Start',29000,9900,300,100),('Concierge',49000,14900,1000,300),('Voice',79000,24900,1000,300)]:
            if not db.scalar(select(BillingPlan.id).where(BillingPlan.code==code,BillingPlan.version==1)):
                db.add(BillingPlan(code=code,version=1,monthly_net=monthly,setup_net=setup,tax_rate_default=22,limits_json={'whatsapp_messages':whatsapp,'telephony_minutes':minutes},effective_from=now()))
        db.flush()
        if db.scalar(select(User.id).limit(1)):
            print('Demo già inizializzata. Credenziali locali in work/demo-access.json.'); return
        accounts=[]
        for index,(name,slug) in enumerate([('Osteria del Porto · DEMO','osteria-demo'),('Giardino delle Spezie · DEMO','giardino-demo')]):
            tenant=Tenant(name=name,slug=slug); db.add(tenant); db.flush()
            db.execute(text("SELECT set_config('app.tenant_id', :t, true)"),{'t':str(tenant.id)})
            v=Venue(tenant_id=tenant.id,name=name,slug=slug,booking_mode='automatic' if index==0 else 'manual',menu_url='/menu-demo',directions_url='https://www.openstreetmap.org',deposit_cents=0)
            db.add(v); db.flush()
            plan=db.scalar(select(BillingPlan).where(BillingPlan.code=='Start',BillingPlan.version==1))
            db.add(Subscription(tenant_id=tenant.id,venue_id=v.id,plan_version_id=plan.id,status='trial',trial_start=now(),trial_end=now()+timedelta(days=14)))
            db.add(VenueRoute(slug=slug,tenant_id=tenant.id,venue_id=v.id))
            room=Room(tenant_id=tenant.id,venue_id=v.id,name='Sala principale'); db.add(room); db.flush()
            tables=[]
            for num,capacity in enumerate([2,2,4,4,6]):
                r=Resource(tenant_id=tenant.id,venue_id=v.id,room_id=room.id,name=f'T{num+1:02}',min_guests=1,max_guests=capacity); db.add(r); db.flush(); tables.append(r)
            combo=ResourceCombination(tenant_id=tenant.id,venue_id=v.id,name='T01 + T02',min_guests=3,max_guests=4); db.add(combo); db.flush()
            for r in tables[:2]: db.add(CombinationMember(tenant_id=tenant.id,venue_id=v.id,combination_id=combo.id,resource_id=r.id))
            for day in range(7):
                for start,end in [(time(12),time(15)),(time(19),time(23,30))]:
                    db.add(ServiceSchedule(tenant_id=tenant.id,venue_id=v.id,weekday=day,local_start_time=start,local_end_time=end,slot_interval_minutes=30,duration_minutes=90,max_arrivals_per_slot=4))
            for role in ['staff','manager']:
                pwd=secrets.token_urlsafe(14); email=f'{role}{index+1}@tavolo.test'; mfa=pyotp.random_base32() if role=='manager' else None
                u=User(email=email,password_hash=hasher.hash(pwd),mfa_config=crypt(mfa) if mfa else None); db.add(u); db.flush()
                db.add(Membership(user_id=u.id,tenant_id=tenant.id,venue_id=v.id,role=role))
                accounts.append({'email':email,'password':pwd,'role':role,'mfa_secret':mfa,'restaurant':name,'slug':slug})
            db.flush()
            tomorrow=datetime.now(ZoneInfo(v.timezone)).date()+timedelta(days=1)
            for num,(hour,minute,party) in enumerate([(19,0,2),(19,30,4),(20,0,3)]):
                data=Booking(starts_at=datetime.combine(tomorrow,time(hour,minute),ZoneInfo(v.timezone)),party_size=party,name=f'Ospite sintetico {num+1}',email=f'ospite{num+1}@example.test',privacy_ack=True)
                create(db,v,data)
        output.write_text(json.dumps(accounts,indent=2,ensure_ascii=False)); output.chmod(0o600)
    print('Due ristoranti DEMO creati. Account casuali in work/demo-access.json (non in Git).')
if __name__=='__main__': main()
