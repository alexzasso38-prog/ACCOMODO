from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_, func
from fastapi import HTTPException
from app.domain.models import Resource, Room, ResourceCombination, CombinationMember, Allocation, ResourceBlock, ServiceSchedule, CalendarException, Reservation

UTC=timezone.utc
ACTIVE={'HOLD','PENDING_APPROVAL','AWAITING_PAYMENT','CONFIRMED','SEATED'}

def local_to_utc(local, zone):
    """Reject both DST gaps and ambiguous wall times; never silently choose fold."""
    z=ZoneInfo(zone)
    a=local.replace(tzinfo=z, fold=0); b=local.replace(tzinfo=z, fold=1)
    if a.utcoffset()!=b.utcoffset() or a.astimezone(UTC).astimezone(z).replace(tzinfo=None)!=local:
        return None
    return a.astimezone(UTC)

def service_slots(db, venue, day):
    exc=db.scalar(select(CalendarException).where(CalendarException.venue_id==venue.id, CalendarException.local_date==day))
    if exc and exc.closed: return []
    if exc and exc.replacement_hours is not None:
        schedules=[dict(local_start_time=time.fromisoformat(x['start']), local_end_time=time.fromisoformat(x['end']), slot_interval_minutes=x['interval'], duration_minutes=x['duration'], max_arrivals_per_slot=x.get('max_arrivals')) for x in exc.replacement_hours]
    else:
        schedules=db.scalars(select(ServiceSchedule).where(ServiceSchedule.venue_id==venue.id, ServiceSchedule.weekday==day.weekday())).all()
    result=[]
    for s in schedules:
        def get(k): return s[k] if isinstance(s,dict) else getattr(s,k)
        start=datetime.combine(day,get('local_start_time')); end=datetime.combine(day,get('local_end_time'))
        if end<=start: end+=timedelta(days=1)
        cursor=start
        while cursor < end:
            instant=local_to_utc(cursor,venue.timezone)
            closing=local_to_utc(end,venue.timezone)
            if instant and closing and instant+timedelta(minutes=get('duration_minutes'))<=closing:
                result.append((instant, instant+timedelta(minutes=get('duration_minutes')), get('max_arrivals_per_slot')))
            cursor+=timedelta(minutes=get('slot_interval_minutes'))
    return result

def validate_slot(db, venue, starts, party, clock):
    if starts.tzinfo is None: raise HTTPException(422,'Data e ora devono includere il fuso orario.')
    starts=starts.astimezone(UTC)
    if party<1 or party>venue.max_party_size: raise HTTPException(422,'Numero di persone non ammesso.')
    local=starts.astimezone(ZoneInfo(venue.timezone))
    if starts < clock+timedelta(minutes=venue.minimum_notice_minutes): raise HTTPException(409,'Preavviso minimo non rispettato.')
    if local.date()>clock.astimezone(ZoneInfo(venue.timezone)).date()+timedelta(days=venue.booking_horizon_days): raise HTTPException(409,'Data oltre il periodo prenotabile.')
    # Previous service day permits intervals crossing midnight.
    for day in (local.date(),local.date()-timedelta(days=1)):
        for slot in service_slots(db,venue,day):
            if slot[0]==starts: return slot
    raise HTTPException(409,'Il ristorante non accetta prenotazioni a questo orario.')

def candidates(db, venue, starts, ends, party, ignore=None, lock=False, clock=None):
    tables=db.scalars(select(Resource).join(Room, Room.id==Resource.room_id).where(Resource.venue_id==venue.id, Resource.enabled.is_(True),Room.enabled.is_(True)).order_by(Resource.id).with_for_update(of=Resource) if lock else select(Resource).join(Room,Room.id==Resource.room_id).where(Resource.venue_id==venue.id,Resource.enabled.is_(True),Room.enabled.is_(True)).order_by(Resource.id)).all()
    by_id={t.id:t for t in tables}
    query=select(Allocation.resource_id).join(Reservation, Reservation.id==Allocation.reservation_id).where(Allocation.venue_id==venue.id, Allocation.active.is_(True),Allocation.starts_at<ends,Allocation.ends_at>starts)
    if ignore: query=query.where(Allocation.reservation_id!=ignore)
    if clock:
        query=query.where(or_(Reservation.status.in_(['CONFIRMED','SEATED']),
            (Reservation.status=='HOLD') & (Reservation.hold_expires_at>clock),
            (Reservation.status=='PENDING_APPROVAL') & (Reservation.pending_expires_at>clock),
            (Reservation.status=='AWAITING_PAYMENT') & (Reservation.payment_expires_at>clock)))
    busy=set(db.scalars(query).all())
    busy.update(db.scalars(select(ResourceBlock.resource_id).where(ResourceBlock.venue_id==venue.id,ResourceBlock.starts_at<ends,ResourceBlock.ends_at>starts)).all())
    choices=[(t.max_guests,[t.id]) for t in tables if t.min_guests<=party<=t.max_guests and t.id not in busy]
    for combo in db.scalars(select(ResourceCombination).where(ResourceCombination.venue_id==venue.id,ResourceCombination.enabled.is_(True),ResourceCombination.min_guests<=party,ResourceCombination.max_guests>=party)):
        ids=db.scalars(select(CombinationMember.resource_id).where(CombinationMember.combination_id==combo.id).order_by(CombinationMember.resource_id)).all()
        if ids and all(x in by_id and x not in busy for x in ids) and sum(by_id[x].max_guests for x in ids)>=party:
            choices.append((combo.max_guests,ids))
    return sorted(choices,key=lambda x:(x[0],len(x[1]),str(x[1])))

def arrival_count(db,venue,starts,ignore=None,clock=None):
    q=select(func.count()).select_from(Reservation).where(Reservation.venue_id==venue.id,Reservation.starts_at==starts,Reservation.status.in_(ACTIVE))
    if ignore: q=q.where(Reservation.id!=ignore)
    if clock:
        q=q.where(or_(Reservation.status.in_(['CONFIRMED','SEATED']),
            Reservation.hold_expires_at>clock, Reservation.pending_expires_at>clock,Reservation.payment_expires_at>clock))
    return db.scalar(q)

def available_slots(db,venue,day,party,clock):
    result=[]
    for starts,ends,limit in service_slots(db,venue,day):
        try: validate_slot(db,venue,starts,party,clock)
        except HTTPException: continue
        choices=candidates(db,venue,starts,ends,party,clock=clock)
        if choices and (limit is None or arrival_count(db,venue,starts,clock=clock)<limit):
            result.append({'starts_at':starts,'ends_at':ends,'label':starts.astimezone(ZoneInfo(venue.timezone)).strftime('%H:%M')})
    return result


def validate_walkin(db,venue,starts,party,clock):
    if not starts.tzinfo or abs((starts-clock).total_seconds())>300:
        raise HTTPException(422,'Un walk-in deve iniziare adesso (entro 5 minuti).')
    if not 1<=party<=venue.max_party_size: raise HTTPException(422,'Numero persone non ammesso.')
    starts=starts.astimezone(UTC);local=starts.astimezone(ZoneInfo(venue.timezone))
    for day in (local.date(),local.date()-timedelta(days=1)):
        slots=service_slots(db,venue,day)
        if slots:
            opening=min(s for s,_,_ in slots);closing=max(e for _,e,_ in slots)
            ends=starts+timedelta(minutes=venue.default_duration_minutes)
            if opening<=starts and ends<=closing:return starts,ends,None
    raise HTTPException(409,'Walk-in fuori dal servizio disponibile o troppo vicino alla chiusura.')
