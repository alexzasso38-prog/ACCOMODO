from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy import select,func
from app.domain.models import Subscription,BillingPlan,UsageLedger,Venue,now

def usage(db,venue,clock=None):
    clock=clock or now();subscription=db.scalar(select(Subscription).where(Subscription.venue_id==venue.id))
    plan=db.get(BillingPlan,subscription.plan_version_id) if subscription else None
    limits=plan.limits_json if plan else {'whatsapp_messages':300,'telephony_minutes':100}
    month=clock.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    result={}
    for channel,limit_key in [('whatsapp','whatsapp_messages'),('telephony','telephony_minutes')]:
        observed=db.scalar(select(func.coalesce(func.sum(UsageLedger.quantity),0)).where(UsageLedger.venue_id==venue.id,UsageLedger.created_at>=month,UsageLedger.channel.in_([channel,channel+'_simulated'])))
        limit=Decimal(str(limits[limit_key]));pct=observed/limit*100 if limit else Decimal(100)
        threshold=100 if pct>=100 else 90 if pct>=90 else 70 if pct>=70 else 0
        result[channel]={'quantity':str(observed),'limit':str(limit),'warning_threshold':threshold,'remaining':str(max(Decimal(0),limit-observed))}
    return {'plan':plan.code if plan else 'Start-assumption','channels':result,'overages_enabled':False,'trial_ends_at':subscription.trial_end if subscription else None,'trial_expired':bool(subscription and subscription.status=='trial' and subscription.trial_end<=clock),'automatic_paid_conversion':False,'simulated_quantities':True}

def permitted(db,venue,channel,quantity,clock=None):
    state=usage(db,venue,clock)
    if state['trial_expired']:return False,'trial_expired'
    if channel not in state['channels']:return True,None
    remain=Decimal(state['channels'][channel]['remaining'])
    return (True,None) if Decimal(str(quantity))<=remain else (False,'included_quota_reached')
