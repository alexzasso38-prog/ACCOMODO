from unittest.mock import Mock
from fastapi import HTTPException
from datetime import timedelta
from app.providers.voice import AuthorizedCall,VoiceTools
from app.domain.models import now
from conftest import payload,sign_in
import pytest

def test_voice_tools_authorization_summary_and_budget():
    api=Mock();tools=VoiceTools(AuthorizedCall('server-tenant','server-slug',now()),api)
    with pytest.raises(HTTPException):tools.invoke('availability',{'day':'2026-10-12','party_size':2,'tenant_id':'attacker'},0)
    with pytest.raises(HTTPException):tools.invoke('book',{'summary_confirmed':False},0)
    with pytest.raises(HTTPException):tools.invoke('allergens',{},0)
    with pytest.raises(HTTPException):tools.invoke('availability',{'day':'2026-10-12','party_size':2},100)
    with pytest.raises(HTTPException):tools.invoke('availability',{'day':'2026-10-12','party_size':2},0,now()+timedelta(minutes=3))
    tools.invoke('availability',{'day':'2026-10-12','party_size':2},0)
    assert api.get.call_args.args[0]=='/api/public/server-slug/availability'
    assert tools.invoke('handoff',{},0)['route']=='human'

def test_waitlist_offer_is_hold_and_cross_tenant_denied(client,tenants):
    b=payload();data={'starts_at':b['starts_at'],'ends_at':(now()+timedelta(days=3)).isoformat(),'name':b['name'],'email':b['email'],'party_size':2,'privacy_ack':True}
    r=client.post('/api/public/test-0/waitlist',json=data);assert r.status_code==201,r.text
    wid=r.json()['reference'];h=sign_in(client,index=1)
    assert client.post('/api/admin/waitlist/'+wid+'/offer',headers=h).status_code==404
    h=sign_in(client);offer=client.post('/api/admin/waitlist/'+wid+'/offer',headers=h)
    assert offer.status_code==200,offer.text;assert offer.json()['reservation']['status']=='HOLD'
    assert client.post('/api/admin/waitlist/'+wid+'/offer',headers=h).status_code==409
    booked=client.post('/api/public/test-0/reservations',json=b);assert booked.status_code==409
    from urllib.parse import urlparse,parse_qs
    token=parse_qs(urlparse(offer.json()['manage_url']).fragment)['token'][0]
    finalize=client.post('/api/public/test-0/booking/finalize',headers={'X-Booking-Token':token})
    assert finalize.status_code==200 and finalize.json()['status']=='CONFIRMED'

def test_quotes_vat_no_fiscal_claim_and_usage_cap(client,tenants):
    from decimal import Decimal
    from app.db import transaction
    from app.domain.models import UsageLedger
    h=sign_in(client,role='manager',mfa=tenants[0]['mfa'])
    q=client.post('/api/admin/billing/quote',json={'plan':'Concierge','include_setup':False},headers=h)
    assert q.status_code==201,q.text
    assert q.json()['amount_total']==18178 and q.json()['tax_amount']==3278
    assert q.json()['fiscal_document_issued'] is False and q.json()['charged'] is False
    with transaction(tenants[0]['tenant']) as db:
        db.add(UsageLedger(tenant_id=tenants[0]['tenant'],venue_id=tenants[0]['venue'],channel='whatsapp_simulated',quantity=270,unit='message',deduplication_key='quota-test'))
    u=client.get('/api/admin/usage').json();assert u['channels']['whatsapp']['warning_threshold']==90
    assert u['overages_enabled'] is False
    from app.services.subscriptions import permitted
    from app.domain.models import Venue
    with transaction(tenants[0]['tenant']) as db:
        allowed,reason=permitted(db,db.get(Venue,tenants[0]['venue']),'whatsapp',31)
        assert not allowed and reason=='included_quota_reached'
