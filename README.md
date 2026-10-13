# Accomodo

Demo operativa in italiano per prenotazioni di ristoranti. Progetto autonomo nella cartella `/workspace/accomodo`, separato da Agro Sales AI. **Non è un prodotto attivato in produzione.** Due ristoranti fittizi, ospiti sintetici, messaggi e acconti simulati; nessuna telefonata, invio o transazione reale.

## Demo online su Render

Per ottenere un link HTTPS senza terminale, seguire [la guida Render](docs/RENDER_DEMO.md). Il Dockerfile nella radice pubblica una demo completa con dati temporanei. La variabile privata `DEMO_STAFF_PASSWORD` è obbligatoria; gli account online sono `staff1@accomodo.test` e `staff2@accomodo.test`. Nessun database o piano a pagamento è richiesto dalla configurazione.

## WhatsApp: integrazione di prova Meta

Il nuovo trial Twilio non supporta le risposte TwiML XML del sandbox classico. L’adattatore Meta Cloud API è pronto per un numero di test, ma richiede autorizzazione e credenziali Meta prima dell’attivazione: [guida e stato](docs/META_DEMO.md). Nessuna migrazione del numero personale o acquisto è automatico.

## Sviluppo locale: Docker Compose

Prerequisiti espliciti: Git, Docker Engine con daemon avviato, Docker Compose v2.24+, Python 3.12+ (per generare la configurazione locale), almeno 4 GB RAM e accesso ai registry Docker/PyPI/npm per la build. Non servono account provider. Node.js non è richiesto per usare la demo Docker; per test E2E sul computer occorrono Node.js 22.12+ o 24 e le dipendenze Linux di Chromium. Su Windows usare WSL2 con Docker integrato.

Dalla cartella `accomodo`:

```bash
make setup
make dev
make seed-demo
make demo-access
```

Apri **http://localhost:8081**. Accedi con uno degli account stampati da `make demo-access`. Le password sono casuali, create sulla tua macchina; si trovano in `work/demo-access.json`, escluso da Git. Gli account staff non richiedono MFA. Per i gestori, `make demo-access` stampa il codice TOTP corrente: rigenerarlo se passano 30 secondi. In produzione enrollment MFA e recovery richiedono una procedura dedicata, non la divulgazione del seed.

- Osteria del Porto DEMO, conferma automatica: http://localhost:8081/b/osteria-demo
- Giardino delle Spezie DEMO, approvazione manuale: http://localhost:8081/b/giardino-demo
- Listino proposto: http://localhost:8081/prezzi
- Informativa dimostrativa: http://localhost:8081/privacy
- Widget: http://localhost:8081/widget/osteria-demo
- OpenAPI: interno al container API, disponibile nello sviluppo locale su http://127.0.0.1:8010/docs. Il proxy demo non espone l'API docs.

L'unica porta host di Compose è `127.0.0.1:8081`. Database e Redis non sono pubblicati. Le password database presenti nel Compose sono esclusivamente locali. `make stop` ferma i servizi e conserva i volumi. Un solo scheduler per installazione. Non usare `docker compose down -v` su ambienti con dati da conservare.

In un cloud con CA del proxy: `TAVOLO_BUILD_CA=/etc/ssl/certs/ca-certificates.crt make setup`. La CA è un secret BuildKit temporaneo, non entra nei layer. Su una normale macchina il mount vuoto non sostituisce il trust di sistema.

## Prova la demo in 5 minuti

1. Accedi come `staff1@tavolo.test` con la password locale. Seleziona domani: ci sono tre prenotazioni sintetiche.
2. Apri “Pagina di prenotazione”, scegli data, persone e orario; usa soltanto un nome fittizio e un indirizzo `@example.test`. Non serve un account cliente.
3. La modalità automatica mostra la conferma definitiva. Il Giardino mostra invece “Richiesta ricevuta”: i tavoli sono bloccati finché lo staff approva o scade il termine (30 minuti).
4. Conserva il link personale mostrato nella barra del browser. Puoi modificare data/persone, cancellare e scaricare un calendario ICS dopo la conferma. Se il nuovo orario è occupato, la prenotazione originale resta valida.
5. Nell'agenda usa Arrivato → Completa, oppure No-show. “Nuova prenotazione” inserisce prenotazioni manuali; il checkbox walk-in registra un arrivo adesso, soltanto durante un servizio con disponibilità fisica.
6. Nel simulatore telefono richiedi esplicitamente WhatsApp (premi 1). Numero nascosto, consenso mancante o errore canale conducono al percorso umano simulato. Apri il pulsante di prenotazione nel messaggio simulato.
7. Accedi come gestore con MFA. In Impostazioni modifica regole e, per provare un acconto, imposta **1000 centesimi netti** e **IVA 10%** (soltanto esempio sintetico, non suggerimento fiscale). Prenota: 10,00 + IVA 1,00 = 11,00 EUR. Usa “Simula pagamento acconto”: nessuna carta e nessun incasso.
8. “Elabora in demo” processa l'outbox senza invii. Report mostra conteggi osservati e CSV protetto da formule; fatturato e ROI restano assenti.

I dati demo non si mescolano a dati reali: l'attivazione fuori demo è bloccata dal server. La voce AI non è attivata. Non esiste un'integrazione Reserve with Google.

## Comandi

| Comando | Cosa esegue |
|---|---|
| `make setup` | Verifica prerequisiti, genera `.env` solo se manca e costruisce immagini |
| `make dev` | Avvia demo, migrazioni, worker e scheduler in background |
| `make migrate` | Migrazioni Alembic incrementali, nessun downgrade distruttivo |
| `make seed-demo` | Seed idempotente di due ristoranti sintetici e account locali |
| `make demo-access` | Mostra credenziali demo e codici MFA locali |
| `make test` | Pytest nel DB separato `tavolo_demo_test`, poi Vitest |
| `make test-e2e` | Installa dipendenze browser, poi Playwright sulla demo localhost |
| `make check` | Controlla Compose, ricostruisce, esegue test backend/frontend |
| `make reset-demo` | Ricrea **solo** il database del Compose locale Accomodo e rigenera account; rifiuta configurazioni non demo |
| `make stop` | Ferma i servizi senza cancellare i volumi |

Per E2E, prima `make dev && make seed-demo`. Su Linux una prima installazione può richiedere `cd frontend && npx playwright install --with-deps chromium` (richiede privilegi per le librerie di sistema). Se Chromium è già installato: `cd frontend && TAVOLO_UI_URL=http://localhost:8081 TAVOLO_BROWSER_PATH=/usr/bin/chromium npm run test:e2e` dopo `npm ci`. I test bloccano richieste fuori da localhost e creano soltanto dati fittizi. Il reset cancella i dati **demo**, perciò usarlo solo quando si vuole ripartire; non tocca Agro Sales AI.

## Sviluppo locale alternativo

Richiede Python 3.12+, Node.js 22.12+/24, PostgreSQL 16 e Redis 7. Dal progetto:

```bash
make local-setup
docker run -d --name tavolo-postgres -e POSTGRES_USER=tavolo_owner -e POSTGRES_PASSWORD=local-demo-owner -e POSTGRES_DB=tavolo_demo -p 127.0.0.1:55432:5432 postgres:16-bookworm
# Attendere: docker exec tavolo-postgres pg_isready -U tavolo_owner
docker exec -i tavolo-postgres psql -U tavolo_owner -d tavolo_demo < infra/init.sql
docker run -d --name tavolo-redis -p 127.0.0.1:56379:6379 redis:7-bookworm
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.seed
cd ..
make demo-access
```

Aprire quattro terminali nella cartella Accomodo:

```bash
# 1. API
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --no-access-log
# 2. Frontend
cd frontend && npm run dev
# 3. Worker
cd backend && ../.venv/bin/celery -A app.workers.tasks.celery worker --loglevel=WARNING --concurrency=2
# 4. Scheduler
cd backend && ../.venv/bin/celery -A app.workers.tasks.celery beat --loglevel=WARNING --schedule=../work/celerybeat-schedule
```

Aprire http://127.0.0.1:5174. Questo DB è distinto da quello interno a Compose; gli account vengono generati separatamente. Non usare contemporaneamente seed locale e Compose con il medesimo file credenziali: il file rappresenta l'ultimo ambiente inizializzato.

Test locali: prima applicare migrazioni anche al DB test:

```bash
cd backend
MIGRATION_DATABASE_URL=postgresql+psycopg://tavolo_owner:local-demo-owner@127.0.0.1:55432/tavolo_demo_test ../.venv/bin/alembic upgrade head
../.venv/bin/pytest -q
cd ../frontend
npm run build
npm test
TAVOLO_BROWSER_PATH=/usr/bin/chromium npm run test:e2e
```

## Architettura e stato

FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL (mai SQLite), React + TypeScript + Vite, Redis + Celery. Monolite modulare, API e worker separati. Tenant ricavato da sessione/membership o routing pubblico verificato; `SET LOCAL` per transazione, RLS forzata e FK composite. Allocazioni GiST `[start,end)`, lock di sede e risorse ordinati, versionamento ottimistico. Prenotazione, evento, audit e outbox nella stessa transazione. Token personali solo hash, recapiti cifrati, cookie HttpOnly e CSRF. MFA gestori; super-admin non può impersonare tenant senza concessione.

Leggere [docs/STATUS.md](docs/STATUS.md) e [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md): distinguono implementato, testato localmente, validato con provider e attivato in produzione. Un adapter SDK scritto o un pagamento simulato **non** costituiscono validazione sandbox. [docs/PREREQUISITES.md](docs/PREREQUISITES.md) è l'elenco unico dei prerequisiti esterni. Fase 2 dispone di schema e tool bridge testato, lista attesa con offerta temporanea via API, quote dimostrative: non dell'intera suite commerciale, della console super-admin o di telefonate AI operative.

Nessun sondaggio, marketing, richiesta recensione o invio post-visita. Nessun dato di Nonna Emilia. Nessun servizio acquistato e nessun deploy/push/publish.
