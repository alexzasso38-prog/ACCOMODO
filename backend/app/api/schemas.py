import re
from uuid import UUID
from datetime import datetime, date, time
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator, HttpUrl

class Login(BaseModel):
    email:str=Field(max_length=254); password:str=Field(max_length=256); otp:str|None=None
class Booking(BaseModel):
    starts_at:datetime; party_size:int=Field(ge=1,le=50)
    name:str=Field(min_length=2,max_length=100); email:str|None=Field(default=None,max_length=254); phone:str|None=Field(default=None,max_length=30)
    channel:Literal['email','whatsapp','sms']='email'; whatsapp_opt_in:bool=False; privacy_ack:bool
    hold:bool=False
    @field_validator('privacy_ack')
    @classmethod
    def privacy(cls,v):
        if not v: raise ValueError('Leggere l’informativa per proseguire.')
        return v
    @field_validator('name')
    @classmethod
    def name_ok(cls,v):
        if len(v.strip())<2 or any(ord(c)<32 for c in v): raise ValueError('Nome non valido.')
        return v.strip()
    @field_validator('email')
    @classmethod
    def email_ok(cls,v):
        if v and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v): raise ValueError('Email non valida.')
        return v.lower() if v else v
    @field_validator('phone')
    @classmethod
    def phone_ok(cls,v):
        if v and not re.fullmatch(r'\+[1-9]\d{7,14}',v): raise ValueError('Usa il formato internazionale, per esempio +39…')
        return v
    @field_validator('starts_at')
    @classmethod
    def aware(cls,v):
        if not v.tzinfo: raise ValueError('Fuso orario richiesto.')
        return v
class Change(BaseModel):
    starts_at:datetime; party_size:int=Field(ge=1,le=50); version:int=Field(ge=1)
class StatusChange(BaseModel):
    status:Literal['CONFIRMED','AWAITING_PAYMENT','SEATED','COMPLETED','CANCELLED','REJECTED','NO_SHOW']; version:int=Field(ge=1)
class VenueSettings(BaseModel):
    booking_mode:Literal['automatic','manual']; pending_expiry_minutes:int=Field(ge=5,le=120)
    minimum_notice_minutes:int=Field(ge=0,le=10080); booking_horizon_days:int=Field(ge=1,le=365)
    max_party_size:int=Field(ge=1,le=50)
    deposit_cents:int=Field(ge=0,le=100000); deposit_tax_rate:Decimal|None=Field(default=None,ge=0,le=100)
    reminder_quiet_start:int=Field(ge=0,le=23); reminder_quiet_end:int=Field(ge=0,le=23)
class TableCreate(BaseModel):
    name:str=Field(min_length=1,max_length=40); min_guests:int=Field(ge=1,le=50); max_guests:int=Field(ge=1,le=50)
class ExceptionCreate(BaseModel):
    local_date:date; closed:bool=True; reason:str=Field(default='Chiusura',max_length=100)
class BlockCreate(BaseModel):
    resource_id:UUID; starts_at:datetime; ends_at:datetime; reason:str=Field(max_length=100)
class PhoneSim(BaseModel):
    whatsapp:bool=False; hidden:bool=False; mobile:bool=True; provider_failure:bool=False
class SimPayment(BaseModel):
    event_id:str=Field(min_length=8,max_length=100)

class CombinationCreate(BaseModel):
    name:str=Field(min_length=1,max_length=40); min_guests:int=Field(ge=1,le=50); max_guests:int=Field(ge=1,le=50); resource_ids:list[UUID]=Field(min_length=2,max_length=10)
class ScheduleCreate(BaseModel):
    weekday:int=Field(ge=0,le=6); local_start_time:time; local_end_time:time
    slot_interval_minutes:int=Field(ge=5,le=180); duration_minutes:int=Field(ge=15,le=480); max_arrivals_per_slot:int|None=Field(default=None,ge=1,le=1000)
class PrivacyAction(BaseModel):
    customer_id:UUID; identity_verified:bool; reason:str=Field(min_length=5,max_length=200)
class WaitlistCreate(BaseModel):
    starts_at:datetime; ends_at:datetime; party_size:int=Field(ge=1,le=50)
    name:str=Field(min_length=2,max_length=100); email:str; whatsapp_opt_in:bool=False; privacy_ack:bool
class QuoteCreate(BaseModel):
    plan:Literal['Start','Concierge','Voice']; include_setup:bool=True; first_five_offer:bool=False

class SlotView(BaseModel):
    starts_at:datetime; ends_at:datetime; label:str
class ReservationView(BaseModel):
    id:UUID; public_reference:str; starts_at:datetime; ends_at:datetime
    party_size:int; status:Literal['HOLD','PENDING_APPROVAL','AWAITING_PAYMENT','CONFIRMED','SEATED','COMPLETED','CANCELLED','EXPIRED','REJECTED','NO_SHOW']
    version:int; name:str; source:str; deposit:dict; expires_at:datetime|None=None; tables:list[str]|None=None
class BookingCreated(BaseModel):
    reservation:ReservationView; access_token:str; manage_url:str
class VenueView(BaseModel):
    name:str;slug:str;address:str;timezone:str;booking_mode:Literal['automatic','manual'];max_party_size:int
    menu_url:str|None;directions_url:str|None;pending_policy:str;deposit:dict;demo:bool
