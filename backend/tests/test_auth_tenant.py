from sqlalchemy import select,text,func
from sqlalchemy.exc import IntegrityError
from app.db import transaction
from app.domain.models import *
from conftest import sign_in,payload,owner
import pytest

def test_auth_csrf_roles_mfa_and_revocation(client,tenants):
    assert client.get('/api/admin/resources').status_code==401
    assert client.post('/api/auth/login',json={'email':'staff0@test.test','password':'wrong'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'manager0@test.test','password':'TestPassword!2026'}).status_code==401
    headers=sign_in(client)
    assert 'HttpOnly' in str(client.cookies) or client.cookies.get('tavolo_session')
    assert client.post('/api/admin/resources',json={'name':'X','min_guests':1,'max_guests':2}).status_code==403
    assert client.post('/api/admin/resources',json={'name':'X','min_guests':1,'max_guests':2},headers=headers).status_code==403
    assert client.post('/api/auth/logout',headers=headers).status_code==200
    assert client.get('/api/auth/me').status_code==401
    headers=sign_in(client,role='manager',mfa=tenants[0]['mfa'])
    assert client.post('/api/admin/resources',json={'name':'X','min_guests':1,'max_guests':2},headers=headers).status_code==200

def test_rls_no_context_and_composite_cross_tenant(tenants):
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Resource))==0
        role=db.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one();assert role==(False,False)
    with transaction(tenants[0]['tenant']) as db:
        assert db.get(Resource,tenants[1]['resource']) is None
        assert db.scalar(select(func.count()).select_from(Resource))==1
    with pytest.raises(IntegrityError):
        with transaction(tenants[0]['tenant']) as db:
            db.add(Resource(tenant_id=tenants[0]['tenant'],venue_id=tenants[1]['venue'],room_id=tenants[1]['room'],name='Illegal',min_guests=1,max_guests=2));db.flush()
    # A pool checkout does not retain SET LOCAL after commit.
    with transaction() as db: assert db.scalar(select(func.count()).select_from(Resource))==0

def test_public_token_and_staff_cross_tenant_denied(client,tenants):
    booked=client.post('/api/public/test-1/reservations',json=payload());assert booked.status_code==201,booked.text
    obj=booked.json();token={'X-Booking-Token':obj['access_token']}
    assert client.get('/api/public/test-0/booking',headers=token).status_code==404
    assert client.get('/api/public/test-1/booking').status_code==401
    headers=sign_in(client)
    assert client.post('/api/admin/reservations/'+obj['reservation']['id']+'/status',json={'status':'CANCELLED','version':1},headers=headers).status_code==404
    headers=sign_in(client,role='manager',mfa=tenants[0]['mfa'])
    exported=client.get('/api/admin/export.csv');assert 'Ospite test' not in exported.text
    assert client.get('/api/admin/customers').json()==[]
    assert client.post('/api/webhooks/twilio',json={'tenant_id':str(tenants[0]['tenant'])}).status_code==503

def test_csv_injection_and_ics_redaction(client,tenants):
    r=client.post('/api/public/test-0/reservations',json=payload(name='=HYPERLINK("bad")')).json()
    token={'X-Booking-Token':r['access_token']}
    ics=client.get('/api/public/test-0/booking/calendar.ics',headers=token)
    assert ics.status_code==200
    assert 'HYPERLINK' not in ics.text and 'example.test' not in ics.text and r['access_token'] not in ics.text
    sign_in(client,role='manager',mfa=tenants[0]['mfa'])
    export=client.get('/api/admin/export.csv');assert "'=HYPERLINK" in export.text
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(BookingAccessToken)).token_hash!=r['access_token']
        assert 'example.test' not in db.scalar(select(Customer)).email

def test_public_booking_reaches_staff_agenda_and_upcoming(client,tenants):
    obj=client.post('/api/public/test-0/reservations',json=payload(hour=20)).json()
    rid=obj['reservation']['id']; day=obj['reservation']['starts_at'][:10]
    sign_in(client)
    assert rid in [r['id'] for r in client.get('/api/admin/reservations?day='+day).json()]
    upcoming=client.get('/api/admin/reservations/upcoming').json()
    assert [r['id'] for r in upcoming]==[rid] and upcoming[0]['source']=='web' and upcoming[0]['created_at']
    # Tenant isolation: the other restaurant never sees it.
    client.post('/api/auth/logout'); sign_in(client,index=1)
    assert client.get('/api/admin/reservations/upcoming').json()==[]
