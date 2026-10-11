from datetime import timedelta
from celery import Celery
from sqlalchemy import select
from app.config import settings
from app.db import transaction, tenant_lock
from app.domain.models import *
from app.services.reservations import expire
from app.auth.security import decrypt, crypt

celery=Celery('tavolo',broker=settings.redis_url,backend=settings.redis_url)
celery.conf.update(timezone='UTC',enable_utc=True,task_ignore_result=True,worker_prefetch_multiplier=1,beat_schedule={'tick':{'task':'tavolo.tick','schedule':30.0}})

@celery.task(name='tavolo.tick')
def tick():
    # Registry contains no guest information; each tenant is processed with SET LOCAL context.
    with transaction() as db: ids=set(db.scalars(select(VenueRoute.tenant_id)).all())
    for tid in ids: dispatch.delay(str(tid))

@celery.task(name='tavolo.dispatch',autoretry_for=(ConnectionError,),retry_backoff=True,max_retries=5)
def dispatch(tid): return process_tenant(tid)

def process_tenant(tid,clock=None,fail=False):
    clock=clock or now(); processed=0
    # Venue mutex is acquired before outbox locks everywhere, preventing reverse lock order.
    with transaction(tid) as db:
        venues=db.scalars(select(Venue).order_by(Venue.id)).all()
        for v in venues: tenant_lock(db,v.id); expire(db,v,clock)
        for w in db.scalars(select(WaitlistEntry).where(WaitlistEntry.status=='offered',WaitlistEntry.offer_expires_at<=clock)):
            r=db.get(Reservation,w.offered_reservation_id)
            w.status='accepted' if r and r.status in {'CONFIRMED','PENDING_APPROVAL','AWAITING_PAYMENT','SEATED','COMPLETED'} else 'expired'
        events=db.scalars(select(OutboxEvent).where(OutboxEvent.status.in_(['pending','retry']),OutboxEvent.available_at<=clock).order_by(OutboxEvent.id).with_for_update(skip_locked=True).limit(100)).all()
        for e in events:
            r=db.get(Reservation,e.aggregate_id)
            if not r or r.ends_at<=clock or r.status in {'COMPLETED','NO_SHOW'}: e.status='cancelled'; continue
            if e.event_type=='reminder' and (r.version!=e.payload['version'] or r.status!='CONFIRMED' or r.starts_at<=clock):
                e.status='cancelled'; continue
            if e.event_type in {'confirmed','payment_due'} and r.status not in {'CONFIRMED','AWAITING_PAYMENT','SEATED'}:
                e.status='cancelled'; continue
            existing=db.scalar(select(Notification).where(Notification.deduplication_key==e.deduplication_key))
            if existing and existing.status in {'simulated','sent','delivered','uncertain'}:
                e.status='done' if existing.status!='uncertain' else 'uncertain'; continue
            c=db.get(Customer,r.customer_id); dest=c.email if c.preferred_channel=='email' else c.phone_e164
            e.attempts+=1
            failure=None
            if not dest: failure='destination_missing'
            if c.preferred_channel=='whatsapp':
                opt=db.scalar(select(ConsentRecord.id).where(ConsentRecord.customer_id==c.id,ConsentRecord.purpose=='whatsapp_opt_in',ConsentRecord.granted.is_(True),ConsentRecord.revoked_at.is_(None)))
                if not opt: failure='whatsapp_opt_in_missing'
            from app.services.subscriptions import permitted
            allowed,quota_failure=permitted(db,db.get(Venue,r.venue_id),c.preferred_channel,1,clock)
            if not allowed: failure=quota_failure
            if fail: failure='provider_unavailable'
            n=existing or Notification(tenant_id=r.tenant_id,reservation_id=r.id,channel=c.preferred_channel,destination_encrypted=dest,deduplication_key=e.deduplication_key,status='queued')
            if not existing: db.add(n)
            n.attempts=e.attempts; n.failure_code=failure
            if failure:
                permanent=failure in {'destination_missing','whatsapp_opt_in_missing','included_quota_reached','trial_expired'} or e.attempts>=5
                e.status='failed' if permanent else 'retry'; n.status=e.status
                e.available_at=clock+timedelta(seconds=min(600,2**e.attempts*10))
            elif settings.demo:
                n.status='simulated'; n.provider_message_id='sim-'+str(e.id); n.sent_at=clock; e.status='done'
                db.add(UsageLedger(tenant_id=r.tenant_id,venue_id=r.venue_id,channel=c.preferred_channel+'_simulated',quantity=1,unit='message',deduplication_key='notification:'+e.deduplication_key,billable_quantity=0))
            else:
                # A persistent attempt may have reached the provider before a crash.
                # Real dispatch remains blocked until reconciliation paths are validated.
                n.status='blocked'; n.failure_code='sandbox_validation_required'; e.status='blocked'
            processed+=1
        from app.services.privacy import retention
        retention(db,clock)
    return {'processed':processed,'simulation':settings.demo}
