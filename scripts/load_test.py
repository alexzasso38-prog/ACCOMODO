"""Local PostgreSQL availability benchmark, isolated test DB, 100 synthetic venues."""
import os,json,time,statistics,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,time as walltime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import settings
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from app.domain.models import Tenant,Venue,Room,Resource,ServiceSchedule
from app.db import transaction
from app.domain.availability import available_slots
from app.domain.models import now
if not settings.db_url.endswith('/tavolo_demo_test'):raise SystemExit('Benchmark consentito solo sul DB tavolo_demo_test.')
owner_url=os.environ.get('MIGRATION_DATABASE_URL','')
if not owner_url.endswith('/tavolo_demo_test'):raise SystemExit('Owner test richiesto.')
owner=create_engine(owner_url)
venues=[]
with Session(owner) as db,db.begin():
    # Add a benchmark cohort; do not remove unrelated rows.
    for i in range(100):
        slug='bench-'+str(i)
        tenant=db.scalar(select(Tenant).where(Tenant.slug==slug))
        if tenant:venue=db.scalar(select(Venue).where(Venue.tenant_id==tenant.id))
        else:
            tenant=Tenant(name='Benchmark DEMO',slug=slug);db.add(tenant);db.flush()
            venue=Venue(tenant_id=tenant.id,name='Benchmark DEMO',slug=slug,minimum_notice_minutes=0);db.add(venue);db.flush()
            room=Room(tenant_id=tenant.id,venue_id=venue.id,name='Sala');db.add(room);db.flush()
            for j in range(10):db.add(Resource(tenant_id=tenant.id,venue_id=venue.id,room_id=room.id,name=f'T{j}',min_guests=1,max_guests=4))
            for d in range(7):db.add(ServiceSchedule(tenant_id=tenant.id,venue_id=venue.id,weekday=d,local_start_time=walltime(19),local_end_time=walltime(23),slot_interval_minutes=30,duration_minutes=90))
        venues.append((tenant.id,venue.id))
day=datetime.now(ZoneInfo('Europe/Rome')).date()+timedelta(days=1)
def request(index):
    t,v=venues[index%100];started=time.perf_counter()
    with transaction(t) as db:slots=available_slots(db,db.get(Venue,v),day,2,now())
    assert len(slots)==6
    return (time.perf_counter()-started)*1000
# Pace 30 requests/s for 10 seconds; ThreadPool keeps concurrent requests in flight.
measurements=[];futures=[];started=time.perf_counter()
with ThreadPoolExecutor(max_workers=30) as pool:
    for i in range(300):
        delay=started+i/30-time.perf_counter()
        if delay>0:time.sleep(delay)
        futures.append(pool.submit(request,i))
    measurements=[f.result() for f in futures]
measurements.sort()
result={'scope':'motore + PostgreSQL + RLS, non HTTP/proxy/provider','synthetic_venues':100,'tables_per_venue':10,'requests':300,'rate_target_rps':30,'p95_ms':round(measurements[int(.95*len(measurements))-1],2),'p50_ms':round(statistics.median(measurements),2),'elapsed_seconds':round(time.perf_counter()-started,2),'target_p95_ms':500,'passed':measurements[int(.95*len(measurements))-1]<500}
print(json.dumps(result,indent=2))
