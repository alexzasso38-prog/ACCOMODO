"""Signed Twilio inbound trial demo: guided booking, no paid AI or outbound API."""
import json, os, re, logging
from datetime import datetime, timedelta
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from app.config import settings
from app.db import transaction, tenant_lock
from app.auth.security import crypt, decrypt
from app.domain.models import VenueRoute, Venue, Conversation, ConversationMessage, now
from app.domain.availability import available_slots
from app.api.schemas import Booking
from app.services.reservations import create, digest

router=APIRouter()
PATH='/api/whatsapp/demo'
logger=logging.getLogger('uvicorn.error')

def reject(status, detail):
    # Static reasons only: no request bodies, phone numbers, tokens or signatures.
    logger.warning('WhatsApp trial: HTTP %s — %s', status, detail)
    raise HTTPException(status, detail)

def xml(reply):
    response=MessagingResponse(); response.message(reply)
    return str(response)

def advance(db, venue, state, body, phone):
    body=body.strip(); command=body.casefold()
    base=settings.base_url.rstrip('/')
    if command in {'ricomincia','annulla'}:
        return {}, 'Percorso azzerato. Scrivi PRENOTA per iniziare. Per cancellare una prenotazione già creata usa il suo link personale.'
    if command in {'operatore','richiama'}:
        return state, 'Questa prova non trasferisce telefonate. Puoi usare la pagina '+base+'/b/'+venue.slug+'.'
    phase=state.get('phase')
    if not phase:
        return {'phase':'privacy'}, f'Ciao! Sono Accomodo Demo per {venue.name}. Prenotiamo insieme in chat. Usa un nome fittizio: questa è una prova con dati temporanei. Informativa: {base}/privacy. Per proseguire dopo averla letta scrivi SI. Scrivi RICOMINCIA per azzerare il percorso.'
    state=dict(state)
    if phase=='privacy':
        if command not in {'si','sì'}: return state, 'Leggi l’informativa e scrivi SI per proseguire, oppure ANNULLA.'
        state['phase']='day'; return state,'Per quale giorno? Scrivi DOMANI oppure una data nel formato GG/MM/AAAA.'
    if phase=='day':
        today=now().astimezone(ZoneInfo(venue.timezone)).date()
        try:
            day=today+timedelta(days=1) if command=='domani' else today if command=='oggi' else datetime.strptime(body,'%d/%m/%Y').date()
        except ValueError: return state,'Data non riconosciuta. Scrivi DOMANI oppure GG/MM/AAAA.'
        if not today<=day<=today+timedelta(days=venue.booking_horizon_days):return state,'La data deve essere futura ed entro il periodo prenotabile. Scegli un’altra data.'
        state.update(day=day.isoformat(),phase='party');return state,'Quante persone? Rispondi con un numero.'
    if phase=='party':
        if not body.isdecimal() or not 1<=int(body)<=venue.max_party_size:return state,f'Indica un numero da 1 a {venue.max_party_size}.'
        state['party']=int(body)
        slots=available_slots(db,venue,datetime.fromisoformat(state['day']).date(),state['party'],now())
        if not slots:state['phase']='day';return state,'Non ci sono tavoli disponibili per queste persone. Scegli un’altra data.'
        state.update(slots={s['label']:s['starts_at'].isoformat() for s in slots},phase='slot')
        return state,'Orari disponibili: '+', '.join(state['slots'])+'. Rispondi con un orario, ad esempio 19:00. Il tavolo verrà verificato di nuovo alla conferma.'
    if phase=='slot':
        if body not in state['slots']:return state,'Scegli uno degli orari elencati nel formato HH:MM, oppure scrivi RICOMINCIA.'
        state.update(starts=state['slots'][body],label=body,phase='name');return state,'A quale nome? Per questa prova usa nome e cognome fittizi.'
    if phase=='name':
        if not 2<=len(body)<=100 or any(ord(c)<32 for c in body):return state,'Indica un nome fittizio valido, da 2 a 100 caratteri.'
        state.update(name=body,phase='confirm')
        return state,f"Riepilogo: {venue.name}, {datetime.fromisoformat(state['day']).strftime('%d/%m/%Y')}, ore {state['label']}, {state['party']} persone, {state['name']}. Scrivi CONFERMO per inviare la prenotazione oppure ANNULLA."
    if phase=='confirm':
        if command!='confermo':return state,'Per inviare scrivi CONFERMO. Per azzerare il percorso scrivi ANNULLA.'
        slots=available_slots(db,venue,datetime.fromisoformat(state['day']).date(),state['party'],now())
        if state['starts'] not in {s['starts_at'].isoformat() for s in slots}:
            state['phase']='party';return state,'L’orario non è più disponibile. Indica di nuovo il numero di persone per vedere gli orari aggiornati.'
        booking=Booking(starts_at=datetime.fromisoformat(state['starts']),party_size=state['party'],name=state['name'],phone=phone,channel='whatsapp',whatsapp_opt_in=True,privacy_ack=True)
        reservation,token=create(db,venue,booking,source='whatsapp')
        result='Prenotazione confermata' if reservation.status=='CONFIRMED' else 'Richiesta ricevuta: serve l’approvazione del ristorante' if reservation.status=='PENDING_APPROVAL' else 'Prenotazione in attesa di acconto simulato'
        link=f'{base}/b/{venue.slug}#token={token}'
        return {'phase':'done'},f'{result}. Riferimento {reservation.public_reference}. Gestisci, modifica o cancella: {link}\nPer un’altra prenotazione scrivi RICOMINCIA.'
    return state,'La prenotazione è già stata inviata. Usa il link ricevuto per gestirla oppure scrivi RICOMINCIA.'

@router.get(PATH)
def status():
    return {'mode':'twilio-trial','enabled':os.getenv('WHATSAPP_DEMO_ENABLED')=='true','configured':all(os.getenv(k) for k in ('TWILIO_AUTH_TOKEN','TWILIO_ACCOUNT_SID','TWILIO_WHATSAPP_FROM')),'voice_enabled':False}

@router.post(PATH)
async def inbound(request:Request):
    logger.warning('WhatsApp trial: webhook ricevuto; firma presente=%s', bool(request.headers.get('x-twilio-signature')))
    if not settings.demo or os.getenv('WHATSAPP_DEMO_ENABLED')!='true':reject(503,'Demo WhatsApp non abilitata.')
    token=os.getenv('TWILIO_AUTH_TOKEN',''); account=os.getenv('TWILIO_ACCOUNT_SID',''); sender=os.getenv('TWILIO_WHATSAPP_FROM','')
    if not token or not account or not sender:reject(503,'Configurazione Twilio incompleta.')
    if 'application/x-www-form-urlencoded' not in request.headers.get('content-type',''):reject(415,'Formato webhook non valido.')
    raw=await request.body()
    if len(raw)>16384:reject(413,'Messaggio troppo grande.')
    try:values=parse_qs(raw.decode('utf8'),keep_blank_values=True,strict_parsing=True,max_num_fields=100)
    except (ValueError,UnicodeError):reject(400,'Webhook non valido.')
    if any(len(v)!=1 for v in values.values()):reject(400,'Parametri duplicati.')
    fields={k:v[0] for k,v in values.items()}
    # Fixed configured HTTPS origin: never trust a caller-provided Host header.
    url=settings.base_url.rstrip('/')+PATH
    if request.url.query:reject(400,'Query non supportata.')
    if not RequestValidator(token).validate(url,fields,request.headers.get('x-twilio-signature','')):reject(403,'Firma non valida.')
    if fields.get('AccountSid')!=account:reject(403,'Account Twilio non corrispondente.')
    if fields.get('To')!=sender:reject(403,'Numero mittente trial non corrispondente.')
    phone=fields.get('From','').removeprefix('whatsapp:'); sid=fields.get('MessageSid','')
    if not re.fullmatch(r'\+[1-9]\d{7,14}',phone) or not fields.get('From','').startswith('whatsapp:') or not re.fullmatch(r'SM[0-9a-fA-F]{32}',sid):reject(400,'Messaggio non valido.')
    with transaction() as db:
        route=db.scalar(select(VenueRoute).where(VenueRoute.slug==os.getenv('WHATSAPP_DEMO_VENUE','osteria-demo')))
        if not route:reject(503,'Ristorante demo non disponibile.')
        tenant,vid=route.tenant_id,route.venue_id
    with transaction(tenant) as db:
        venue=db.get(Venue,vid);tenant_lock(db,vid)
        identity=digest(account+sender+phone)
        convo=db.scalar(select(Conversation).where(Conversation.venue_id==vid,Conversation.channel=='whatsapp_trial',Conversation.provider_conversation_id==identity))
        if not convo:
            convo=Conversation(tenant_id=tenant,venue_id=vid,channel='whatsapp_trial',provider_conversation_id=identity);db.add(convo);db.flush()
        duplicate=db.scalar(select(ConversationMessage).where(ConversationMessage.conversation_id==convo.id,ConversationMessage.provider_message_id==sid,ConversationMessage.direction=='outbound'))
        if duplicate:return Response(xml(json.loads(decrypt(duplicate.redacted_body))['reply']),media_type='application/xml')
        recent=db.scalar(select(ConversationMessage).where(ConversationMessage.conversation_id==convo.id,ConversationMessage.direction=='outbound').order_by(ConversationMessage.created_at.desc(),ConversationMessage.id.desc()))
        state=json.loads(decrypt(recent.redacted_body))['state'] if recent and convo.last_inbound_at and convo.last_inbound_at>now()-timedelta(minutes=30) else {}
        state,reply=advance(db,venue,state,fields.get('Body',''),phone)
        convo.last_inbound_at=now()
        db.add(ConversationMessage(tenant_id=tenant,conversation_id=convo.id,direction='outbound',provider_message_id=sid,redacted_body=crypt(json.dumps({'state':state,'reply':reply})),retention_expires_at=now()+timedelta(days=1)))
    return Response(xml(reply),media_type='application/xml')
