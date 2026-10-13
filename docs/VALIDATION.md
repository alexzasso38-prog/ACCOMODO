# Verifica locale — 11 ottobre 2026

Ambiente osservato: Python 3.12.14, Node 24.19, Docker 28.4, PostgreSQL 16.15, Redis 7, browser Chromium di sistema. Dipendenze bloccate in backend/requirements.lock e frontend/package-lock.json; build Node 22 nel Dockerfile. Vite6.4.4/Vitest4.1.11 aggiornati dopo audit; npm audit finale zero advisory rilevati. Gli SDK Twilio9.5.2/Stripe12.1.0 sono installati e i contratti locali testati, non sandbox provider.

- Migrazioni 0001/0002 riuscite sia su DB demo che test, anche da schema nuovo attraverso reset.
- `make dev` avvia i sei servizi persistenti; migrate termina con exit0. API/db/redis healthy; porta host esclusivamente 127.0.0.1:8081, DB/Redis interni.
- Seed due ristoranti, account casuali/MFA cifrati, dati fittizi. `make reset-demo` eseguito sulla sola demo Compose: ripartenza e nuove credenziali riuscite. Guard contro APP_ENV produzione provata in directory test senza chiamare Docker.
- Pytest PostgreSQL: **28 test passati**. Una sola allocazione su50 richieste simultanee, composite FK/RLS/sessioni/CSRF/MFA, combinazioni, [start,end), rollback modifica, expiry, DST/notturni, arrivi, walk-in, contatto facoltativo staff, privacy, outbox/retry/idempotenza/no-post-visita, pagamenti/rimborsi simulati, firme SDK, quote/cap/lista attesa e voce bridge.
- `make check` finale eseguito con successo via Docker Compose: 28 Pytest e 3 Vitest. Lo script reset viene montato read-only nel container di test.
- Vitest: **3 test passati**; TypeScript/Vite build riuscita. Audit npm zero vulnerabilità rilevate.
- Playwright: **4 flussi passati** anche su ingress Compose: cliente automatico/modifica/calendario/cancellazione, richiesta manuale, staff/telefono/report, mobile360px/tastiera. Axe WCAG2A/2AA/2.1AA/2.2AA senza violazioni sulle pagine testate.
- Benchmark:300 richieste,100 sedi sintetiche/10 tavoli,30rps, p95 motore176,15ms e p5043,21ms. Non è una misura del percorso HTTP né uno SLA garantito.
- Backup Fernet + pg_dump/pg_restore in DB locale distinto: restore riuscito, conteggio prenotazioni corrispondente. RPO/RTO e custodia chiavi produzione non dimostrati.

Durante le verifiche sono emersi e corretti conflitti di import UUID/Session, contrasto testi, focus durante loading, permessi dello SQL e del seed container, risoluzione DNS nginx dopo ricreazione API, e superficie SDK Stripe/Twilio specifica delle versioni bloccate. Non ci sono stati cambiamenti a file tracked Agro Sales AI. Nessun push, deploy, acquisto, invio reale, incasso o account provider contattato. L'avvio su 0.0.0.0 host è stato rifiutato dalla review automatica; la demo usa solo loopback. Le porte interne container non sono esposte.

Limiti: test automatizzati locali non equivalgono a usability test, audit legale/sicurezza completo, sandbox provider, validazione WCAG manuale completa o prontezza produzione. Residui e prerequisiti in STATUS/ACCEPTANCE/PREREQUISITES.


## Demo HTTPS per Render
Immagine Docker di demo compilata e avviata in QA con 512 MiB e 0,1 CPU, PostgreSQL/Redis privati e healthcheck `/ready` positivo. Frontend definitivo compilato con TypeScript/Vite e verificato via proxy HTTPS locale: 4 Playwright passati (13,6 s), inclusa una risposta agenda precedente consegnata dopo quella del giorno selezionato. 28 test PostgreSQL di regressione passati. Cookie Secure e login dei due tenant verificati. Il consumo memoria osservato era circa 254 MiB, non una misura del picco né una garanzia di carico. Nessun deploy Render eseguito dagli strumenti: avvio dalla dashboard dell’utente ancora da fare. Dati temporanei rigenerati a ogni avvio.


WhatsApp trial: 30 test PostgreSQL passati, inclusi percorso completo, nessuna creazione prima di CONFERMO, replay senza duplicati, isolamento numero/tenant, cifratura stato, firma/account invalidi e feature disabilitata. Provider reale non ancora provato.


Diagnostica trial: 3 test webhook passati, incluso controllo che body, numero, Account SID e Auth Token non compaiano nei log. Causa della mancata risposta reale ancora da determinare con i nuovi log Render; non richiede upgrade Twilio.


## Meta test adapter
39 test PostgreSQL passati (52,93 s), inclusi firma/challenge, percorso completo fino a prenotazione, replay senza nuovo invio/prenotazione, isolamento tenant e destinatari, cifratura, mancata creazione prima di CONFERMO, mittente LIVE o non verificabile bloccato, eventi vecchi ignorati, budget50, esito incerto senza reinvio e modalità manuale. Le risposte HTTP Meta nei test sono simulate con MockTransport, non costituiscono validazione provider reale. Nessun messaggio reale inviato. Render predisposto con verifica webhook privata e allowlist del tester; integrazione disabilitata in attesa dell’autorizzazione Meta.
