# API

OpenAPI tipizzato è generato da FastAPI. Endpoint staff: cookie `tavolo_session` HttpOnly; mutazioni `X-CSRF-Token` ritornato dal login. Tenant e sede non sono parametri di autorizzazione client. Gestori/tenant_admin richiedono MFA al login. Super-admin non può accedere ai dati ospiti senza un workflow supporto, attualmente disabilitato.

| Endpoint | Scopo |
|---|---|
| `POST /api/auth/login`, `/logout`; `GET /me` | Sessione, MFA, CSRF |
| `GET /api/public/{slug}` | Informazioni pubbliche sede senza ospiti |
| `GET /api/public/{slug}/availability?day=YYYY-MM-DD&party_size=2` | Slot reali UTC + label locale |
| `POST /api/public/{slug}/reservations` | Nome, email/telefono, canale, opt-in, privacy_ack, starts_at con offset, party_size, hold opzionale |
| `GET/PATCH /api/public/{slug}/booking` | `X-Booking-Token`, lettura o cambio atomico con version |
| `POST .../booking/cancel`, `/finalize` | Cancellazione o finalizzazione HOLD |
| `GET .../booking/calendar.ics` | ICS senza PII, dopo conferma |
| `POST .../booking/payment-simulation` | Solo demo, event_id; un solo pagamento, nessuna carta |
| `GET/POST /api/admin/reservations` | Agenda per giorno IANA locale, inserimento staff/walk-in |
| `GET /api/admin/reservations/upcoming` | Prenotazioni attive da oggi in poi (tutti i giorni), per avvisi e conteggi per giorno nell’agenda |
| `PATCH /api/admin/reservations/{uuid}` | Modifica con starts_at, party_size, version |
| `POST .../{uuid}/status` | Transizione con version; acconto impedisce conferma prematura |
| `GET/POST /api/admin/resources`, `POST /combinations` | Tavoli fisici, membri distinti/coerenti con sede |
| `GET/POST /api/admin/schedules`; `POST /exceptions`, `/blocks` | Servizi, chiusure e blocchi; advanced UI non completa |
| `GET/PATCH /api/admin/settings` | Regole e stato integrazioni; scrittura manager |
| `GET /api/admin/customers`, `/report?start=...&end=...`, `/export.csv` | Scoping tenant/sede, CSV anti-formula (manager) |
| `GET /api/admin/notifications`, `/usage` | Outbox/consumi e soglie 70/90/100, nessun addebito |
| `POST /api/admin/privacy/export`, `/anonymize` | Manager, customer_id, identity_verified, reason |
| `POST /api/demo/phone`, `/dispatch` | Simulazione autenticata e protetta CSRF |
| `POST /api/public/{slug}/waitlist`; `GET /api/admin/waitlist`; `POST /{uuid}/offer` | Consenso email, offerta HOLD 5 minuti |
| `GET /api/pricing`; `POST /api/admin/billing/quote` | Prezzi imponibile/IVA/totale e preventivo draft non fiscale |
| `POST /api/webhooks/{provider}` | 503: integrazione reale non attivata |
| `GET /health`, `/ready` | Liveness e DB ruolo sicuro + Redis |

Errori: 401 sessione/link richiesto, 403 ruolo/CSRF/Origin, 404 relazione o token estraneo/non valido, 409 disponibilità/transizione/versione/policy, 422 input, 429 rate limit, 503 protezione Redis/provider disabilitato. Errori DB non restituiscono SQL o valori sensibili. Inizio/fine UTC, intervalli semiaperti; slot notturni legati al giorno del servizio. I link contengono token nel frammento e lo inviano solo in header; access logs disabilitati. Nessun endpoint usa un tenant_id client per superare RLS.

Esempio payload sintetico:
```json
{"starts_at":"2026-10-13T19:00:00+02:00","party_size":2,"name":"Ospite sintetico","email":"ospite@example.test","channel":"email","whatsapp_opt_in":false,"privacy_ack":true}
```
Non riutilizzare la data statica per test: scegliere una data futura nel periodo prenotabile.
