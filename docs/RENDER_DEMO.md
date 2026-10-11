# Accomodo — link HTTPS su Render, demo con dati temporanei

Il Dockerfile nella radice contiene frontend, API, PostgreSQL e Redis. Non richiede servizi database acquistati. Il processo usa un account non root; PostgreSQL/Redis ascoltano solo loopback. Il ruolo API non è superuser e mantiene RLS. Messaggi, chiamate e pagamenti sono simulati. Questo ambiente non è produzione.

## Configurazione dal browser

In Render: New → Web Service → GitHub `alexzasso38-prog/ACCOMODO`.

| Campo | Valore |
| --- | --- |
| Name | `accomodo` (o un nome libero) |
| Language | Docker |
| Branch | main |
| Region | Frankfurt, se disponibile |
| Root Directory | vuoto |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context Directory | `.` se richiesto, altrimenti predefinito |
| Docker Command | vuoto: usa il comando dell'immagine |
| Instance Type | Free |
| Health Check Path | `/ready` |

In Environment Variables aggiungere **DEMO_STAFF_PASSWORD**, valore privato scelto dall'utente con almeno 16 caratteri. Non metterlo in GitHub, screenshot o messaggi. Nessuna chiave API provider è richiesta. Render fornisce automaticamente PORT e RENDER_EXTERNAL_HOSTNAME: il codice ricava l'origine HTTPS e genera le chiavi locali all'avvio.

Premere Deploy Web Service. Attendere lo stato Live. Aprire l'URL `https://<nome-effettivo>.onrender.com` mostrato da Render; non presumere che il nome sia disponibile.

Account staff: `staff1@accomodo.test` (Osteria del Porto) e `staff2@accomodo.test` (Giardino delle Spezie). Password: quella della variabile privata. MFA vuoto. I gestori hanno password e MFA casuali non pubblicati: questa demo web serve per il percorso ospite e staff.

Provare domani nell'agenda; dal percorso cliente `/b/osteria-demo` prenotare con nome fittizio e `ospite@example.test`, modificare/cancellare e scaricare ICS. `/b/giardino-demo` richiede approvazione dello staff2. Il simulatore telefono non invia messaggi.

## Limiti espliciti

Ogni avvio del processo genera un nuovo database con due ristoranti fittizi. Prenotazioni, sessioni e link creati prima dell'avvio non sono conservati. Il piano Free può andare in sospensione: al ritorno attendere l'avvio. Ogni avvio ricrea prenotazioni per il giorno successivo. Non inserire dati veri. Non sono installati dischi persistenti. Questa configurazione non ha SLA, backup persistente o provider reali. Controllare il prezzo corrente nella dashboard prima del deploy; la configurazione non richiede piani a pagamento.

Per uso reale è necessario un progetto separato di messa in produzione: PostgreSQL/Redis persistenti, worker, segreti stabili, validazione provider e controlli già elencati in ACCEPTANCE.md. Non rimuovere il gate produzione per pubblicare questa demo.
