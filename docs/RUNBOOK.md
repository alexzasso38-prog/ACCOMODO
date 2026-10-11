# Runbook demo e operazioni

Avvio/credenziali/comandi: README. Prerequisiti esterni: PREREQUISITES.md. Nessuna esposizione pubblica autorizzata.

1. `docker compose ps`: db/redis/api healthy, worker e scheduler Up, migrate Exited(0).
2. `curl -f http://localhost:8081/health` e `/ready`: live, DB ruolo senza superuser/bypass, Redis raggiungibile.
3. `make seed-demo`: seed idempotente; account in work/demo-access.json. Se manca il file su DB già seeded, non rigenerare password silenziosamente: ripristinare il file o scegliere esplicitamente reset demo.
4. `docker compose logs --tail=50 api worker scheduler`: senza access logs. Non copiare `.env`, recapiti, token o dump in ticket.
5. Coda lenta: verificare scheduler unico, Redis, outbox status/attempts/available_at per tenant. Retry fino a 5; blocco su opt-in mancante/quota/trial. Nessun reinvio reale cieco per esiti incerti. API resta utilizzabile se un provider è indisponibile; Redis assente invece blocca rate-limited endpoints per protezione.
6. Pending scaduti: tick ogni 30 s, transazioni per sede. GET agenda/booking e nuove richieste eseguono anche expiry. Non sbloccare tavoli con SQL ad hoc.
7. Quote: soglie 70/90/100 disponibili via API usage; hard cap prima dei nuovi invii, percorso umano al limite telefonico; eccedenze disabilitate. I consumi demo sono simulati, non fatturabili.
8. Webhook reale 503 è voluto: verificare prerequisiti, non disabilitare firma o gate per renderlo verde.
9. Backup demo: `scripts/restore_test.py` usa il container locale tavolo-postgres, pg_dump -Fc, Fernet e DB restore separato; non è un job di backup produzione. Le chiavi demo in work devono essere custodite separatamente in reale.
10. Reset: `make reset-demo` rifiuta env/profilo/db inattesi, ferma processi, ricrea solo tavolo_demo nel servizio Compose db, migra e seed. Nessun volume Agro Sales AI viene toccato.

Produzione (obiettivo, non raggiunto): dump/snapshot cifrati giornalieri, retention da validare, chiavi KMS separate; restore in ambiente isolato con traffico chiuso, verifica schema/migrazioni/RLS e conteggi, riapplicazione cancellazioni GDPR, riconciliazione outbox/provider prima di riaprire invii. Obiettivi RPO24h/RTO4h da misurare in esercitazione con volumi realistici.

Incidenti: bloccare invii e pagamenti senza perdere le prenotazioni persistite; limitare accessi supporto con grant tenant temporaneo (console ancora disabilitata); salvare request_id/azioni redatte, distinguere violazione dati da outage, seguire tempi di notifica legalmente validati. Alert target: health, tasso 5xx/conflitti, latenza p95, età outbox, retry/esiti incerti, scadenze bloccate, storage/backup, login falliti.
