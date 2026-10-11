import secrets, hashlib
from datetime import timedelta, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, update, or_
from fastapi import HTTPException
from app.domain.models import *
from app.domain.availability import candidates, validate_slot, arrival_count, validate_walkin
from app.db import tenant_lock

TRANSITIONS={
 'HOLD':{'PENDING_APPROVAL','AWAITING_PAYMENT','CONFIRMED','CANCELLED','EXPIRED'},
 'PENDING_APPROVAL':{'AWAITING_PAYMENT','CONFIRMED','REJECTED','CANCELLED','EXPIRED'},
 'AWAITING_PAYMENT':{'CONFIRMED','CANCELLED','EXPIRED'},
 'CONFIRMED':{'SEATED','CANCELLED','NO_SHOW'}, 'SEATED':{'COMPLETED'},
 'COMPLETED':set(),'CANCELLED':set(),'EXPIRED':set(),'REJECTED':set(),'NO_SHOW':set()
}
TERMINAL={'COMPLETED','CANCELLED','EXPIRED','REJECTED','NO_SHOW'}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def money(net_cents, rate):
    tax=int((Decimal(net_cents)*Decimal(str(rate))/100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return {'amount_net':net_cents,'tax_amount':tax,'amount_total':net_cents+tax,'tax_rate':str(rate),'currency':'EUR'}

def event(db,r,kind,previous=None,actor='system',actor_id=None):
    db.add(ReservationEvent(tenant_id=r.tenant_id,reservation_id=r.id,actor_type=actor,actor_id=actor_id,previous_status=previous,next_status=r.status,event_type=kind))
    db.add(AuditLog(tenant_id=r.tenant_id,actor_id=actor_id,action=kind,target_type='reservation',target_id=r.id,redacted_diff={'status':r.status,'version':r.version}))

def enqueue(db,r,kind,at=None):
    c=db.get(Customer,r.customer_id)
    if not c.email and not c.phone_e164:return
    key=f'{r.id}:{r.version}:{kind}'
    db.add(OutboxEvent(tenant_id=r.tenant_id,aggregate_id=r.id,event_type=kind,payload={'version':r.version},available_at=at or now(),deduplication_key=key))

def cancel_reminders(db,r):
    db.execute(update(OutboxEvent).where(OutboxEvent.aggregate_id==r.id,OutboxEvent.event_type=='reminder',OutboxEvent.status.in_(['pending','retry'])).values(status='cancelled'))

def reminder(db,r,venue,clock):
    if r.status!='CONFIRMED': return
    from zoneinfo import ZoneInfo
    due=r.starts_at-timedelta(hours=24)
    # Late bookings receive their immediate confirmation only.
    if due<=clock: return
    local=due.astimezone(ZoneInfo(venue.timezone))
    start,end=venue.reminder_quiet_start,venue.reminder_quiet_end
    quiet=(local.hour>=start or local.hour<end) if start>end else start<=local.hour<end
    if quiet:
        # Move earlier, never after the appointment.
        day=local.date() if local.hour>=start else local.date()-timedelta(days=1)
        from app.domain.availability import local_to_utc
        due=local_to_utc(datetime.combine(day,time(start,0)),venue.timezone)-timedelta(minutes=1)
    if due>clock: enqueue(db,r,'reminder',due)

def change_status(db,r,target,venue,actor='staff',actor_id=None,clock=None):
    clock=clock or now()
    if target not in TRANSITIONS[r.status]: raise HTTPException(409,'Passaggio di stato non consentito.')
    if target=='CONFIRMED' and r.deposit_policy_snapshot.get('amount_total',0)>0:
        paid=db.scalar(select(Payment).where(Payment.reservation_id==r.id,Payment.status=='succeeded'))
        if not paid: raise HTTPException(409,'Conferma disponibile soltanto dopo il pagamento.')
    prev=r.status; r.status=target; r.version+=1
    cancel_reminders(db,r)
    if target in TERMINAL:
        db.execute(update(Allocation).where(Allocation.reservation_id==r.id).values(active=False))
        if target in {'CANCELLED','REJECTED'}:
            for p in db.scalars(select(Payment).where(Payment.reservation_id==r.id,Payment.status=='succeeded')):
                if p.provider=='simulation':
                    db.add(Refund(tenant_id=r.tenant_id,payment_id=p.id,amount=p.amount_total,reason='policy-demo-full',status='simulated',idempotency_key=f'refund:{p.id}'))
                    p.status='refunded'
    event(db,r,target.lower(),prev,actor,actor_id)
    if target in {'CONFIRMED','CANCELLED','REJECTED'}: enqueue(db,r,target.lower())
    if target=='AWAITING_PAYMENT':
        r.payment_expires_at=clock+timedelta(minutes=15); enqueue(db,r,'payment_due')
    reminder(db,r,venue,clock)
    db.flush()

def expire(db,venue,clock):
    tenant_lock(db,venue.id)
    q=select(Reservation).where(Reservation.venue_id==venue.id,or_(
        (Reservation.status=='HOLD') & (Reservation.hold_expires_at<=clock),
        (Reservation.status=='PENDING_APPROVAL') & (Reservation.pending_expires_at<=clock),
        (Reservation.status=='AWAITING_PAYMENT') & (Reservation.payment_expires_at<=clock))).order_by(Reservation.id).with_for_update()
    for r in db.scalars(q): change_status(db,r,'EXPIRED',venue,clock=clock,actor='system')

def allocate(db,venue,r,starts,party,clock):
    starts,ends,limit=(validate_walkin if r.source=='walk_in' else validate_slot)(db,venue,starts,party,clock)
    if limit is not None and arrival_count(db,venue,starts,ignore=r.id,clock=clock)>=limit:
        raise HTTPException(409,'Limite degli arrivi raggiunto. Scegli un altro orario.')
    choices=candidates(db,venue,starts,ends,party,ignore=r.id,lock=True)
    if not choices: raise HTTPException(409,'Orario non più disponibile. Scegli un’alternativa.')
    # Nothing is mutated before availability is known. The transaction rolls back on failure.
    db.execute(update(Allocation).where(Allocation.reservation_id==r.id).values(active=False))
    db.flush()
    for resource in choices[0][1]:
        db.add(Allocation(tenant_id=venue.tenant_id,venue_id=venue.id,reservation_id=r.id,resource_id=resource,starts_at=starts,ends_at=ends))
    r.starts_at=starts; r.ends_at=ends; r.party_size=party
    db.flush()

def create(db,venue,data,source='web',actor_id=None,clock=None):
    clock=clock or now(); tenant_lock(db,venue.id); expire(db,venue,clock)
    starts,ends,_=(validate_walkin if source=='walk_in' else validate_slot)(db,venue,data.starts_at,data.party_size,clock)
    from app.auth.security import crypt
    if data.channel=='email' and not data.email and source in {'web','waitlist'}: raise HTTPException(422,'Indica un’email per questo canale.')
    if data.channel in {'whatsapp','sms'} and not data.phone: raise HTTPException(422,'Indica il numero per questo canale.')
    customer=Customer(tenant_id=venue.tenant_id,name=data.name.strip(),email=crypt(data.email),phone_e164=crypt(data.phone),preferred_channel=data.channel)
    db.add(customer); db.flush()
    db.add(ConsentRecord(tenant_id=venue.tenant_id,customer_id=customer.id,purpose='booking_processing',channel='web',granted=True,source='staff' if source!='web' else 'web',policy_version='demo-v1'))
    db.add(ConsentRecord(tenant_id=venue.tenant_id,customer_id=customer.id,purpose='whatsapp_opt_in',channel='whatsapp',granted=data.whatsapp_opt_in,source='staff' if source!='web' else 'web',policy_version='demo-v1'))
    if venue.deposit_cents and venue.deposit_tax_rate is None: raise HTTPException(409,'Acconto non configurato: aliquota mancante.')
    snapshot=money(venue.deposit_cents,venue.deposit_tax_rate) if venue.deposit_cents and source!='walk_in' else {}
    status='SEATED' if source=='walk_in' else 'HOLD' if data.hold else 'PENDING_APPROVAL' if venue.booking_mode=='manual' else 'AWAITING_PAYMENT' if snapshot else 'CONFIRMED'
    r=Reservation(tenant_id=venue.tenant_id,venue_id=venue.id,customer_id=customer.id,starts_at=starts,ends_at=ends,party_size=data.party_size,source=source,status=status,public_reference=secrets.token_hex(5).upper(),hold_expires_at=clock+timedelta(minutes=5) if status=='HOLD' else None,pending_expires_at=clock+timedelta(minutes=venue.pending_expiry_minutes) if status=='PENDING_APPROVAL' else None,payment_expires_at=clock+timedelta(minutes=15) if status=='AWAITING_PAYMENT' else None,cancellation_policy_snapshot={'version':'demo-v1','free_until_start':True,'refund':'full-simulation'},deposit_policy_snapshot=snapshot)
    db.add(r); db.flush(); allocate(db,venue,r,starts,data.party_size,clock)
    event(db,r,'created',actor='customer' if source=='web' else 'staff',actor_id=actor_id)
    if status!='HOLD': enqueue(db,r,'received')
    if status in {'CONFIRMED','SEATED'}: enqueue(db,r,'confirmed'); reminder(db,r,venue,clock)
    if status=='AWAITING_PAYMENT': enqueue(db,r,'payment_due')
    token=secrets.token_urlsafe(32)
    db.add(BookingAccessToken(tenant_id=r.tenant_id,reservation_id=r.id,token_hash=digest(token),expires_at=ends+timedelta(days=1)))
    db.flush()
    return r,token

def modify(db,venue,r,data,actor_id=None,clock=None):
    clock=clock or now()
    if r.version!=data.version: raise HTTPException(409,'Prenotazione aggiornata da un altro operatore. Ricarica.')
    if r.status not in {'HOLD','PENDING_APPROVAL','CONFIRMED'}: raise HTTPException(409,'Modifica non consentita in questo stato.')
    if r.deposit_policy_snapshot: raise HTTPException(409,'Modifica con acconto: contatta il locale per verificare la policy.')
    allocate(db,venue,r,data.starts_at,data.party_size,clock)
    r.version+=1; cancel_reminders(db,r); event(db,r,'changed',actor='staff' if actor_id else 'customer',actor_id=actor_id)
    enqueue(db,r,'changed'); reminder(db,r,venue,clock); db.flush()
    return r

def serialize(db,r,public=False):
    c=db.get(Customer,r.customer_id)
    result={'id':str(r.id),'public_reference':r.public_reference,'starts_at':r.starts_at,'ends_at':r.ends_at,'party_size':r.party_size,'status':r.status,'version':r.version,'name':c.name,'source':r.source,'deposit':r.deposit_policy_snapshot,'expires_at':r.hold_expires_at if r.status=='HOLD' else r.pending_expires_at if r.status=='PENDING_APPROVAL' else r.payment_expires_at if r.status=='AWAITING_PAYMENT' else None}
    if not public: result['tables']=[x for x in db.scalars(select(Resource.name).join(Allocation,Allocation.resource_id==Resource.id).where(Allocation.reservation_id==r.id,Allocation.active.is_(True)))]
    return result
