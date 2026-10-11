import hashlib,hmac,json,time
from datetime import timedelta
from sqlalchemy import select,func
from app.domain.models import *
from app.db import transaction
from app.workers.tasks import process_tenant
from app.providers.adapters import TwilioAdapter,StripeConnectAdapter,ProviderUnavailable,ALLOWED
from app.services.reservations import money
from conftest import sign_in,payload
import pytest

def test_outbox_retry_dedup_and_tenant_isolation(client,tenants):
    for i in range(2): assert client.post(f'/api/public/test-{i}/reservations',json=payload()).status_code==201
    tid=tenants[0]['tenant'];clock=now()
    assert process_tenant(tid,clock=clock,fail=True)['processed']==2
    assert process_tenant(tid,clock=clock+timedelta(minutes=1))['processed']==2
    assert process_tenant(tid,clock=clock+timedelta(minutes=2))['processed']==0
    with transaction(tid) as db:
        assert db.scalar(select(func.count()).select_from(Notification))==2
        assert db.scalar(select(func.count()).select_from(UsageLedger))==2
    with transaction(tenants[1]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Notification))==0

def test_missing_optin_and_no_post_visit_messages(client,tenants):
    body=payload(channel='whatsapp',phone='+393331234567',whatsapp_opt_in=False)
    assert client.post('/api/public/test-0/reservations',json=body).status_code==201
    process_tenant(tenants[0]['tenant'])
    with transaction(tenants[0]['tenant']) as db:
        assert all(n.failure_code=='whatsapp_opt_in_missing' for n in db.scalars(select(Notification)))
        assert all(e.event_type in ALLOWED for e in db.scalars(select(OutboxEvent)))
    r=client.get('/api/public/test-0/availability?day=2026-10-12&party_size=2'); assert r.status_code==200
    assert client.post('/api/public/test-1/reservations',json=payload(phone='123')).status_code==422

def test_cancel_invalidates_reminder_and_optimistic_conflict(client,tenants):
    b=client.post('/api/public/test-0/reservations',json=payload()).json();h={'X-Booking-Token':b['access_token']}
    cancel={'status':'CANCELLED','version':1}
    assert client.post('/api/public/test-0/booking/cancel',json=cancel,headers=h).status_code==200
    assert client.post('/api/public/test-0/booking/cancel',json=cancel,headers=h).status_code==409
    process_tenant(tenants[0]['tenant'],clock=now()+timedelta(days=3))
    with transaction(tenants[0]['tenant']) as db:
        reminders=db.scalars(select(OutboxEvent).where(OutboxEvent.event_type=='reminder')).all()
        assert reminders and all(e.status=='cancelled' for e in reminders)
        assert not db.scalar(select(Notification.id).where(Notification.deduplication_key.like('%reminder')))

def test_payment_simulation_idempotent_refund_and_tenant(client,tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);v.deposit_cents=1000;v.deposit_tax_rate=10
    obj=client.post('/api/public/test-0/reservations',json=payload()).json();h={'X-Booking-Token':obj['access_token']}
    assert obj['reservation']['status']=='AWAITING_PAYMENT'
    assert obj['reservation']['deposit']['amount_total']==1100
    staff_h=sign_in(client)
    assert client.post('/api/admin/reservations/'+obj['reservation']['id']+'/status',json={'status':'CONFIRMED','version':1},headers=staff_h).status_code==409
    assert client.post('/api/public/test-1/booking/payment-simulation',json={'event_id':'event-12345'},headers=h).status_code==404
    for ev in ['event-12345','event-duplicate-different']:
        res=client.post('/api/public/test-0/booking/payment-simulation',json={'event_id':ev},headers=h);assert res.status_code==200,res.text;assert res.json()['reservation']['status']=='CONFIRMED'
    cancel=client.post('/api/public/test-0/booking/cancel',json={'status':'CANCELLED','version':2},headers=h);assert cancel.status_code==200,cancel.text
    with transaction(t['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Payment))==1
        assert db.scalar(select(func.count()).select_from(Refund))==1
        assert db.scalar(select(Refund)).amount==1100
    duplicate=client.post('/api/public/test-0/booking/payment-simulation',json={'event_id':'event-later'},headers=h);assert duplicate.json()['payment_status']=='refunded'

def test_late_payment_releases_without_capture(client,tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);v.deposit_cents=1000;v.deposit_tax_rate=10
    b=client.post('/api/public/test-0/reservations',json=payload()).json();h={'X-Booking-Token':b['access_token']}
    with transaction(t['tenant']) as db:
        r=db.scalar(select(Reservation));r.payment_expires_at=now()-timedelta(seconds=1)
    res=client.post('/api/public/test-0/booking/payment-simulation',json={'event_id':'late-event'},headers=h)
    assert res.status_code==409
    process_tenant(t['tenant'])
    with transaction(t['tenant']) as db:
        assert db.scalar(select(Reservation)).status=='EXPIRED'
        assert db.scalar(select(func.count()).select_from(Payment))==0

def test_sdk_signatures_and_real_send_gate():
    from twilio.request_validator import RequestValidator
    adapter=TwilioAdapter('AC123','test-secret')
    url='https://example.test/voice';form={'AccountSid':'AC123','CallSid':'CA123'}
    sig=RequestValidator('test-secret').compute_signature(url,form)
    assert adapter.validate(url,form,sig,'AC123')
    assert not adapter.validate(url,form,'bad','AC123')
    assert not adapter.validate(url,form,sig,'AC_OTHER')
    assert 'record' not in adapter.greeting('Locale','https://example.test/keypad').lower()
    with pytest.raises(ProviderUnavailable):adapter.send('+393331234567','whatsapp:+10000000000','confirmed',{'approval_status':'approved','provider_template_id':'HX'}, {},True)
    payload_bytes=b'{"id":"evt_test","type":"checkout.session.completed"}'
    timestamp=int(time.time());sig=hmac.new(b'whsec-test',str(timestamp).encode()+b'.'+payload_bytes,hashlib.sha256).hexdigest()
    event=StripeConnectAdapter.validate(payload_bytes,f't={timestamp},v1={sig}','whsec-test');assert event['id']=='evt_test'
    with pytest.raises(Exception):StripeConnectAdapter.validate(payload_bytes,'t=1,v1=bad','whsec-test')
    assert money(14900,22)['tax_amount']==3278

def test_manual_receipt_distinct_confirmation_and_phone_fallback(client,tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:db.get(Venue,t['venue']).booking_mode='manual'
    r=client.post('/api/public/test-0/reservations',json=payload()).json();assert r['reservation']['status']=='PENDING_APPROVAL'
    with transaction(t['tenant']) as db:assert [x.event_type for x in db.scalars(select(OutboxEvent))]==['received']
    h=sign_in(client)
    for bad in [{'whatsapp':False},{'whatsapp':True,'hidden':True},{'whatsapp':True,'mobile':False},{'whatsapp':True,'provider_failure':True}]:
        res=client.post('/api/demo/phone',json=bad,headers=h);assert res.status_code==200;assert res.json()['booking_url'] is None
    good=client.post('/api/demo/phone',json={'whatsapp':True},headers=h);assert good.json()['real_message_sent'] is False
    assert client.post('/api/admin/reservations/'+r['reservation']['id']+'/status',json={'status':'CONFIRMED','version':1},headers=h).status_code==200

def test_stripe_sdk_contract_uses_connected_account_and_idempotency(monkeypatch):
    from unittest.mock import Mock
    from app.config import settings
    monkeypatch.setattr(settings,'demo',False)
    monkeypatch.setenv('STRIPE_CONNECT_ENABLED','true')
    a=StripeConnectAdapter('sk_test_fake')
    a.client.checkout.sessions.create=Mock(return_value={'id':'cs_test_fake'})
    result=a.checkout('acct_test','reservation-id',1100,'EUR','idem-123','https://example.test/success','https://example.test/cancel')
    assert result['id']=='cs_test_fake'
    call=a.client.checkout.sessions.create.call_args
    assert call.kwargs['options']=={'stripe_account':'acct_test','idempotency_key':'idem-123'}
    assert call.kwargs['params']['line_items'][0]['price_data']['unit_amount']==1100
    a.client.refunds.create=Mock(return_value={'id':'re_test_fake'})
    a.refund('acct_test','pi_test_fake',1100,'refund-123')
    assert a.client.refunds.create.call_args.kwargs['options']['stripe_account']=='acct_test'

def test_no_delayed_sends_after_visit(client,tenants):
    b=client.post('/api/public/test-0/reservations',json=payload()).json()
    process_tenant(tenants[0]['tenant'],clock=now()+timedelta(days=4))
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Notification))==0
        assert all(e.status=='cancelled' for e in db.scalars(select(OutboxEvent)))
