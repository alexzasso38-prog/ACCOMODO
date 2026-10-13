"""Meta Cloud API test-number adapter. No templates or production senders."""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from sqlalchemy import select, func

from app.auth.security import crypt, decrypt
from app.config import settings
from app.db import transaction, tenant_lock
from app.domain.models import Conversation, ConversationMessage, Venue, VenueRoute, now
from app.providers.whatsapp_demo import advance
from app.services.reservations import digest

router = APIRouter()
PATH = '/api/whatsapp/meta'
logger = logging.getLogger('uvicorn.error')
BUDGET = 50


def configuration():
    if not settings.demo or os.getenv('META_DEMO_ENABLED') != 'true':
        return None
    keys = ('META_ACCESS_TOKEN', 'META_APP_SECRET', 'META_VERIFY_TOKEN', 'META_TEST_PHONE_NUMBER_ID', 'META_TEST_RECIPIENTS')
    if not all(os.getenv(k) for k in keys):
        return None
    phone_id = os.environ['META_TEST_PHONE_NUMBER_ID']
    version = os.getenv('META_GRAPH_VERSION', 'v23.0')
    recipients = {x.strip().removeprefix('+') for x in os.environ['META_TEST_RECIPIENTS'].split(',')}
    if not phone_id.isascii() or not phone_id.isdecimal() or not re.fullmatch(r'v\d{2}\.\d+', version):
        return None
    if not 1 <= len(recipients) <= 5 or any(not re.fullmatch(r'[1-9][0-9]{7,14}', x) for x in recipients):
        return None
    return {'phone_id': phone_id, 'version': version, 'recipients': recipients,
            'token': os.environ['META_ACCESS_TOKEN'], 'secret': os.environ['META_APP_SECRET']}


@router.get(PATH)
def verify(request: Request):
    if 'hub.mode' in request.query_params:
        token = os.getenv('META_VERIFY_TOKEN', '')
        supplied = request.query_params.get('hub.verify_token', '')
        challenge = request.query_params.get('hub.challenge', '')
        if not token or not secrets.compare_digest(token, supplied) or request.query_params['hub.mode'] != 'subscribe' or not re.fullmatch(r'[0-9]{1,256}', challenge):
            raise HTTPException(403, 'Verifica Meta non valida.')
        return Response(challenge, media_type='text/plain')
    return {'mode': 'meta-test-number', 'enabled': os.getenv('META_DEMO_ENABLED') == 'true',
            'configured': configuration() is not None, 'voice_enabled': False,
            'delivery_verified': False, 'message_limit': BUDGET}


def venue_route():
    with transaction() as db:
        route = db.scalar(select(VenueRoute).where(VenueRoute.slug == os.getenv('META_DEMO_VENUE', 'osteria-demo')))
        if not route:
            raise HTTPException(503, 'Ristorante demo non disponibile.')
        return route.tenant_id, route.venue_id


def ingest(cfg, message):
    phone = message.get('from', '')
    sid = message.get('id', '')
    if phone not in cfg['recipients'] or not isinstance(sid, str) or not sid.startswith('wamid.') or len(sid) > 512:
        return False
    try:
        timestamp = datetime.fromtimestamp(int(message.get('timestamp', '0')), timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return False
    if not now() - timedelta(minutes=10) <= timestamp <= now() + timedelta(minutes=2):
        return False
    if message.get('type') != 'text' or not isinstance(message.get('text', {}).get('body'), str):
        return False
    body = message['text']['body']
    if len(body) > 4096:
        return False
    tid, vid = venue_route()
    with transaction(tid) as db:
        tenant_lock(db, vid)
        convo = db.scalar(select(Conversation).where(Conversation.venue_id == vid, Conversation.channel == 'meta_test', Conversation.provider_conversation_id == digest(cfg['phone_id'] + phone)))
        if not convo:
            convo = Conversation(tenant_id=tid, venue_id=vid, channel='meta_test', provider_conversation_id=digest(cfg['phone_id'] + phone))
            db.add(convo)
            db.flush()
        if db.scalar(select(ConversationMessage.id).where(ConversationMessage.conversation_id == convo.id, ConversationMessage.provider_message_id == sid)):
            return False
        # Reserve budget when recording a reply, before any network operation.
        count = db.scalar(select(func.count()).select_from(ConversationMessage).join(Conversation, Conversation.id == ConversationMessage.conversation_id).where(Conversation.channel == 'meta_test', Conversation.venue_id == vid))
        if count >= BUDGET:
            logger.warning('Meta demo: limite messaggi raggiunto; nessun invio.')
            return False
        previous = db.scalar(select(ConversationMessage).where(ConversationMessage.conversation_id == convo.id).order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc()))
        if previous:
            old = json.loads(decrypt(previous.redacted_body))
            if old['delivery'] in {'pending', 'sending', 'uncertain', 'failed'}:
                logger.warning('Meta demo: risposta precedente non consegnata; percorso sospeso.')
                return False
        state = json.loads(decrypt(previous.redacted_body))['state'] if previous and convo.last_inbound_at and convo.last_inbound_at > now() - timedelta(minutes=30) else {}
        venue = db.get(Venue, vid)
        state, reply = advance(db, venue, state, body, '+' + phone)
        convo.last_inbound_at = now()
        payload = {'state': state, 'reply': reply, 'phone': phone, 'delivery': 'pending', 'inbound_at': timestamp.isoformat()}
        db.add(ConversationMessage(tenant_id=tid, conversation_id=convo.id, direction='outbound', provider_message_id=sid, redacted_body=crypt(json.dumps(payload)), retention_expires_at=now() + timedelta(days=1)))
    return True


@router.post(PATH)
async def inbound(request: Request, background_tasks: BackgroundTasks):
    cfg = configuration()
    if not cfg:
        raise HTTPException(503, 'Meta demo non configurata.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 131072:
            raise HTTPException(413, 'Webhook troppo grande.')
    expected = 'sha256=' + hmac.new(cfg['secret'].encode(), bytes(raw), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(expected, request.headers.get('x-hub-signature-256', '')):
        logger.warning('Meta demo: firma non valida.')
        raise HTTPException(403, 'Firma non valida.')
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('object') != 'whatsapp_business_account':
            raise ValueError()
        entries = data.get('entry', [])
        if not isinstance(entries, list) or len(entries) > 20:
            raise ValueError()
        for entry in entries:
            changes = entry.get('changes', [])
            if not isinstance(changes, list) or len(changes) > 20:
                raise ValueError()
            for change in changes:
                value = change.get('value', {})
                if change.get('field') != 'messages' or value.get('metadata', {}).get('phone_number_id') != cfg['phone_id']:
                    continue
                messages = value.get('messages', [])
                if not isinstance(messages, list) or len(messages) > 20:
                    raise ValueError()
                for message in messages:
                    ingest(cfg, message)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'Evento Meta non valido.')
    background_tasks.add_task(process_outbox)
    logger.warning('Meta demo: webhook verificato e acquisito; invio separato.')
    return {'received': True}


def send_test_reply(cfg, payload):
    """Never send unless Graph independently confirms the sender is SANDBOX."""
    headers = {'Authorization': 'Bearer ' + cfg['token']}
    base = 'https://graph.facebook.com/' + cfg['version'] + '/' + cfg['phone_id']
    if payload['phone'] not in cfg['recipients'] or datetime.fromisoformat(payload['inbound_at']) < now() - timedelta(minutes=15):
        return 'failed', 'recipient_or_window'
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            check = client.get(base, params={'fields': 'id,account_mode'}, headers=headers)
            if check.status_code != 200 or check.json().get('id') != cfg['phone_id'] or check.json().get('account_mode') != 'SANDBOX':
                return 'failed', 'test_sender_not_verified'
            response = client.post(base + '/messages', headers=headers, json={'messaging_product': 'whatsapp', 'to': payload['phone'], 'type': 'text', 'text': {'preview_url': False, 'body': payload['reply']}})
            if response.status_code == 200:
                messages = response.json().get('messages', [])
                if messages and isinstance(messages[0].get('id'), str):
                    return 'submitted', None
                return 'uncertain', 'missing_message_id'
            return ('uncertain' if response.status_code >= 500 else 'failed'), 'graph_http_' + str(response.status_code)
    except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError):
        # Never automatically replay a potentially accepted request.
        return 'uncertain', 'network_or_response'


def process_outbox():
    cfg = configuration()
    if not cfg:
        return
    tid, vid = venue_route()
    for _ in range(5):
        selected = None
        with transaction(tid) as db:
            tenant_lock(db, vid)
            rows = db.scalars(select(ConversationMessage).join(Conversation, Conversation.id == ConversationMessage.conversation_id).where(Conversation.channel == 'meta_test', Conversation.venue_id == vid).order_by(ConversationMessage.created_at).limit(BUDGET)).all()
            for row in rows:
                payload = json.loads(decrypt(row.redacted_body))
                if payload['delivery'] == 'pending':
                    payload['delivery'] = 'sending'
                    row.redacted_body = crypt(json.dumps(payload))
                    selected = (row.id, payload)
                    break
        if not selected:
            break
        message_id, payload = selected
        outcome, code = send_test_reply(cfg, payload)
        with transaction(tid) as db:
            tenant_lock(db, vid)
            row = db.get(ConversationMessage, message_id)
            payload['delivery'] = outcome
            payload['failure_code'] = code
            row.redacted_body = crypt(json.dumps(payload))
        logger.warning('Meta demo: invio %s; codice=%s', outcome, code or 'none')
