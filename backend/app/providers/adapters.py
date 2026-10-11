"""Real SDK adapters, deliberately detached from demo dispatch until sandbox validation."""
import os, json, smtplib
from email.message import EmailMessage
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse
import stripe
from app.config import settings

ALLOWED={'booking_link','received','confirmed','changed','cancelled','rejected','reminder','payment_due'}
class ProviderUnavailable(Exception): pass
class ProviderUncertain(Exception): pass

class SMTPAdapter:
    def send(self,destination,subject,body,message_id):
        if settings.demo or not settings.real_messages: raise ProviderUnavailable('real_send_disabled')
        if '\r' in destination or '\n' in destination: raise ValueError('invalid_destination')
        msg=EmailMessage(); msg['From']=os.environ['SMTP_FROM']; msg['To']=destination; msg['Subject']=subject
        msg['Message-ID']=f'<{message_id}@tavolo>'; msg.set_content(body)
        # STARTTLS mandatory; no plaintext fallback.
        with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=10) as server:
            server.starttls()
            if os.getenv('SMTP_USER'): server.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
            server.send_message(msg)
        return msg['Message-ID']

class TwilioAdapter:
    def __init__(self,sid,token): self.sid=sid; self.token=token
    def validate(self,url,form,signature,account):
        return account==self.sid and RequestValidator(self.token).validate(url,form,signature)
    def send(self,destination,sender,kind,template,variables,opt_in=False,sms=False):
        if kind not in ALLOWED: raise ValueError('disallowed_message_type')
        if settings.demo or not settings.real_messages: raise ProviderUnavailable('real_send_disabled')
        if not sms and (not opt_in or not template or template.get('approval_status')!='approved' or not template.get('provider_template_id')):
            raise ProviderUnavailable('whatsapp_opt_in_or_approved_template_missing')
        client=Client(self.sid,self.token,http_client=TwilioHttpClient(timeout=10))
        if sms:
            message=client.messages.create(to=destination,from_=sender,body=variables['body'])
        else:
            message=client.messages.create(to='whatsapp:'+destination,from_=sender,content_sid=template['provider_template_id'],content_variables=json.dumps(variables))
        return message.sid
    def greeting(self,name,action_url,transfer_phone=None):
        v=VoiceResponse(); gather=v.gather(num_digits=1,action=action_url,method='POST',timeout=6)
        gather.say(f'Benvenuto da {name}. Sono l’assistente automatico. Premi 1 per richiedere il link WhatsApp. Premi 2 per parlare con il locale.',language='it-IT')
        if transfer_phone: v.dial(transfer_phone)
        else: v.say('Il personale non è raggiungibile. Riprova al numero del locale.',language='it-IT')
        return str(v)

class StripeConnectAdapter:
    def __init__(self,key):
        if not key.startswith('sk_test_'): raise ProviderUnavailable('only_test_keys_allowed')
        self.client=stripe.StripeClient(key)
    @staticmethod
    def validate(payload,signature,secret):
        return stripe.Webhook.construct_event(payload,signature,secret)
    def checkout(self,account,reservation_id,total,currency,key,success_url,cancel_url):
        if settings.demo or os.getenv('STRIPE_CONNECT_ENABLED','false')!='true': raise ProviderUnavailable('connect_not_enabled')
        if not account or not account.startswith('acct_'): raise ProviderUnavailable('connected_account_required')
        return self.client.checkout.sessions.create(params={'mode':'payment','success_url':success_url,'cancel_url':cancel_url,'client_reference_id':str(reservation_id),'line_items':[{'price_data':{'currency':currency.lower(),'unit_amount':total,'product_data':{'name':'Acconto prenotazione'}},'quantity':1}]},options={'stripe_account':account,'idempotency_key':key})
    def refund(self,account,payment_intent,amount,key):
        if settings.demo: raise ProviderUnavailable('simulation_only')
        return self.client.refunds.create(params={'payment_intent':payment_intent,'amount':amount},options={'stripe_account':account,'idempotency_key':key})
