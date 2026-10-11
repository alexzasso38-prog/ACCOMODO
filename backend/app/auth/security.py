import secrets, os
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import HTTPException, Request
from sqlalchemy import select
from redis import Redis
from cryptography.fernet import Fernet
from app.config import settings
from app.db import transaction
from app.domain.models import User, Session, Membership, now
from app.services.reservations import digest
import pyotp

hasher=PasswordHasher()
redis=Redis.from_url(settings.redis_url, socket_connect_timeout=2,socket_timeout=2)

def crypt(value):
    if value is None: return None
    if not settings.encryption_key: raise RuntimeError('ENCRYPTION_KEY mancante: eseguire make setup.')
    return Fernet(settings.encryption_key.encode()).encrypt(value.encode()).decode()

def decrypt(value):
    return Fernet(settings.encryption_key.encode()).decrypt(value.encode()).decode() if value else None

def rate_limit(request,kind,limit):
    ip=request.client.host if request.client else 'local'
    key='rate:'+digest(ip+kind)
    try:
        count=redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",1,key)
    except Exception:
        raise HTTPException(503,'Protezione temporaneamente indisponibile. Riprova.')
    if count>limit: raise HTTPException(429,'Troppe richieste. Riprova tra un minuto.')

def login(db,email,password,otp=None):
    user=db.scalar(select(User).where(User.email==email.strip().lower(),User.active.is_(True)))
    valid=False
    try: valid=hasher.verify(user.password_hash if user else hasher.hash('dummy-credential'),password)
    except (VerifyMismatchError,InvalidHashError): pass
    if not user or not valid: raise HTTPException(401,'Credenziali non valide.')
    membership=db.scalar(select(Membership).where(Membership.user_id==user.id).order_by(Membership.id))
    if not membership or membership.role=='super_admin': raise HTTPException(403,'Accesso assistenza non disponibile senza concessione autorizzata.')
    if membership.role in {'manager','tenant_admin'}:
        if not user.mfa_config or not pyotp.TOTP(decrypt(user.mfa_config)).verify(otp or '',valid_window=1):
            raise HTTPException(401,'Codice MFA richiesto o non valido.')
    raw=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
    db.add(Session(user_id=user.id,membership_id=membership.id,token_hash=digest(raw),csrf_hash=digest(csrf),expires_at=now()+timedelta(hours=8)))
    # App role intentionally cannot modify global identities; last_login is omitted until an audited identity-service path exists.
    return raw,csrf,membership

def identity(request:Request):
    raw=request.cookies.get('tavolo_session')
    if not raw: raise HTTPException(401,'Accedi per continuare.')
    with transaction() as db:
        session=db.scalar(select(Session).where(Session.token_hash==digest(raw),Session.revoked_at.is_(None),Session.expires_at>now()))
        if not session: raise HTTPException(401,'Sessione scaduta.')
        member=db.get(Membership,session.membership_id)
        user=db.get(User,session.user_id)
        if not user or not user.active or member.role=='super_admin': raise HTTPException(403,'Accesso non autorizzato.')
        if request.method not in {'GET','HEAD','OPTIONS'}:
            csrf=request.headers.get('x-csrf-token','')
            if not secrets.compare_digest(digest(csrf),session.csrf_hash): raise HTTPException(403,'Protezione della sessione: ricarica e accedi.')
            origin=request.headers.get('origin')
            if origin and origin not in settings.origins: raise HTTPException(403,'Origine non autorizzata.')
        return {'tenant_id':member.tenant_id,'venue_id':member.venue_id,'role':member.role,'user_id':user.id,'email':user.email,'session_id':session.id}

def manager(who):
    if who['role'] not in {'manager','tenant_admin'}: raise HTTPException(403,'Operazione riservata al gestore.')
