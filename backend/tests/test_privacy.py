from sqlalchemy import select
from app.db import transaction
from app.domain.models import Customer,ConsentRecord,BookingAccessToken,Notification
from conftest import payload,sign_in

def test_privacy_requires_manager_verified_identity_and_no_active_booking(client,tenants):
    b=client.post('/api/public/test-0/reservations',json=payload()).json();token={'X-Booking-Token':b['access_token']}
    with transaction(tenants[0]['tenant']) as db:cid=str(db.scalar(select(Customer)).id)
    h=sign_in(client,role='manager',mfa=tenants[0]['mfa'])
    body={'customer_id':cid,'identity_verified':False,'reason':'richiesta verificata manualmente'}
    assert client.post('/api/admin/privacy/anonymize',json=body,headers=h).status_code==422
    body['identity_verified']=True
    assert client.post('/api/admin/privacy/anonymize',json=body,headers=h).status_code==409
    exported=client.post('/api/admin/privacy/export',json=body,headers=h);assert exported.status_code==200;assert exported.json()['email']=='test@example.test'
    assert client.post('/api/public/test-0/booking/cancel',json={'status':'CANCELLED','version':1},headers=token).status_code==200
    assert client.post('/api/admin/privacy/anonymize',json=body,headers=h).status_code==200
    assert client.get('/api/public/test-0/booking',headers=token).status_code==404
    with transaction(tenants[0]['tenant']) as db:
        c=db.scalar(select(Customer));assert c.name=='Ospite anonimizzato' and c.email is None
        assert db.scalar(select(ConsentRecord)) is None
