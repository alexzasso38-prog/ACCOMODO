import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Date, Time, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase

def now(): return datetime.now(timezone.utc)
def uid(): return uuid.uuid4()
class Base(DeclarativeBase): pass
class Common:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uid)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
class Scoped(Common):
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)

class Tenant(Common, Base):
    __tablename__='tenants'
    name=Column(String, nullable=False); slug=Column(String, unique=True, nullable=False)
    status=Column(String, default='demo', nullable=False)
    legal_name=Column(String); vat_number=Column(String); billing_email=Column(String); billing_address=Column(String)
    default_currency=Column(String, default='EUR'); default_tax_rate=Column(Numeric(6,3), default=22)
class User(Common, Base):
    __tablename__='users'
    email=Column(String, unique=True, nullable=False); password_hash=Column(String, nullable=False)
    active=Column(Boolean, default=True, nullable=False); mfa_config=Column(Text); last_login=Column(DateTime(timezone=True))
class Membership(Common, Base):
    __tablename__='memberships'
    user_id=Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    tenant_id=Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    venue_id=Column(UUID(as_uuid=True)); role=Column(String, nullable=False)
    __table_args__=(CheckConstraint("role IN ('staff','manager','tenant_admin','super_admin')"),
                   ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']))
class Session(Common, Base):
    __tablename__='sessions'
    user_id=Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    membership_id=Column(UUID(as_uuid=True), ForeignKey('memberships.id'), nullable=False)
    token_hash=Column(String, unique=True, nullable=False); csrf_hash=Column(String, nullable=False)
    expires_at=Column(DateTime(timezone=True), nullable=False); revoked_at=Column(DateTime(timezone=True))
class Venue(Scoped, Base):
    __tablename__='venues'
    name=Column(String, nullable=False); slug=Column(String, unique=True, nullable=False)
    address=Column(String, default='Indirizzo fittizio — demo'); timezone=Column(String, default='Europe/Rome', nullable=False)
    phone_public=Column(String); transfer_phone=Column(String); email=Column(String)
    menu_url=Column(String); directions_url=Column(String)
    booking_mode=Column(String, default='automatic', nullable=False)
    booking_horizon_days=Column(Integer, default=60, nullable=False); minimum_notice_minutes=Column(Integer, default=30, nullable=False)
    default_duration_minutes=Column(Integer, default=90, nullable=False); pending_expiry_minutes=Column(Integer, default=30, nullable=False)
    max_party_size=Column(Integer, default=12, nullable=False); branding=Column(JSONB, default=dict); locale=Column(String, default='it')
    status=Column(String, default='demo'); deposit_cents=Column(Integer, default=0, nullable=False)
    deposit_tax_rate=Column(Numeric(6,3), nullable=True); policy_version=Column(Integer, default=1, nullable=False)
    reminder_quiet_start=Column(Integer, default=22); reminder_quiet_end=Column(Integer, default=9)
    __table_args__=(UniqueConstraint('tenant_id','id'),CheckConstraint("booking_mode IN ('automatic','manual')"),CheckConstraint('deposit_cents >= 0'), CheckConstraint('default_duration_minutes > 0'))
# Public routing contains no guest data. Slug is resolved before setting the RLS context.
class VenueRoute(Common, Base):
    __tablename__='venue_routes'
    slug=Column(String, unique=True, nullable=False); tenant_id=Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)
    venue_id=Column(UUID(as_uuid=True), nullable=False)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),)
class Room(Scoped, Base):
    __tablename__='rooms'
    venue_id=Column(UUID(as_uuid=True), nullable=False); name=Column(String, nullable=False); enabled=Column(Boolean, default=True)
    __table_args__=(UniqueConstraint('tenant_id','venue_id','id'),ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']))
class Resource(Scoped, Base):
    __tablename__='resources'
    venue_id=Column(UUID(as_uuid=True), nullable=False); room_id=Column(UUID(as_uuid=True), nullable=False)
    name=Column(String, nullable=False); min_guests=Column(Integer, default=1, nullable=False); max_guests=Column(Integer, nullable=False)
    enabled=Column(Boolean, default=True, nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','venue_id','id'),ForeignKeyConstraint(['tenant_id','venue_id','room_id'],['rooms.tenant_id','rooms.venue_id','rooms.id']), CheckConstraint('min_guests > 0 AND max_guests >= min_guests'))
class ResourceCombination(Scoped, Base):
    __tablename__='resource_combinations'
    venue_id=Column(UUID(as_uuid=True), nullable=False); name=Column(String, nullable=False)
    min_guests=Column(Integer, nullable=False); max_guests=Column(Integer, nullable=False); enabled=Column(Boolean, default=True)
    __table_args__=(UniqueConstraint('tenant_id','venue_id','id'),ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),CheckConstraint('min_guests > 0 AND max_guests >= min_guests'))
class CombinationMember(Scoped, Base):
    __tablename__='combination_members'
    venue_id=Column(UUID(as_uuid=True), nullable=False); combination_id=Column(UUID(as_uuid=True), nullable=False); resource_id=Column(UUID(as_uuid=True), nullable=False)
    __table_args__=(UniqueConstraint('combination_id','resource_id'),ForeignKeyConstraint(['tenant_id','venue_id','combination_id'],['resource_combinations.tenant_id','resource_combinations.venue_id','resource_combinations.id']),ForeignKeyConstraint(['tenant_id','venue_id','resource_id'],['resources.tenant_id','resources.venue_id','resources.id']))
class ServiceSchedule(Scoped, Base):
    __tablename__='service_schedules'
    venue_id=Column(UUID(as_uuid=True), nullable=False); weekday=Column(Integer, nullable=False)
    local_start_time=Column(Time, nullable=False); local_end_time=Column(Time, nullable=False)
    slot_interval_minutes=Column(Integer, default=30, nullable=False); duration_minutes=Column(Integer, default=90, nullable=False); max_arrivals_per_slot=Column(Integer)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),CheckConstraint('weekday BETWEEN 0 AND 6 AND slot_interval_minutes > 0 AND duration_minutes > 0'),CheckConstraint('max_arrivals_per_slot IS NULL OR max_arrivals_per_slot > 0'))
class CalendarException(Scoped, Base):
    __tablename__='calendar_exceptions'
    venue_id=Column(UUID(as_uuid=True), nullable=False); local_date=Column(Date, nullable=False); closed=Column(Boolean, nullable=False)
    replacement_hours=Column(JSONB); reason=Column(String); policy_version=Column(Integer, default=1)
    __table_args__=(UniqueConstraint('tenant_id','venue_id','local_date'),ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']))
class ResourceBlock(Scoped, Base):
    __tablename__='resource_blocks'
    venue_id=Column(UUID(as_uuid=True), nullable=False); resource_id=Column(UUID(as_uuid=True), nullable=False)
    starts_at=Column(DateTime(timezone=True), nullable=False); ends_at=Column(DateTime(timezone=True), nullable=False); reason=Column(String)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id','resource_id'],['resources.tenant_id','resources.venue_id','resources.id']),CheckConstraint('ends_at > starts_at'))
class Customer(Scoped, Base):
    __tablename__='customers'
    name=Column(String, nullable=False); phone_e164=Column(Text); email=Column(Text); preferred_channel=Column(String, default='email'); locale=Column(String, default='it')
    __table_args__=(UniqueConstraint('tenant_id','id'),)
class ConsentRecord(Scoped, Base):
    __tablename__='consent_records'
    customer_id=Column(UUID(as_uuid=True), nullable=False); purpose=Column(String, nullable=False); channel=Column(String, nullable=False)
    granted=Column(Boolean, nullable=False); captured_at=Column(DateTime(timezone=True), default=now)
    source=Column(String, nullable=False); policy_version=Column(String, nullable=False); evidence_reference=Column(String); revoked_at=Column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['tenant_id','customer_id'],['customers.tenant_id','customers.id']),)
class Reservation(Scoped, Base):
    __tablename__='reservations'
    venue_id=Column(UUID(as_uuid=True), nullable=False); customer_id=Column(UUID(as_uuid=True), nullable=False)
    starts_at=Column(DateTime(timezone=True), nullable=False); ends_at=Column(DateTime(timezone=True), nullable=False)
    party_size=Column(Integer, nullable=False); source=Column(String, nullable=False); status=Column(String, nullable=False)
    hold_expires_at=Column(DateTime(timezone=True)); pending_expires_at=Column(DateTime(timezone=True)); payment_expires_at=Column(DateTime(timezone=True))
    public_reference=Column(String, unique=True, nullable=False); version=Column(Integer, default=1, nullable=False)
    cancellation_policy_snapshot=Column(JSONB, default=dict); deposit_policy_snapshot=Column(JSONB, default=dict)
    operational_note=Column(Text)
    __table_args__=(UniqueConstraint('tenant_id','venue_id','id'),UniqueConstraint('tenant_id','id'),ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),ForeignKeyConstraint(['tenant_id','customer_id'],['customers.tenant_id','customers.id']),CheckConstraint('ends_at > starts_at AND party_size > 0'),CheckConstraint("status IN ('HOLD','PENDING_APPROVAL','AWAITING_PAYMENT','CONFIRMED','SEATED','COMPLETED','CANCELLED','EXPIRED','REJECTED','NO_SHOW')"))
class Allocation(Scoped, Base):
    __tablename__='allocations'
    venue_id=Column(UUID(as_uuid=True), nullable=False); reservation_id=Column(UUID(as_uuid=True), nullable=False); resource_id=Column(UUID(as_uuid=True), nullable=False)
    starts_at=Column(DateTime(timezone=True), nullable=False); ends_at=Column(DateTime(timezone=True), nullable=False); active=Column(Boolean, default=True, nullable=False)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id','reservation_id'],['reservations.tenant_id','reservations.venue_id','reservations.id']),ForeignKeyConstraint(['tenant_id','venue_id','resource_id'],['resources.tenant_id','resources.venue_id','resources.id']),CheckConstraint('ends_at > starts_at'))
class ReservationEvent(Scoped, Base):
    __tablename__='reservation_events'
    reservation_id=Column(UUID(as_uuid=True), nullable=False); actor_type=Column(String, nullable=False); actor_id=Column(UUID(as_uuid=True))
    previous_status=Column(String); next_status=Column(String); event_type=Column(String, nullable=False); reason=Column(String)
    occurred_at=Column(DateTime(timezone=True), default=now); redacted_metadata=Column(JSONB, default=dict)
    __table_args__=(ForeignKeyConstraint(['tenant_id','reservation_id'],['reservations.tenant_id','reservations.id']),)
class BookingAccessToken(Scoped, Base):
    __tablename__='booking_access_tokens'
    reservation_id=Column(UUID(as_uuid=True), nullable=False); token_hash=Column(String, unique=True, nullable=False); scope=Column(String, default='manage')
    expires_at=Column(DateTime(timezone=True), nullable=False); revoked_at=Column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['tenant_id','reservation_id'],['reservations.tenant_id','reservations.id']),)
class OutboxEvent(Scoped, Base):
    __tablename__='outbox_events'
    aggregate_type=Column(String, default='reservation'); aggregate_id=Column(UUID(as_uuid=True), nullable=False)
    event_type=Column(String, nullable=False); payload=Column(JSONB, default=dict); status=Column(String, default='pending', nullable=False)
    attempts=Column(Integer, default=0, nullable=False); available_at=Column(DateTime(timezone=True), default=now, nullable=False)
    deduplication_key=Column(String, unique=True, nullable=False)
    __table_args__=(CheckConstraint("event_type IN ('booking_link','received','confirmed','changed','cancelled','rejected','reminder','payment_due')"),)
class Notification(Scoped, Base):
    __tablename__='notifications'
    reservation_id=Column(UUID(as_uuid=True), nullable=False); channel=Column(String, nullable=False); template_version=Column(String, default='1')
    destination_encrypted=Column(Text); status=Column(String, nullable=False); scheduled_at=Column(DateTime(timezone=True), default=now)
    provider_message_id=Column(String); attempts=Column(Integer, default=0); failure_code=Column(String)
    deduplication_key=Column(String, unique=True, nullable=False); sent_at=Column(DateTime(timezone=True)); delivered_at=Column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['tenant_id','reservation_id'],['reservations.tenant_id','reservations.id']),)
class Payment(Scoped, Base):
    __tablename__='payments'
    venue_id=Column(UUID(as_uuid=True), nullable=False); reservation_id=Column(UUID(as_uuid=True), nullable=False)
    connected_account_id=Column(String); provider=Column(String, nullable=False); provider_payment_id=Column(String, unique=True)
    idempotency_key=Column(String, unique=True, nullable=False); amount_net=Column(Integer, nullable=False); tax_amount=Column(Integer, nullable=False); amount_total=Column(Integer, nullable=False)
    currency=Column(String, default='EUR'); status=Column(String, nullable=False); captured_at=Column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('tenant_id','id'),ForeignKeyConstraint(['tenant_id','venue_id','reservation_id'],['reservations.tenant_id','reservations.venue_id','reservations.id']),CheckConstraint('amount_net >= 0 AND tax_amount >= 0 AND amount_total = amount_net + tax_amount'))
class Refund(Scoped, Base):
    __tablename__='refunds'
    payment_id=Column(UUID(as_uuid=True), nullable=False); provider_refund_id=Column(String); amount=Column(Integer, nullable=False); reason=Column(String); status=Column(String, nullable=False); idempotency_key=Column(String, unique=True, nullable=False)
    __table_args__=(ForeignKeyConstraint(['tenant_id','payment_id'],['payments.tenant_id','payments.id']),CheckConstraint('amount > 0'))
class WebhookReceipt(Common, Base):
    __tablename__='webhook_receipts'
    provider=Column(String, nullable=False); provider_account_reference=Column(String, nullable=False); event_id=Column(String, nullable=False)
    signature_valid=Column(Boolean, nullable=False); processed_at=Column(DateTime(timezone=True)); status=Column(String, nullable=False)
    __table_args__=(UniqueConstraint('provider','provider_account_reference','event_id'),)
class ChannelConnection(Scoped, Base):
    __tablename__='channel_connections'
    venue_id=Column(UUID(as_uuid=True), nullable=False); provider=Column(String, nullable=False); channel=Column(String, nullable=False)
    account_reference=Column(String); credential_secret_reference=Column(String); sender_identity=Column(String); status=Column(String, default='unconfigured'); capability_flags=Column(JSONB, default=dict)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),)
class MessageTemplate(Scoped, Base):
    __tablename__='message_templates'
    venue_id=Column(UUID(as_uuid=True)); type=Column(String, nullable=False); channel=Column(String, nullable=False); language=Column(String, default='it')
    provider_template_id=Column(String); provider_category=Column(String, default='UTILITY'); approval_status=Column(String, default='unapproved'); content_version=Column(Integer, default=1); content=Column(Text)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),CheckConstraint("type IN ('booking_link','received','confirmed','changed','cancelled','rejected','reminder','payment_due')"))
class AuditLog(Scoped, Base):
    __tablename__='audit_logs'
    actor_id=Column(UUID(as_uuid=True)); action=Column(String, nullable=False); target_type=Column(String); target_id=Column(UUID(as_uuid=True)); timestamp=Column(DateTime(timezone=True), default=now); redacted_diff=Column(JSONB, default=dict); request_id=Column(String)
class PrivacyRequest(Scoped, Base):
    __tablename__='privacy_requests'
    requester_reference=Column(String); type=Column(String, nullable=False); identity_verified_at=Column(DateTime(timezone=True)); status=Column(String, default='pending'); deadline=Column(DateTime(timezone=True)); completed_at=Column(DateTime(timezone=True))
class SupportAccessGrant(Scoped, Base):
    __tablename__='support_access_grants'
    super_admin_user_id=Column(UUID(as_uuid=True), ForeignKey('users.id')); purpose=Column(String, nullable=False); granted_by=Column(UUID(as_uuid=True), ForeignKey('users.id')); starts_at=Column(DateTime(timezone=True), nullable=False); expires_at=Column(DateTime(timezone=True), nullable=False); revoked_at=Column(DateTime(timezone=True))
class UsageLedger(Scoped, Base):
    __tablename__='usage_ledger'
    venue_id=Column(UUID(as_uuid=True), nullable=False); channel=Column(String, nullable=False); quantity=Column(Numeric(14,4), nullable=False); unit=Column(String, nullable=False); provider_event_id=Column(String)
    estimated_provider_cost=Column(Integer); billable_quantity=Column(Numeric(14,4), default=0); period=Column(String); deduplication_key=Column(String, unique=True, nullable=False)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),)
class CallSession(Scoped, Base):
    __tablename__='call_sessions'
    venue_id=Column(UUID(as_uuid=True), nullable=False); provider_call_id=Column(String, unique=True); caller_phone_encrypted=Column(Text)
    started_at=Column(DateTime(timezone=True), default=now); ended_at=Column(DateTime(timezone=True)); route=Column(String, default='ivr'); outcome=Column(String); whatsapp_opt_in_reference=Column(String); duration_seconds=Column(Integer); provider_cost=Column(Integer)
    __table_args__=(ForeignKeyConstraint(['tenant_id','venue_id'],['venues.tenant_id','venues.id']),)
