import hashlib
import hmac
import json
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select, func
from app.auth.security import decrypt
from app.db import transaction
from app.domain.models import Reservation, ConversationMessage, now
from app.providers import meta_demo as meta

PHONE = '390000000001'
PHONE_ID = '1234567890'
SECRET = 'not-a-real-meta-app-secret'
TOKEN = 'not-a-real-meta-access-token'
VERIFY = 'not-a-real-meta-verification-token'


def configure(monkeypatch, mode='SANDBOX', outcome=200):
    values = {'META_DEMO_ENABLED':'true','META_ACCESS_TOKEN':TOKEN,'META_APP_SECRET':SECRET,'META_VERIFY_TOKEN':VERIFY,'META_TEST_PHONE_NUMBER_ID':PHONE_ID,'META_TEST_RECIPIENTS':PHONE,'META_DEMO_VENUE':'test-0'}
    for key, value in values.items():
        monkeypatch.setenv(key,value)
    calls=[]
    original=httpx.Client
    def handle(request):
        assert request.url.host=='graph.facebook.com'
        assert request.headers['Authorization']=='Bearer '+TOKEN
        if request.method=='GET':
            return httpx.Response(200,json={'id':PHONE_ID,'account_mode':mode})
        calls.append(json.loads(request.content))
        return httpx.Response(outcome,json={'messages':[{'id':'wamid.outbound'}]})
    monkeypatch.setattr(meta.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    return calls


def envelope(body='PRENOTA', sid=None, phone=PHONE, phone_id=PHONE_ID, timestamp=None):
    return {'object':'whatsapp_business_account','entry':[{'id':'test-waba','changes':[{'field':'messages','value':{'metadata':{'phone_number_id':phone_id},'messages':[{'id':sid or 'wamid.'+uuid4().hex,'from':phone,'timestamp':str(timestamp if timestamp is not None else int(now().timestamp())),'type':'text','text':{'body':body}}]}}]}]}


def send(client, body='PRENOTA', **kwargs):
    data=json.dumps(envelope(body,**kwargs)).encode()
    signature='sha256='+hmac.new(SECRET.encode(),data,hashlib.sha256).hexdigest()
    return client.post(meta.PATH,content=data,headers={'Content-Type':'application/json','X-Hub-Signature-256':signature})


def test_subscription_challenge_and_unsigned_request(client,monkeypatch):
    assert client.get(meta.PATH).json()['configured'] is False
    monkeypatch.setenv('META_VERIFY_TOKEN',VERIFY)
    query={'hub.mode':'subscribe','hub.verify_token':VERIFY,'hub.challenge':'123456'}
    assert client.get(meta.PATH,params=query).text=='123456'
    query['hub.verify_token']='wrong'
    assert client.get(meta.PATH,params=query).status_code==403
    assert send(client).status_code==503
    configure(monkeypatch)
    assert client.post(meta.PATH,json=envelope()).status_code==403
    assert client.get(meta.PATH).json()['delivery_verified'] is False


def test_complete_chat_replay_encryption_and_tenant_isolation(client,tenants,monkeypatch,caplog):
    calls=configure(monkeypatch)
    for body in ('PRENOTA','SI','DOMANI','2','19:00','Ospite Fittizio'):
        assert send(client,body).status_code==200
    assert 'Riepilogo' in calls[-1]['text']['body']
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Reservation))==0
    sid='wamid.confirm'
    assert send(client,'CONFERMO',sid=sid).status_code==200
    assert 'Prenotazione confermata' in calls[-1]['text']['body']
    count=len(calls)
    assert send(client,'CONFERMO',sid=sid).status_code==200
    assert len(calls)==count
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Reservation))==1
        for row in db.scalars(select(ConversationMessage)):
            assert 'Ospite Fittizio' not in row.redacted_body and PHONE not in row.redacted_body
            assert json.loads(decrypt(row.redacted_body))['delivery']=='submitted'
    with transaction(tenants[1]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Reservation))==0
    for value in (TOKEN,SECRET,PHONE,'Ospite Fittizio'):
        assert value not in caplog.text


@pytest.mark.parametrize('mode',['LIVE',None])
def test_never_sends_from_production_or_unverified_sender(client,tenants,monkeypatch,mode):
    calls=configure(monkeypatch,mode=mode)
    assert send(client).status_code==200
    assert not calls
    with transaction(tenants[0]['tenant']) as db:
        payload=json.loads(decrypt(db.scalar(select(ConversationMessage)).redacted_body))
        assert payload['delivery']=='failed' and payload['failure_code']=='test_sender_not_verified'


def test_ignores_unapproved_sender_destination_and_old_events(client,tenants,monkeypatch):
    calls=configure(monkeypatch)
    assert send(client,phone='390000000009').status_code==200
    assert send(client,phone_id='9999999').status_code==200
    assert send(client,timestamp=int(now().timestamp())-3600).status_code==200
    assert not calls
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage))==0


def test_uncertain_delivery_is_not_replayed_or_advanced(client,tenants,monkeypatch):
    calls=configure(monkeypatch,outcome=500)
    assert send(client,sid='wamid.uncertain').status_code==200
    assert send(client,sid='wamid.uncertain').status_code==200
    assert send(client,'SI').status_code==200
    meta.process_outbox()
    assert len(calls)==1
    with transaction(tenants[0]['tenant']) as db:
        row=db.scalar(select(ConversationMessage))
        assert json.loads(decrypt(row.redacted_body))['delivery']=='uncertain'
        assert db.scalar(select(func.count()).select_from(Reservation))==0


def test_hard_test_message_budget(client,tenants,monkeypatch):
    calls=configure(monkeypatch)
    monkeypatch.setattr(meta,'BUDGET',2)
    for body in ('PRENOTA','SI','DOMANI'):
        assert send(client,body).status_code==200
    assert len(calls)==2


def test_manual_venue_does_not_claim_confirmation(client,tenants,monkeypatch):
    calls=configure(monkeypatch)
    monkeypatch.setenv('META_DEMO_VENUE','test-1')
    from app.domain.models import Venue
    with transaction(tenants[1]['tenant']) as db:
        db.get(Venue,tenants[1]['venue']).booking_mode='manual'
    for body in ('PRENOTA','SI','DOMANI','2','19:00','Ospite Manuale','CONFERMO'):
        assert send(client,body).status_code==200
    assert 'approvazione' in calls[-1]['text']['body']


def send_message(client, message):
    # Come send(), ma con un messaggio WhatsApp arbitrario (pulsanti, tipi non supportati).
    message={'id':'wamid.'+uuid4().hex,'from':PHONE,'timestamp':str(int(now().timestamp())),**message}
    data=envelope()
    data['entry'][0]['changes'][0]['value']['messages']=[message]
    raw=json.dumps(data).encode()
    signature='sha256='+hmac.new(SECRET.encode(),raw,hashlib.sha256).hexdigest()
    return client.post(meta.PATH,content=raw,headers={'Content-Type':'application/json','X-Hub-Signature-256':signature})


def test_template_quick_reply_button_starts_chat(client,tenants,monkeypatch):
    calls=configure(monkeypatch)
    assert send_message(client,{'type':'button','button':{'text':'Prenota','payload':'Prenota'}}).status_code==200
    assert len(calls)==1 and 'Informativa' in calls[-1]['text']['body']
    assert send_message(client,{'type':'interactive','interactive':{'type':'button_reply','button_reply':{'id':'si','title':'SI'}}}).status_code==200
    assert 'Per quale giorno' in calls[-1]['text']['body']


@pytest.mark.parametrize('message',[
    {'type':'button','button':'Prenota'},
    {'type':'interactive','interactive':{'type':'button_reply','button_reply':None}},
    {'type':'interactive','interactive':['Prenota']},
    {'type':'image','image':{'id':'media'}},
])
def test_malformed_or_unsupported_messages_are_ignored(client,tenants,monkeypatch,message):
    calls=configure(monkeypatch)
    assert send_message(client,message).status_code==200
    assert not calls
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(ConversationMessage))==0
