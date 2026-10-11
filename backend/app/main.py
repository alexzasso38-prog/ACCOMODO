import csv, io, os, secrets
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, text, update
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.db import transaction, tenant_lock
from app.auth.security import identity, login, rate_limit, manager
from app.api.schemas import *
from app.domain.models import *
from uuid import UUID
from app.domain.availability import available_slots
from app.services import reservations as service

app=FastAPI(title='Accomodo',version='0.1.0',description='Demo isolata — nessun invio o incasso reale')
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=['GET','POST','PATCH'],allow_headers=['Content-Type','X-CSRF-Token','X-Booking-Token'])

@app.middleware('http')
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'; response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors "+' '.join(settings.origins)
    if os.getenv('FRONTEND_DIST') and not request.url.path.startswith(('/api/', '/docs', '/openapi.json')):
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    return response

@app.exception_handler(IntegrityError)
async def conflict(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409,content={'detail':'Conflitto di disponibilità o relazione non consentita. Ricarica e riprova.'})

def venue_for(db,who):
    q=select(Venue).where(Venue.tenant_id==who['tenant_id'])
    if who['venue_id']: q=q.where(Venue.id==who['venue_id'])
    venue=db.scalar(q.order_by(Venue.id))
    if not venue: raise HTTPException(404,'Sede non disponibile.')
    return venue

def route(slug):
    with transaction() as db:
        r=db.scalar(select(VenueRoute).where(VenueRoute.slug==slug))
        if not r: raise HTTPException(404,'Ristorante non trovato.')
        return r.tenant_id,r.venue_id

def booking_for(db,venue,rid,lock=True):
    q=select(Reservation).where(Reservation.id==rid,Reservation.venue_id==venue.id)
    if lock: q=q.with_for_update()
    r=db.scalar(q)
    if not r: raise HTTPException(404,'Prenotazione non trovata.')
    return r

def access(db,venue,token):
    if not token: raise HTTPException(401,'Link di accesso richiesto.')
    t=db.scalar(select(BookingAccessToken).where(BookingAccessToken.token_hash==service.digest(token),BookingAccessToken.revoked_at.is_(None),BookingAccessToken.expires_at>now()))
    if not t: raise HTTPException(404,'Link non valido o scaduto.')
    return booking_for(db,venue,t.reservation_id)

def venue_public(v):
    return {'name':v.name,'slug':v.slug,'address':v.address,'timezone':v.timezone,'booking_mode':v.booking_mode,'max_party_size':v.max_party_size,'menu_url':v.menu_url,'directions_url':v.directions_url,'pending_policy':f'La richiesta occupa i tavoli per {v.pending_expiry_minutes} minuti e richiede approvazione.','deposit':service.money(v.deposit_cents,v.deposit_tax_rate) if v.deposit_cents and v.deposit_tax_rate is not None else {},'demo':settings.demo}

@app.get('/health')
def health(): return {'status':'ok','demo':settings.demo,'real_messages':False}
@app.get('/ready')
def ready():
    from app.auth.security import redis
    with transaction() as db:
        role=db.execute(text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user')).one()
        if any(role): raise HTTPException(503,'Ruolo database non sicuro.')
        db.execute(text('SELECT 1 FROM venues LIMIT 1'))
    try: redis.ping()
    except Exception: raise HTTPException(503,'Redis non disponibile.')
    return {'status':'ready'}

@app.post('/api/auth/login')
def signin(data:Login,request:Request,response:Response):
    rate_limit(request,'login',10)
    if request.headers.get('origin') and request.headers['origin'] not in settings.origins: raise HTTPException(403,'Origine non autorizzata.')
    with transaction() as db: raw,csrf,m=login(db,data.email,data.password,data.otp)
    response.set_cookie('tavolo_session',raw,httponly=True,secure=settings.base_url.startswith('https://'),samesite='lax',max_age=28800,path='/')
    return {'csrf_token':csrf,'role':m.role}
@app.post('/api/auth/logout')
def logout(response:Response,who=Depends(identity)):
    with transaction() as db: db.get(Session,who['session_id']).revoked_at=now()
    response.delete_cookie('tavolo_session',path='/')
    return {'ok':True}
@app.get('/api/auth/me')
def me(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        return {'email':who['email'],'role':who['role'],'venue':venue_public(v),'tenant_id':str(who['tenant_id'])}

@app.get('/api/public/{slug}',response_model=VenueView)
def public_venue(slug:str):
    tenant,vid=route(slug)
    with transaction(tenant) as db: return venue_public(db.get(Venue,vid))
@app.get('/api/public/{slug}/availability',response_model=list[SlotView])
def availability(slug:str,day:date,party_size:int,request:Request):
    rate_limit(request,'availability',180)
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid)
        if not 1<=party_size<=v.max_party_size: raise HTTPException(422,'Numero persone non ammesso.')
        return available_slots(db,v,day,party_size,now())
@app.post('/api/public/{slug}/reservations',status_code=201,response_model=BookingCreated)
def public_create(slug:str,data:Booking,request:Request):
    rate_limit(request,'booking',30)
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); r,token=service.create(db,v,data)
        return {'reservation':service.serialize(db,r,True),'access_token':token,'manage_url':f'{settings.base_url}/b/{slug}#token={token}'}
@app.get('/api/public/{slug}/booking',response_model=ReservationView)
def public_booking(slug:str,x_booking_token:str=Header(default='')):
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); tenant_lock(db,vid); service.expire(db,v,now()); r=access(db,v,x_booking_token)
        return service.serialize(db,r,True)
@app.patch('/api/public/{slug}/booking',response_model=ReservationView)
def public_modify(slug:str,data:Change,x_booking_token:str=Header(default='')):
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); tenant_lock(db,vid); service.expire(db,v,now()); r=access(db,v,x_booking_token)
        service.modify(db,v,r,data); return service.serialize(db,r,True)
@app.post('/api/public/{slug}/booking/cancel',response_model=ReservationView)
def public_cancel(slug:str,data:StatusChange,x_booking_token:str=Header(default='')):
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); tenant_lock(db,vid); service.expire(db,v,now()); r=access(db,v,x_booking_token)
        if data.status!='CANCELLED': raise HTTPException(422,'Operazione non consentita.')
        if r.version!=data.version: raise HTTPException(409,'Prenotazione modificata. Ricarica.')
        if r.starts_at<=now(): raise HTTPException(409,'Contatta il locale per cancellare dopo l’inizio.')
        service.change_status(db,r,'CANCELLED',v,actor='customer'); return service.serialize(db,r,True)
@app.post('/api/public/{slug}/booking/finalize',response_model=ReservationView)
def finalize(slug:str,x_booking_token:str=Header(default='')):
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); tenant_lock(db,vid); service.expire(db,v,now()); r=access(db,v,x_booking_token)
        if r.status!='HOLD': raise HTTPException(409,'Opzione scaduta o già finalizzata.')
        target='PENDING_APPROVAL' if v.booking_mode=='manual' else 'AWAITING_PAYMENT' if r.deposit_policy_snapshot else 'CONFIRMED'
        r.pending_expires_at=now()+timedelta(minutes=v.pending_expiry_minutes) if target=='PENDING_APPROVAL' else None
        service.change_status(db,r,target,v,actor='customer'); service.enqueue(db,r,'received')
        return service.serialize(db,r,True)
@app.get('/api/public/{slug}/booking/calendar.ics')
def calendar(slug:str,x_booking_token:str=Header(default='')):
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); r=access(db,v,x_booking_token)
        if r.status not in {'CONFIRMED','SEATED'}: raise HTTPException(409,'Calendario disponibile dopo la conferma.')
        fmt=lambda d:d.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        body='\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Accomodo//Booking//IT','BEGIN:VEVENT',f'UID:{r.id}@tavolo',f'DTSTAMP:{fmt(now())}',f'DTSTART:{fmt(r.starts_at)}',f'DTEND:{fmt(r.ends_at)}','SUMMARY:Prenotazione ristorante','END:VEVENT','END:VCALENDAR',''])
        return Response(body,media_type='text/calendar',headers={'Content-Disposition':'attachment; filename="prenotazione.ics"'})

@app.get('/api/admin/reservations',response_model=list[ReservationView])
def agenda(day:date,who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); service.expire(db,v,now())
        start=datetime.combine(day,datetime.min.time(),ZoneInfo(v.timezone)); end=datetime.combine(day+timedelta(days=1),datetime.min.time(),ZoneInfo(v.timezone))
        return [service.serialize(db,r) for r in db.scalars(select(Reservation).where(Reservation.venue_id==v.id,Reservation.starts_at>=start,Reservation.starts_at<end).order_by(Reservation.starts_at))]
@app.post('/api/admin/reservations',status_code=201,response_model=BookingCreated)
def staff_create(data:Booking,walk_in:bool=False,who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); r,token=service.create(db,v,data,source='walk_in' if walk_in else 'staff',actor_id=who['user_id'])
        return {'reservation':service.serialize(db,r),'access_token':token,'manage_url':f'{settings.base_url}/b/{v.slug}#token={token}'}
@app.patch('/api/admin/reservations/{rid}',response_model=ReservationView)
def staff_modify(rid:UUID,data:Change,who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); tenant_lock(db,v.id); service.expire(db,v,now()); r=booking_for(db,v,rid)
        service.modify(db,v,r,data,who['user_id']); return service.serialize(db,r)
@app.post('/api/admin/reservations/{rid}/status',response_model=ReservationView)
def staff_status(rid:UUID,data:StatusChange,who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); tenant_lock(db,v.id); service.expire(db,v,now()); r=booking_for(db,v,rid)
        if r.version!=data.version: raise HTTPException(409,'Prenotazione già modificata. Ricarica.')
        if data.status=='CONFIRMED' and r.deposit_policy_snapshot and r.status=='PENDING_APPROVAL':
            service.change_status(db,r,'AWAITING_PAYMENT',v,actor_id=who['user_id'])
        else: service.change_status(db,r,data.status,v,actor_id=who['user_id'])
        return service.serialize(db,r)
@app.get('/api/admin/resources')
def resources(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        return [{'id':str(t.id),'name':t.name,'min_guests':t.min_guests,'max_guests':t.max_guests,'enabled':t.enabled} for t in db.scalars(select(Resource).where(Resource.venue_id==v.id).order_by(Resource.name))]
@app.post('/api/admin/resources')
def table_create(data:TableCreate,who=Depends(identity)):
    manager(who)
    if data.max_guests<data.min_guests: raise HTTPException(422,'Capienza massima inferiore alla minima.')
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); room=db.scalar(select(Room).where(Room.venue_id==v.id))
        r=Resource(tenant_id=v.tenant_id,venue_id=v.id,room_id=room.id,**data.model_dump()); db.add(r); db.flush()
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='resource_created',target_type='resource',target_id=r.id))
        return {'id':str(r.id)}
@app.get('/api/admin/settings')
def config(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        return {k:getattr(v,k) for k in VenueSettings.model_fields}|{'integrations':{'email':'Simulata','whatsapp':'Non verificata con provider','sms':'Non verificata con provider','telephony':'Simulatore locale','stripe':'Acconti simulati; nessun incasso','voice_ai':'Disattivata'},'pending_policy':'Le richieste in attesa bloccano i tavoli.','policy_version':v.policy_version}
@app.patch('/api/admin/settings')
def update_settings(data:VenueSettings,who=Depends(identity)):
    manager(who)
    if data.deposit_cents and data.deposit_tax_rate is None: raise HTTPException(422,'Specifica l’aliquota dell’acconto del ristorante.')
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); tenant_lock(db,v.id)
        for k,value in data.model_dump().items(): setattr(v,k,value)
        v.policy_version+=1
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='settings_changed',target_type='venue',target_id=v.id,redacted_diff=data.model_dump(mode='json')))
    return {'ok':True}
@app.post('/api/admin/exceptions')
def exception_create(data:ExceptionCreate,who=Depends(identity)):
    manager(who)
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); tenant_lock(db,v.id)
        if not data.closed: raise HTTPException(422,'Per orari sostitutivi usare configurazione amministrata, non una riapertura implicita.')
        existing=db.scalar(select(CalendarException).where(CalendarException.venue_id==v.id,CalendarException.local_date==data.local_date))
        if existing: existing.closed=True; existing.reason=data.reason
        else: db.add(CalendarException(tenant_id=v.tenant_id,venue_id=v.id,**data.model_dump()))
    return {'ok':True,'warning':'Le prenotazioni già confermate restano visibili: contattare gli ospiti prima di cambiarle.'}
@app.post('/api/admin/blocks')
def block_create(data:BlockCreate,who=Depends(identity)):
    manager(who)
    if not data.starts_at.tzinfo or not data.ends_at.tzinfo or data.ends_at<=data.starts_at: raise HTTPException(422,'Intervallo non valido.')
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); tenant_lock(db,v.id)
        r=db.scalar(select(Resource).where(Resource.id==UUID(str(data.resource_id)),Resource.venue_id==v.id))
        if not r: raise HTTPException(404,'Accomodo non trovato.')
        if db.scalar(select(Allocation.id).where(Allocation.resource_id==r.id,Allocation.active.is_(True),Allocation.starts_at<data.ends_at,Allocation.ends_at>data.starts_at)):
            raise HTTPException(409,'Il tavolo ha prenotazioni nell’intervallo.')
        db.add(ResourceBlock(tenant_id=v.tenant_id,venue_id=v.id,resource_id=r.id,starts_at=data.starts_at,ends_at=data.ends_at,reason=data.reason))
    return {'ok':True}
@app.get('/api/admin/customers')
def customers(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        return [{'id':str(c.id),'name':c.name,'channel':c.preferred_channel,'contact':'Recapito protetto'} for c in db.scalars(select(Customer).join(Reservation,Reservation.customer_id==Customer.id).where(Reservation.venue_id==venue_for(db,who).id).distinct().order_by(Customer.name))]
@app.get('/api/admin/report')
def report(start:date,end:date,who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        a=datetime.combine(start,datetime.min.time(),ZoneInfo(v.timezone)); b=datetime.combine(end+timedelta(days=1),datetime.min.time(),ZoneInfo(v.timezone))
        rows=db.scalars(select(Reservation).where(Reservation.venue_id==v.id,Reservation.starts_at>=a,Reservation.starts_at<b)).all()
        counts={s:sum(r.status==s for r in rows) for s in service.TRANSITIONS}
        return {'requests':len(rows),'statuses':counts,'served_guests':sum(r.party_size for r in rows if r.status=='COMPLETED'),'channels':{s:sum(r.source==s for r in rows) for s in ['web','staff','walk_in']},'revenue':None,'roi':None,'usage':[{'channel':u.channel,'quantity':str(u.quantity),'unit':u.unit,'billable_quantity':str(u.billable_quantity)} for u in db.scalars(select(UsageLedger).where(UsageLedger.venue_id==v.id))]}

def csv_safe(v):
    s=str(v)
    return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
@app.get('/api/admin/export.csv')
def export(who=Depends(identity)):
    manager(who)
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who); output=io.StringIO(); writer=csv.writer(output)
        writer.writerow(['Riferimento','Data UTC','Persone','Stato','Nome'])
        for r in db.scalars(select(Reservation).where(Reservation.venue_id==v.id).order_by(Reservation.starts_at)):
            c=db.get(Customer,r.customer_id); writer.writerow([csv_safe(x) for x in [r.public_reference,r.starts_at.isoformat(),r.party_size,r.status,c.name]])
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='reservation_export',target_type='venue',target_id=v.id))
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="prenotazioni.csv"'})

@app.get('/api/admin/notifications')
def notifications(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        events=db.scalars(select(OutboxEvent).join(Reservation,Reservation.id==OutboxEvent.aggregate_id).where(Reservation.venue_id==v.id).order_by(OutboxEvent.created_at.desc()).limit(100)).all()
        return [{'id':str(e.id),'type':e.event_type,'status':e.status,'attempts':e.attempts,'available_at':e.available_at} for e in events]
@app.post('/api/demo/dispatch')
def dispatch(who=Depends(identity)):
    if not settings.demo: raise HTTPException(404)
    from app.workers.tasks import process_tenant
    return process_tenant(str(who['tenant_id']))
@app.post('/api/demo/phone')
def simulate_phone(data:PhoneSim,who=Depends(identity)):
    if not settings.demo: raise HTTPException(404)
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        from app.services.subscriptions import permitted
        allowed,_=permitted(db,v,'telephony',Decimal('0.3333'))
        human=not allowed or data.hidden or not data.mobile or not data.whatsapp or data.provider_failure
        call=CallSession(tenant_id=v.tenant_id,venue_id=v.id,provider_call_id='sim-'+secrets.token_hex(12),route='human' if human else 'ivr',outcome='human_fallback' if human else 'booking_link_simulated',whatsapp_opt_in_reference='keypad-1-demo' if data.whatsapp and not data.hidden else None,duration_seconds=20,ended_at=now())
        db.add(call); db.flush()
        db.add(UsageLedger(tenant_id=v.tenant_id,venue_id=v.id,channel='telephony_simulated',quantity=Decimal('0.3333'),unit='minute',deduplication_key='call:'+str(call.id),billable_quantity=0))
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='phone_simulated',target_type='call',target_id=call.id))
        return {'greeting':f'Benvenuto da {v.name}. Sono l’assistente automatico. Premi 1 per richiedere il link WhatsApp, 2 per parlare con il locale.','outcome':'Trasferimento al locale simulato' if human else 'WhatsApp simulato: apri il link di prenotazione','booking_url':None if human else '/b/'+v.slug,'recording':False,'real_message_sent':False}
@app.post('/api/public/{slug}/booking/payment-simulation')
def payment_simulation(slug:str,data:SimPayment,x_booking_token:str=Header(default='')):
    if not settings.demo: raise HTTPException(404)
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid); tenant_lock(db,vid); service.expire(db,v,now()); r=access(db,v,x_booking_token)
        key='simulation:'+str(r.id)
        p=db.scalar(select(Payment).where(Payment.idempotency_key==key))
        if p: return {'payment_status':p.status,'reservation':service.serialize(db,r,True),'simulation':True}
        if r.status!='AWAITING_PAYMENT': raise HTTPException(409,'Prenotazione non in attesa di pagamento; nessun incasso.')
        if not r.deposit_policy_snapshot: raise HTTPException(409,'Nessun acconto previsto.')
        amount=r.deposit_policy_snapshot
        p=Payment(tenant_id=tenant,venue_id=vid,reservation_id=r.id,provider='simulation',provider_payment_id='sim-'+secrets.token_hex(12),idempotency_key=key,amount_net=amount['amount_net'],tax_amount=amount['tax_amount'],amount_total=amount['amount_total'],status='succeeded',captured_at=now())
        db.add(p); db.flush()
        db.add(WebhookReceipt(provider='simulation',provider_account_reference=str(vid),event_id=data.event_id,signature_valid=True,status='simulated',processed_at=now()))
        service.change_status(db,r,'CONFIRMED',v,actor='payment-simulation')
        return {'payment_status':p.status,'reservation':service.serialize(db,r,True),'simulation':True}
@app.post('/api/webhooks/{provider}')
def unconfigured_webhooks(provider:str):
    raise HTTPException(503,'Integrazione reale non verificata e non attivata. Usare il simulatore locale.')

@app.get('/api/pricing')
def pricing():
    plans=[('Start',29000,9900,300,100),('Concierge',49000,14900,1000,300),('Voice',79000,24900,1000,300)]
    return {'assumption':True,'per':'sede','plans':[{'name':n,'setup':service.money(s,22),'monthly':service.money(m,22),'whatsapp_included':w,'minutes_included':t,'available':n!='Voice'} for n,s,m,w,t in plans],'overages_enabled':False,'trial_days':14,'automatic_paid_conversion':False,'first_five':{'setup':service.money(29000,22),'plan':'Concierge'},'fiscal_issuance':False}

@app.post('/api/admin/combinations')
def combination_create(data:CombinationCreate,who=Depends(identity)):
    manager(who)
    ids=sorted(set(UUID(str(x)) for x in data.resource_ids))
    if len(ids)!=len(data.resource_ids) or data.max_guests<data.min_guests: raise HTTPException(422,'Combinazione non valida.')
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who);tenant_lock(db,v.id)
        tables=db.scalars(select(Resource).where(Resource.id.in_(ids),Resource.venue_id==v.id).order_by(Resource.id).with_for_update()).all()
        if len(tables)!=len(ids): raise HTTPException(404,'Tavoli non trovati nella sede.')
        if data.max_guests>sum(t.max_guests for t in tables): raise HTTPException(422,'Capienza superiore ai tavoli fisici.')
        combo=ResourceCombination(tenant_id=v.tenant_id,venue_id=v.id,name=data.name,min_guests=data.min_guests,max_guests=data.max_guests);db.add(combo);db.flush()
        for rid in ids:db.add(CombinationMember(tenant_id=v.tenant_id,venue_id=v.id,combination_id=combo.id,resource_id=rid))
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='combination_created',target_type='combination',target_id=combo.id))
        return {'id':str(combo.id)}
@app.get('/api/admin/schedules')
def schedules(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        return [{'id':str(s.id),**{k:getattr(s,k) for k in ScheduleCreate.model_fields}} for s in db.scalars(select(ServiceSchedule).where(ServiceSchedule.venue_id==v.id).order_by(ServiceSchedule.weekday,ServiceSchedule.local_start_time))]
@app.post('/api/admin/schedules')
def schedule_create(data:ScheduleCreate,who=Depends(identity)):
    manager(who)
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who);tenant_lock(db,v.id)
        # Additive changes do not delete existing services or confirmed reservations.
        db.add(ServiceSchedule(tenant_id=v.tenant_id,venue_id=v.id,**data.model_dump()))
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='schedule_created',target_type='venue',target_id=v.id))
    return {'ok':True}
@app.post('/api/admin/privacy/anonymize')
def privacy_anonymize(data:PrivacyAction,who=Depends(identity)):
    manager(who)
    if not data.identity_verified: raise HTTPException(422,'Identità del richiedente da verificare prima dell’operazione.')
    from app.services.privacy import anonymize_customer
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who);tenant_lock(db,v.id)
        c=db.get(Customer,UUID(str(data.customer_id)))
        if not c: raise HTTPException(404,'Ospite non trovato.')
        anonymize_customer(db,c,who['user_id'])
        db.add(PrivacyRequest(tenant_id=v.tenant_id,requester_reference=str(c.id),type='erase',identity_verified_at=now(),status='completed-anonymized',deadline=now()+timedelta(days=30),completed_at=now()))
    return {'ok':True,'method':'Anonymized identifiers; anonymous reservation statistics retained; separate fiscal retention not configured.'}
@app.post('/api/admin/privacy/export')
def privacy_export(data:PrivacyAction,who=Depends(identity)):
    manager(who)
    if not data.identity_verified: raise HTTPException(422,'Identità non verificata.')
    from app.auth.security import decrypt
    with transaction(who['tenant_id']) as db:
        c=db.get(Customer,UUID(str(data.customer_id)))
        if not c: raise HTTPException(404,'Ospite non trovato.')
        db.add(AuditLog(tenant_id=c.tenant_id,actor_id=who['user_id'],action='privacy_export',target_type='customer',target_id=c.id))
        return {'name':c.name,'email':decrypt(c.email),'phone':decrypt(c.phone_e164),'reservations':[service.serialize(db,r,True) for r in db.scalars(select(Reservation).where(Reservation.customer_id==c.id))]}

@app.post('/api/public/{slug}/waitlist',status_code=201)
def waitlist_create(slug:str,data:WaitlistCreate,request:Request):
    rate_limit(request,'waitlist',10)
    if not data.privacy_ack or not data.starts_at.tzinfo or not data.ends_at.tzinfo or data.ends_at<=data.starts_at:
        raise HTTPException(422,'Intervallo e presa visione dell’informativa richiesti.')
    from app.auth.security import crypt
    # Reuse booking input validation for contact and name; no automatic booking is made.
    from pydantic import ValidationError
    try: checked=Booking(starts_at=data.starts_at,party_size=data.party_size,name=data.name,email=data.email,privacy_ack=True)
    except ValidationError: raise HTTPException(422,'Nome o recapito non valido.')
    tenant,vid=route(slug)
    with transaction(tenant) as db:
        v=db.get(Venue,vid)
        if data.party_size>v.max_party_size or data.starts_at<now() or data.ends_at>now()+timedelta(days=v.booking_horizon_days):raise HTTPException(422,'Richiesta fuori dai limiti della sede.')
        c=Customer(tenant_id=tenant,name=checked.name,email=crypt(checked.email),preferred_channel='email');db.add(c);db.flush()
        consent=ConsentRecord(tenant_id=tenant,customer_id=c.id,purpose='waitlist_offer',channel='email',granted=True,source='web',policy_version='demo-v1',evidence_reference='explicit-waitlist-request');db.add(consent);db.flush()
        w=WaitlistEntry(tenant_id=tenant,venue_id=vid,customer_id=c.id,desired_start=data.starts_at,desired_end=data.ends_at,party_size=data.party_size,consent_reference=consent.id);db.add(w);db.flush()
        return {'reference':str(w.id),'status':'waiting','message':'Richiesta lista d’attesa ricevuta. Non è una prenotazione né una conferma.'}
@app.get('/api/admin/waitlist')
def waitlist(who=Depends(identity)):
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who)
        return [{'id':str(w.id),'name':db.get(Customer,w.customer_id).name,'starts_at':w.desired_start,'ends_at':w.desired_end,'party_size':w.party_size,'status':w.status,'offer_expires_at':w.offer_expires_at} for w in db.scalars(select(WaitlistEntry).where(WaitlistEntry.venue_id==v.id).order_by(WaitlistEntry.desired_start))]
@app.post('/api/admin/waitlist/{wid}/offer')
def waitlist_offer(wid:UUID,who=Depends(identity)):
    from app.auth.security import decrypt
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who);tenant_lock(db,v.id);service.expire(db,v,now())
        w=db.scalar(select(WaitlistEntry).where(WaitlistEntry.id==wid,WaitlistEntry.venue_id==v.id).with_for_update())
        if not w:raise HTTPException(404,'Richiesta non trovata.')
        if w.status!='waiting':raise HTTPException(409,'Offerta già creata o richiesta non attiva.')
        consent=db.get(ConsentRecord,w.consent_reference)
        if not consent or not consent.granted or consent.revoked_at:raise HTTPException(409,'Consenso al canale non valido.')
        c=db.get(Customer,w.customer_id)
        r,token=service.create(db,v,Booking(starts_at=w.desired_start,party_size=w.party_size,name=c.name,email=decrypt(c.email),privacy_ack=True,hold=True),source='waitlist',actor_id=who['user_id'])
        w.status='offered';w.offer_expires_at=r.hold_expires_at;w.offered_reservation_id=r.id
        return {'reservation':service.serialize(db,r,True),'manage_url':f'{settings.base_url}/b/{v.slug}#token={token}','simulation':True,'message':'Offerta temporanea di 5 minuti; link da copiare soltanto nella demo.'}

@app.get('/api/admin/usage')
def usage_state(who=Depends(identity)):
    from app.services.subscriptions import usage
    with transaction(who['tenant_id']) as db:return usage(db,venue_for(db,who))
@app.post('/api/admin/billing/quote',status_code=201)
def billing_quote(data:QuoteCreate,who=Depends(identity)):
    manager(who)
    amounts={'Start':(29000,9900),'Concierge':(49000,14900),'Voice':(79000,24900)}
    if data.plan=='Voice':raise HTTPException(409,'Voice non disponibile; non proporre una vendita attivabile prima dei test di fase 2.')
    with transaction(who['tenant_id']) as db:
        v=venue_for(db,who);tenant=db.get(Tenant,v.tenant_id);tax=tenant.default_tax_rate
        setup,monthly=amounts[data.plan]
        if data.first_five_offer:
            if data.plan!='Concierge':raise HTTPException(422,'L’offerta primi 5 riguarda Concierge.')
            # Demo quote only; eligibility is not inferred, and no invoice/payment is created.
            setup=29000
        lines=[('Canone mensile '+data.plan,monthly)]
        if data.include_setup:lines.append(('Setup '+data.plan,setup))
        totals=[service.money(amount,tax) for _,amount in lines]
        document=BillingDocument(tenant_id=v.tenant_id,document_type='quote',number='DEMO-'+secrets.token_hex(8).upper(),status='draft',subtotal_net=sum(x['amount_net'] for x in totals),tax_total=sum(x['tax_amount'] for x in totals),grand_total=sum(x['amount_total'] for x in totals))
        db.add(document);db.flush()
        for (description,amount),total in zip(lines,totals):
            db.add(BillingLine(tenant_id=v.tenant_id,document_id=document.id,description=description,quantity=1,unit_net=amount,discount_net=0,tax_rate=tax,line_net=amount,line_tax=total['tax_amount'],line_total=total['amount_total']))
        db.add(AuditLog(tenant_id=v.tenant_id,actor_id=who['user_id'],action='quote_created',target_type='billing_document',target_id=document.id))
        return {'id':str(document.id),'number':document.number,'type':'quote','fiscal_document_issued':False,'charged':False,'amount_net':document.subtotal_net,'tax_amount':document.tax_total,'amount_total':document.grand_total,'tax_rate':str(tax),'currency':'EUR','commercial_assumption':True,'lines':[{'description':d,**t} for (d,_),t in zip(lines,totals)]}

# Hosted demo serves the built UI on the same HTTPS origin as its API.
if os.getenv('FRONTEND_DIST'):
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StarletteHTTPException
    class DemoSPA(StaticFiles):
        async def get_response(self, path, scope):
            if path.startswith(('api/', 'docs', 'openapi.json')):
                raise StarletteHTTPException(404)
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if exc.status_code != 404 or '.' in path.rsplit('/', 1)[-1]:
                    raise
                return await super().get_response('index.html', scope)
    app.mount('/', DemoSPA(directory=os.environ['FRONTEND_DIST'], html=True), name='demo-ui')
