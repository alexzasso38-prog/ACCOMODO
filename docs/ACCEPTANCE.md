# Accettazione e prove

Esiti osservati l'11 ottobre 2026. Lo stato finale viene riepilogato in STATUS.md; prerequisiti esterni soltanto in PREREQUISITES.md.

| Milestone | Prove locali | Residui |
|---|---|---|
| M0 | Migrazioni PostgreSQL 16, due tenant seed, login/cookie/CSRF/ruoli/MFA, RLS senza contesto, runtime NOSUPERUSER/NOBYPASSRLS, FK cross-tenant, pool senza contaminazione | User provisioning e lifecycle support grants; audit sicurezza staging |
| M1 | 50 richieste simultanee → 1 sola allocazione; GiST bypass motore negato; adiacenza [start,end), combinazioni fisiche, rollback modifica, expiry HOLD/pending, chiusure/preavviso/arrivi, DST/mezzanotte, walk-in, E2E cliente/staff/ICS | Test di durata rappresentativa, UI avanzata per eccezioni/sale/combination, test utenti UX quantitativi |
| M2 | Outbox/receipt/confirmation separate, retry/dedup, isolamento worker, opt-in mancante, input recapito, reminder cancellato, nessun invio dopo visita | Sandbox provider; callback reconciliation, esiti incerti, template provider non approvato; fallback SMS operativo |
| M3 | Simulatore consenso/numero nascosto/non mobile/fallimento, firme Twilio con SDK valide/invalide/account errato | Telefonata sandbox, callback/replay mapping account+numero e trasferimento reale |
| M4 | Acconti simulati IVA separata, conferma post-pagamento, duplicati/due tentativi, scadenza/pagamento tardivo, rimborso unico, mismatch tenant, contratto SDK Connect | Stripe test end-to-end, webhook fuori ordine e riconciliazione sul provider, policy reali |
| M5 | Build/lock, Vitest, Playwright, axe e tastiera desktop/360px, report/CSV injection, benchmark motore 100 sedi/30rps, backup cifrato e restore locale | Carico HTTP realistico, volumi restore realistici/RPO/RTO, monitoraggio SLA, WCAG completa manuale e usability test |
| M6 | Bridge voce autorizzato/riepilogo/budget/handoff testato, lista attesa API/offerta HOLD/idempotenza/tenant, quote IVA e soglie usage/cap | Provider voce e chiamate autorizzate; UI lista attesa/controllo multi-sede, integrazioni gestionali, billing SaaS lifecycle e lingue |

Axe senza violazioni sulle schermate testate non dimostra da solo WCAG 2.2 AA completa. Tastiera controllata su form e dialog nativo; ulteriori verifiche screen reader/focus/error recovery richieste. Obiettivi booking<90s/manuale<30s/formazione<45min/90% task autonomi sono ASSUNZIONI non misurate con utenti reali.

Benchmark locale: 100 sedi sintetiche, 10 tavoli/sede, 300 richieste in 10 s a 30rps, p95 176,15 ms, p50 43,21 ms. Misura motore + PostgreSQL + RLS, **non HTTP/proxy/provider**; target del servizio completo ancora da verificare. Script in scripts/load_test.py rifiuta DB diversi da tavolo_demo_test. Restore: dump cifrato, pg_restore riuscito su DB distinto, conteggio prenotazioni corrispondente; non certifica RPO/RTO. Nessuna integrazione esterna validata e nessuna produzione attiva.
