from datetime import timedelta
from sqlalchemy import select,update,delete,func
from fastapi import HTTPException
from app.domain.models import *
from app.services.reservations import cancel_reminders

def anonymize_customer(db,customer,actor_id=None):
    reservations=db.scalars(select(Reservation).where(Reservation.customer_id==customer.id).with_for_update()).all()
    if any(r.status in {'HOLD','PENDING_APPROVAL','AWAITING_PAYMENT','CONFIRMED','SEATED'} and r.ends_at>now() for r in reservations):
        raise HTTPException(409,'Esistono prenotazioni attive: definire prima gli obblighi e gestire la prenotazione.')
    # Anonymous statistics remain; direct identifiers, secrets and destinations are removed.
    customer.name='Ospite anonimizzato';customer.phone_e164=None;customer.email=None
    db.execute(delete(ConsentRecord).where(ConsentRecord.customer_id==customer.id))
    for r in reservations:
        r.operational_note=None
        db.execute(update(BookingAccessToken).where(BookingAccessToken.reservation_id==r.id).values(revoked_at=now()))
        db.execute(update(Notification).where(Notification.reservation_id==r.id).values(destination_encrypted=None))
        db.execute(update(OutboxEvent).where(OutboxEvent.aggregate_id==r.id,OutboxEvent.status.in_(['pending','retry'])).values(status='cancelled'))
    db.execute(delete(WaitlistEntry).where(WaitlistEntry.customer_id==customer.id))
    conversations=db.scalars(select(Conversation).where(Conversation.customer_id==customer.id)).all()
    for c in conversations:
        db.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id==c.id));db.delete(c)
    db.add(AuditLog(tenant_id=customer.tenant_id,actor_id=actor_id,action='customer_anonymized',target_type='customer',target_id=customer.id))

def retention(db,clock):
    # Demo retention of encrypted destinations and call metadata; no tax-policy inference.
    db.execute(update(Notification).where(Notification.created_at<clock-timedelta(days=90)).values(destination_encrypted=None))
    db.execute(delete(ConversationMessage).where(ConversationMessage.retention_expires_at<=clock))
    db.execute(update(CallSession).where(CallSession.created_at<clock-timedelta(days=90)).values(caller_phone_encrypted=None))
    for c in db.scalars(select(Customer)):
        latest=db.scalar(select(func.max(Reservation.ends_at)).where(Reservation.customer_id==c.id))
        if latest and latest<clock-timedelta(days=365) and c.name!='Ospite anonimizzato': anonymize_customer(db,c)
