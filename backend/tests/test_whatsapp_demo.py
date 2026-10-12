import json
from urllib.parse import urlencode
from uuid import uuid4
from sqlalchemy import select,func
from twilio.request_validator import RequestValidator
from app.config import settings
from app.providers.whatsapp_demo import PATH
from app.domain.models import Reservation,ConversationMessage
from app.db import transaction

ACCOUNT='AC'+'1'*32
TOKEN='test-token-not-a-real-provider-secret'
SENDER='whatsapp:+390000000002'

def setup(monkeypatch):
    for key,value in {'WHATSAPP_DEMO_ENABLED':'true','TWILIO_ACCOUNT_SID':ACCOUNT,'TWILIO_AUTH_TOKEN':TOKEN,'TWILIO_WHATSAPP_FROM':SENDER,'WHATSAPP_DEMO_VENUE':'test-0'}.items():monkeypatch.setenv(key,value)

def send(client,body,sid=None,phone='+390000000001',account=ACCOUNT):
    fields={'AccountSid':account,'To':SENDER,'From':'whatsapp:'+phone,'MessageSid':sid or 'SM'+uuid4().hex,'Body':body}
    signature=RequestValidator(TOKEN).compute_signature(settings.base_url.rstrip('/')+PATH,fields)
    return client.post(PATH,content=urlencode(fields),headers={'Content-Type':'application/x-www-form-urlencoded','X-Twilio-Signature':signature})

def test_signed_chat_books_once_and_isolates_customer_and_tenant(client,tenants,monkeypatch):
    setup(monkeypatch)
    assert 'Informativa' in send(client,'ciao').text
    assert 'quale giorno' in send(client,'SI').text
    assert 'persone' in send(client,'DOMANI').text
    assert 'Orari disponibili' in send(client,'2').text
    assert 'nome' in send(client,'19:00').text
    assert 'Riepilogo' in send(client,'Ospite Fittizio').text
    with transaction(tenants[0]['tenant']) as db:assert db.scalar(select(func.count()).select_from(Reservation))==0
    # A different number cannot confirm another guest's conversation.
    assert 'Informativa' in send(client,'CONFERMO',phone='+390000000003').text
    sid='SM'+uuid4().hex
    first=send(client,'CONFERMO',sid);assert first.status_code==200 and 'Prenotazione confermata' in first.text
    assert send(client,'CONFERMO',sid).text==first.text
    assert 'già stata inviata' in send(client,'CONFERMO').text
    with transaction(tenants[0]['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Reservation))==1
        assert all('Ospite Fittizio' not in m.redacted_body and '+390000000001' not in m.redacted_body for m in db.scalars(select(ConversationMessage)))
    with transaction(tenants[1]['tenant']) as db:assert db.scalar(select(func.count()).select_from(Reservation))==0

def test_disabled_bad_signature_and_wrong_account(client,tenants,monkeypatch):
    assert send(client,'ciao').status_code==503
    setup(monkeypatch)
    assert client.post(PATH,content='Body=ciao',headers={'Content-Type':'application/x-www-form-urlencoded'}).status_code==403
    assert send(client,'ciao',account='AC'+'2'*32).status_code==403
    assert send(client,'ciao',phone='hidden').status_code==400


def test_diagnostics_never_log_message_phone_token_or_signature(client,tenants,monkeypatch,caplog):
    setup(monkeypatch)
    response=send(client,'contenuto-privato-di-test')
    assert response.status_code==200
    assert 'webhook ricevuto' in caplog.text and 'HTTP 200' in caplog.text
    for secret in (TOKEN,ACCOUNT,SENDER,'+390000000001','contenuto-privato-di-test'):
        assert secret not in caplog.text
    caplog.clear()
    response=client.post(PATH,content='Body=contenuto-privato-di-test',headers={'Content-Type':'application/x-www-form-urlencoded'})
    assert response.status_code==403
    assert 'Firma non valida' in caplog.text and 'firma presente=False' in caplog.text
    assert 'contenuto-privato-di-test' not in caplog.text
