# Decisioni
- [ASSUNZIONE] Agro Sales AI è incompatibile come prodotto: Accomodo è un sottoprogetto indipendente, senza riscrittura o modifica dei suoi dati.
- [ASSUNZIONE] Demo esclusivamente PostgreSQL 16; ruolo proprietario per migrazioni/seed, ruolo tavolo_app NOSUPERUSER NOBYPASSRLS per API e worker. RLS FORCE su dati operativi, FK composite.
- [ASSUNZIONE] Lock di sede per serializzare modifiche di disponibilità/limite arrivi, seguito da lock di risorse UUID ordinati. Intervalli [inizio,fine). Il vincolo GiST è la barriera finale. Prestazioni da misurare.
- [ASSUNZIONE] Pending blocca tavoli per 30 minuti (configurabile). HOLD 5 minuti. Modifica atomica; scadenze emettono eventi e liberano risorse.
- [ASSUNZIONE] Orari DST ambigui e inesistenti non sono prenotabili; non si sceglie silenziosamente una delle due occorrenze. Durata in minuti reali UTC; servizi notturni appartengono al giorno di avvio.
- [ASSUNZIONE] In demo cancellazione gratuita fino all'inizio e rimborso simulato completo. Nessuna policy commerciale reale dedotta. Acconto solo simulato, con aliquota esplicita configurata dalla sede.
- [ASSUNZIONE] Identità globali e assegnazioni non contengono dati ospiti. Routing pubblico è una tabella senza PII, non un tenant_id scelto dal client. Sessione seleziona una membership verificata; nessun impersonamento super-admin.
- [ASSUNZIONE] Token prenotazione nel frammento URL, poi header; digest SHA256 soltanto in DB. Link non inviati a provider demo. Cookie sessione HttpOnly, SameSite=Lax, Secure fuori demo; mutazioni staff protette da CSRF e Origin.
- BLOCCO: nessun account/provider, approvazione WhatsApp, Connected Account o configurazione commerciale autorizzata. Nessun invio/incasso/overage reale; produzione fail-fast fino alle verifiche residue.
- [ASSUNZIONE] Walk-in registrato dallo staff: inizio entro 5 minuti da adesso, durante un servizio effettivo e con durata completa prima della chiusura; stato SEATED e nessun acconto online. Risorse e blocchi sempre verificati.
- [ASSUNZIONE] Il worker sopprime anche comunicazioni di servizio rimaste in coda oltre la fine della prenotazione o dopo COMPLETED/NO_SHOW: nessun recupero di messaggi dopo la visita.
- [ASSUNZIONE] Lista attesa demo: richiesta esplicita email, offerta manuale dello staff sul primo orario richiesto, HOLD fisico 5 minuti. Link copiato in demo, nessun invio a destinatari reali. L’automazione delle alternative e l’interfaccia dedicata restano successive.
- [ASSUNZIONE] Voce fase 2: interfaccia provider e tool bridge con routing server, riepilogo confermato, budget e handoff; nessun provider conversazionale scelto o attivato. Test locali del bridge non validano una telefonata AI.
- [ASSUNZIONE] Staff può registrare un ospite senza recapito, per evitare contatti inventati. La prenotazione e l'evento persistono; nessuna comunicazione viene accodata se non esiste un recapito. Il cliente web deve scegliere e fornire un canale valido.
- Il reverse proxy usa resolver DNS Docker con TTL breve per sopravvivere alla ricreazione dell'API. Il seed può essere eseguito con UID host; il codice immagine è leggibile, i segreti restano fuori immagine.


## Nome e separazione del progetto
Il prodotto si chiama Accomodo e risiede in `/workspace/accomodo`, separato da Agro Sales AI. Il branding, il titolo browser e la documentazione sono aggiornati. Gli identificatori tecnici PostgreSQL, Compose, cookie e gli account demo già generati restano compatibili con i dati esistenti; non sono il nome commerciale.


## Demo Render gratuita
Pubblicazione di prova con un solo container non root, PostgreSQL e Redis su loopback, UI e API sullo stesso dominio HTTPS. Dati rigenerati a ogni avvio; password staff via variabile privata Render. Nessuna attivazione produzione o provider. Il dispatcher periodico in un processo separato sostituisce Celery/beat soltanto nella piccola demo pubblica.


Demo WhatsApp senza AI a pagamento: TwiML inbound, routing server al ristorante demo, firma Twilio obbligatoria, stato e risposta cifrati in PostgreSQL nella stessa transazione della prenotazione. Nessun invio outbound né rimozione dei gate provider.
