# Stato Accomodo

Implementata una demo locale operativa, non l'intera suite commerciale richiesta. Agro Sales AI preservato. Non è pronto produzione.

**Implementato e testato localmente**: PostgreSQL/RLS/FK/allocazioni GiST, auth staff e MFA gestori, agenda, flusso pubblico senza account, pending distinto da conferma, gestione stati, modifica atomica/versione/cancellazione, walk-in e tavoli/combinazioni, scadenze/turni/chiusure/DST, link sicuro e ICS, outbox/worker/scheduler e messaggi simulati, IVR/WhatsApp simulati, acconti/rimborsi simulati, report/CSV, listino e preventivi non fiscali, privacy export/anonimizzazione, limiti consumo e trial senza conversione, lista attesa via API e tool bridge voce disabilitata.

**Adapter scritti, integrazioni reali non verificate**: SMTP, Twilio Voice/Messaging, Stripe Connect. Firme/contratti SDK provati localmente. Nessun destinatario reale, nessuna carta, nessun account sandbox utilizzato.

**Validato con provider**: nessuno. **Attivato in produzione**: nulla. `/api/webhooks/{provider}` e invii reali restano bloccati; non esistono incassi/overage reali, voce AI attiva, SdI o Reserve with Google.

**Residui interni concreti**: ciclo completo callback/replay/reconciliation provider; provisioning utenti e support access grants; UI avanzata agenda/exception/rooms/combination e lista attesa; console super-admin/multi-sede; lifecycle subscriptions/billing/refund policy; rettifica contatti/console GDPR completa e cancellazione su backup; test utenti e accessibility manuale estesa; carico end-to-end, restore con volumi realistici, monitoring e processi incidenti. Schema dei contesti successivi non equivale a workflow completo.

**Blocchi esterni e prossimo passo**: PREREQUISITES.md. Collegare account di test/destinatari autorizzati, validare sandbox e policy commerciali/legali, poi completare residui e acceptance staging. Nessuna pubblicazione senza autorizzazione.

Prove: suite Pytest PostgreSQL (28 test), build TS/Vite, Vitest (3 test), Playwright (4 flussi), axe WCAG2.2 e tastiera sulle pagine principali. npm audit: 0 vulnerabilità dopo aggiornamento Vite 6.4.4 / Vitest 4.1.11. Benchmark motore p95 176 ms su 100 sedi a30rps; restore cifrato locale riuscito. Le prove finali Compose e relativi output sono registrati in VALIDATION.md.


Nome prodotto aggiornato ad Accomodo; cartella autonoma `/workspace/accomodo`. Dati demo preservati.


Demo Render: Dockerfile nella radice, frontend e API sullo stesso dominio HTTPS, PostgreSQL/Redis locali al container, account staff configurabili via variabile privata. Configurazione verificata sotto i limiti Free; il deploy esterno attende il clic dell’utente nella dashboard Render. Non è una messa in produzione persistente.
