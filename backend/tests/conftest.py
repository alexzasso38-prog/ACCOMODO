import os
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
# A dedicated, explicit PostgreSQL test database. No SQLite fallback.
TEST_URL=os.environ.get('TAVOLO_TEST_DATABASE_URL','postgresql+psycopg://tavolo_app:local-demo-app@127.0.0.1:55432/tavolo_demo_test')
OWNER_URL=os.environ.get('TAVOLO_TEST_OWNER_URL','postgresql+psycopg://tavolo_owner:local-demo-owner@127.0.0.1:55432/tavolo_demo_test')
if not TEST_URL.endswith('/tavolo_demo_test') or not OWNER_URL.endswith('/tavolo_demo_test'): raise RuntimeError('Test consentiti soltanto sul DB dedicato tavolo_demo_test.')
os.environ['DATABASE_URL']=TEST_URL
os.environ['MIGRATION_DATABASE_URL']=OWNER_URL
os.environ['ENCRYPTION_KEY']=Fernet.generate_key().decode()
os.environ['APP_ENV']='demo';os.environ['DEMO_MODE']='true';os.environ['SEND_REAL_MESSAGES']='false'
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session as DBSession
from app.domain.models import *
from app.auth.security import hasher,crypt,redis
from app.db import transaction
from app.main import app
from fastapi.testclient import TestClient
from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
import pyotp
owner=create_engine(OWNER_URL)

@pytest.fixture(autouse=True)
def clean():
    # Refuse unguarded production cleanup; the owner URL was checked above.
    with owner.begin() as db:
        names=', '.join(t.name for t in Base.metadata.sorted_tables)
        db.execute(text('TRUNCATE '+names+' CASCADE'))
    for key in redis.scan_iter('rate:*'): redis.delete(key)

@pytest.fixture
def tenants():
    result=[]
    with DBSession(owner) as db,db.begin():
        for i in range(2):
            tenant=Tenant(name=f'Test {i}',slug=f'test-{i}'); db.add(tenant);db.flush()
            v=Venue(tenant_id=tenant.id,name=f'Ristorante {i} DEMO',slug=f'test-{i}',minimum_notice_minutes=0,booking_horizon_days=365,booking_mode='automatic')
            db.add(v);db.flush();db.add(VenueRoute(tenant_id=tenant.id,venue_id=v.id,slug=v.slug))
            room=Room(tenant_id=tenant.id,venue_id=v.id,name='Sala');db.add(room);db.flush()
            table=Resource(tenant_id=tenant.id,venue_id=v.id,room_id=room.id,name='Unico tavolo',min_guests=1,max_guests=4);db.add(table);db.flush()
            for wd in range(7): db.add(ServiceSchedule(tenant_id=tenant.id,venue_id=v.id,weekday=wd,local_start_time=time(12),local_end_time=time(23,30),duration_minutes=90,slot_interval_minutes=30))
            mfa=pyotp.random_base32()
            for role in ['staff','manager']:
                u=User(email=f'{role}{i}@test.test',password_hash=hasher.hash('TestPassword!2026'),mfa_config=crypt(mfa) if role=='manager' else None);db.add(u);db.flush();db.add(Membership(user_id=u.id,tenant_id=tenant.id,venue_id=v.id,role=role))
            result.append({'tenant':tenant.id,'venue':v.id,'resource':table.id,'room':room.id,'slug':v.slug,'mfa':mfa})
    return result

@pytest.fixture
def client():
    with TestClient(app) as c: yield c

def sign_in(client,index=0,role='staff',mfa=None):
    body={'email':f'{role}{index}@test.test','password':'TestPassword!2026'}
    if mfa: body['otp']=pyotp.TOTP(mfa).now()
    response=client.post('/api/auth/login',json=body);assert response.status_code==200,response.text
    return {'X-CSRF-Token':response.json()['csrf_token']}

def payload(hour=19,minute=0,party=2,**kwargs):
    day=datetime.now(ZoneInfo('Europe/Rome')).date()+timedelta(days=2)
    return {'starts_at':datetime.combine(day,time(hour,minute),ZoneInfo('Europe/Rome')).isoformat(),'party_size':party,'name':'Ospite test','email':'test@example.test','privacy_ack':True,**kwargs}
