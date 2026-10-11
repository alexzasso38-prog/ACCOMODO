from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta,datetime,date,time,timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select,func,text
from sqlalchemy.exc import IntegrityError
from app.db import transaction,tenant_lock
from app.domain.models import *
from app.api.schemas import Booking,Change
from app.services.reservations import create,modify,expire,change_status
from app.domain.availability import local_to_utc,service_slots,available_slots
from conftest import owner,payload
import pytest

def test_50_simultaneous_requests_one_allocation(tenants):
    t=tenants[0]
    def attempt(i):
        try:
            with transaction(t['tenant']) as db:
                r,_=create(db,db.get(Venue,t['venue']),Booking(**payload(name=f'Ospite {i}')))
                return str(r.id)
        except HTTPException as e:
            assert e.status_code==409;return None
    with ThreadPoolExecutor(max_workers=50) as pool: results=list(pool.map(attempt,range(50)))
    assert sum(x is not None for x in results)==1
    with transaction(t['tenant']) as db:
        assert db.scalar(select(func.count()).select_from(Allocation).where(Allocation.active.is_(True)))==1
        assert db.scalar(select(func.count()).select_from(Customer))==1
        assert db.scalar(select(func.count()).select_from(OutboxEvent))==3 # receipt, confirmation, future reminder

def test_adjacent_intervals_and_atomic_failed_change(tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);r,_=create(db,v,Booking(**payload()));rid=r.id;original=r.starts_at
        second,_=create(db,v,Booking(**payload(hour=20,minute=30)))
    with pytest.raises(HTTPException):
        with transaction(t['tenant']) as db:
            tenant_lock(db,t['venue']);v=db.get(Venue,t['venue']);r=db.get(Reservation,rid)
            modify(db,v,r,Change(starts_at=datetime.fromisoformat(payload(hour=20,minute=30)['starts_at']),party_size=2,version=1))
    with transaction(t['tenant']) as db:
        r=db.get(Reservation,rid);assert r.starts_at==original;assert r.version==1
        assert db.scalar(select(func.count()).select_from(Allocation).where(Allocation.active.is_(True)))==2
        assert len(available_slots(db,db.get(Venue,t['venue']),original.astimezone(ZoneInfo('Europe/Rome')).date(),2,now()))>0

def test_database_exclusion_is_final_barrier(tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        r,_=create(db,db.get(Venue,t['venue']),Booking(**payload()));rid=r.id;start=r.starts_at;end=r.ends_at
    with pytest.raises(IntegrityError):
        with transaction(t['tenant']) as db:
            db.add(Allocation(tenant_id=t['tenant'],venue_id=t['venue'],reservation_id=rid,resource_id=t['resource'],starts_at=start,ends_at=end,active=True));db.flush()

def test_combinations_occupy_physical_tables(tenants):
    t=tenants[0]
    with SessionOwner() as db,db.begin():
        first=db.get(Resource,t['resource']);first.max_guests=2
        second=Resource(tenant_id=t['tenant'],venue_id=t['venue'],room_id=t['room'],name='Secondo',min_guests=1,max_guests=2);db.add(second);db.flush()
        combo=ResourceCombination(tenant_id=t['tenant'],venue_id=t['venue'],name='Uniti',min_guests=3,max_guests=4);db.add(combo);db.flush()
        for rid in [first.id,second.id]:db.add(CombinationMember(tenant_id=t['tenant'],venue_id=t['venue'],combination_id=combo.id,resource_id=rid))
    with transaction(t['tenant']) as db:
        r,_=create(db,db.get(Venue,t['venue']),Booking(**payload(party=4)))
        assert db.scalar(select(func.count()).select_from(Allocation).where(Allocation.reservation_id==r.id,Allocation.active.is_(True)))==2
    with pytest.raises(HTTPException):
        with transaction(t['tenant']) as db:create(db,db.get(Venue,t['venue']),Booking(**payload(party=1)))

def SessionOwner():
    from sqlalchemy.orm import Session
    return Session(owner)

def test_hold_and_pending_expiry_release(tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);r,_=create(db,v,Booking(**payload(hold=True)));rid=r.id
        expire(db,v,now()+timedelta(minutes=6));assert r.status=='EXPIRED'
        v.booking_mode='manual';r2,_=create(db,v,Booking(**payload()));assert r2.status=='PENDING_APPROVAL'
        expire(db,v,now()+timedelta(minutes=31));assert r2.status=='EXPIRED'
        assert db.scalar(select(func.count()).select_from(Allocation).where(Allocation.active.is_(True)))==0

def test_closure_notice_arrivals_and_block(tenants):
    t=tenants[0];data=payload()
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);day=datetime.fromisoformat(data['starts_at']).date()
        db.add(CalendarException(tenant_id=t['tenant'],venue_id=v.id,local_date=day,closed=True));db.flush()
        assert available_slots(db,v,day,2,now())==[]
    with pytest.raises(HTTPException):
        with transaction(t['tenant']) as db:create(db,db.get(Venue,t['venue']),Booking(**data))
    with transaction(t['tenant']) as db:
        ex=db.scalar(select(CalendarException));db.delete(ex);db.flush()
        v=db.get(Venue,t['venue']);v.minimum_notice_minutes=10080
    with pytest.raises(HTTPException):
        with transaction(t['tenant']) as db:create(db,db.get(Venue,t['venue']),Booking(**data))

def test_overnight_and_dst(tenants):
    assert local_to_utc(datetime(2026,3,29,2,30),'Europe/Rome') is None
    assert local_to_utc(datetime(2026,10,25,2,30),'Europe/Rome') is None
    assert local_to_utc(datetime(2026,10,25,3,30),'Europe/Rome')==datetime(2026,10,25,2,30,tzinfo=timezone.utc)
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);day=date(2026,10,20)
        for schedule in db.scalars(select(ServiceSchedule).where(ServiceSchedule.venue_id==v.id)):
            db.delete(schedule)
        db.add(ServiceSchedule(tenant_id=t['tenant'],venue_id=v.id,weekday=day.weekday(),local_start_time=time(22),local_end_time=time(2),duration_minutes=60,slot_interval_minutes=30));db.flush()
        slots=service_slots(db,v,day)
        assert len(slots)==7
        assert slots[-1][0].astimezone(ZoneInfo('Europe/Rome')).date()==day+timedelta(days=1)
        assert all(e-s==timedelta(hours=1) for s,e,_ in slots)

def test_arrival_limit_with_two_free_tables(tenants):
    t=tenants[0]
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue'])
        db.add(Resource(tenant_id=t['tenant'],venue_id=v.id,room_id=t['room'],name='Extra',min_guests=1,max_guests=4))
        for s in db.scalars(select(ServiceSchedule).where(ServiceSchedule.venue_id==v.id)): s.max_arrivals_per_slot=1
        db.flush();create(db,v,Booking(**payload()))
    with pytest.raises(HTTPException,match=''):
        with transaction(t['tenant']) as db:create(db,db.get(Venue,t['venue']),Booking(**payload()))

def test_walkin_arrives_now_checks_physical_capacity(tenants):
    t=tenants[0];clock=datetime.fromisoformat(payload()['starts_at'])+timedelta(minutes=7)
    with transaction(t['tenant']) as db:
        v=db.get(Venue,t['venue']);r,_=create(db,v,Booking(**payload(starts_at=clock.isoformat())),source='walk_in',clock=clock)
        assert r.status=='SEATED' and r.starts_at==clock
    with pytest.raises(HTTPException):
        with transaction(t['tenant']) as db:create(db,db.get(Venue,t['venue']),Booking(**payload(starts_at=clock.isoformat())),source='walk_in',clock=clock)
