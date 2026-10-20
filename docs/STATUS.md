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


WhatsApp trial: assistente guidato e webhook firmato implementati; disponibilità, prenotazione e replay atomici. In attesa di credenziali private e configurazione webhook da dashboard utente. Nessuna telefonata attiva, nessun messaggio provider inviato durante i test.


Diagnostica WhatsApp trial: log di ricezione, presenza della firma, rifiuti distinti e stato HTTP. Non registrano body, recapiti, segreti o firma. Necessaria perché il Debugger Twilio è inaccessibile nel trial dell’utente.


Meta test: adattatore, challenge/firma webhook, messaggi API in outbox atomica e test locali preparati. Invio limitato a mittente Graph SANDBOX e destinatari verificati, massimo 50 risposte/demo. Nessuna autorizzazione Meta o credenziale disponibile: invio non attivato, prova end-to-end provider non completata. Incompatibilità Twilio trial/TwiML individuata dai log Render e dalla documentazione ufficiale.


Meta test – pulsanti: il webhook accetta anche il tocco su un pulsante "risposta rapida" di un modello approvato (`type=button`, es. "Prenota") e i pulsanti/elenchi dei messaggi interattivi (`button_reply`/`list_reply`), trattati come il testo equivalente. Payload malformati o tipi non supportati ignorati senza errori né risposte. Test locali su PostgreSQL superati; prova con il modello Meta reale non ancora eseguita.


Agenda staff: le prenotazioni dal form pubblico per giorni diversi da quello visualizzato non risultavano visibili (agenda ferma su “oggi”, mai aggiornata da sola). Ora l’agenda si aggiorna ogni 15 s e al ritorno sulla scheda, segnala le nuove prenotazioni online con “Vai al giorno” e mostra i prossimi giorni con il numero di prenotazioni. Test backend su PostgreSQL e verifica browser completati. Limite invariato della demo Render: un riavvio/sospensione azzera il database.


Pagina prenotazione mobile: il modulo compare subito sotto il nome del ristorante; indirizzo, menu e indicazioni spostati sotto il modulo. Corretto su iOS il campo data che si sovrapponeva al selettore persone. Agenda staff: rimossa la scheda “Dal telefono al tavolo” (il simulatore resta nella barra laterale).
