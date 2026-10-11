"""Provider-neutral phase-2 interface; live conversational voice remains disabled."""
from dataclasses import dataclass
from typing import Protocol, Any
from datetime import datetime, timezone
from fastapi import HTTPException

class VoiceProvider(Protocol):
    def answer(self,call_id:str,tools:dict[str,Any],handoff_number:str|None)->None: ...

@dataclass(frozen=True)
class AuthorizedCall:
    tenant_id:str
    venue_slug:str
    started_at:datetime
    max_duration_seconds:int=120
    max_cost_cents:int=100

class VoiceTools:
    """Authorized routing is injected by verified server mapping, never model arguments.
    The injected API client owns HTTP authorization and invokes the same booking API.
    No database connection or availability estimation is exposed to the model.
    """
    def __init__(self,call:AuthorizedCall,api_client): self.call=call;self.api=api_client
    def invoke(self,name:str,args:dict,spent_cents:int,clock:datetime|None=None):
        clock=clock or datetime.now(timezone.utc)
        if spent_cents>=self.call.max_cost_cents or (clock-self.call.started_at).total_seconds()>=self.call.max_duration_seconds:
            raise HTTPException(409,'Passaggio al personale: limite di durata o budget raggiunto.')
        if any(k in args for k in ['tenant_id','venue_id','venue_slug','sql']): raise HTTPException(403,'Routing non modificabile dal modello.')
        if name=='availability':
            if set(args)!={'day','party_size'}: raise HTTPException(422,'Argomenti di disponibilità non validi.')
            return self.api.get(f'/api/public/{self.call.venue_slug}/availability',params=args)
        if name=='book':
            if not args.get('summary_confirmed'): raise HTTPException(409,'Leggere il riepilogo e ottenere conferma prima della prenotazione.')
            body={k:v for k,v in args.items() if k!='summary_confirmed'}
            return self.api.post(f'/api/public/{self.call.venue_slug}/reservations',json=body)
        if name=='handoff': return {'route':'human','reason':'requested'}
        raise HTTPException(422,'Tool non consentito. Informazioni sugli allergeni richiedono il personale.')
