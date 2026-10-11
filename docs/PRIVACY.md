# Privacy — bozze da validare legalmente

Non è una certificazione di compliance. Non inserire dati reali nella demo. Prerequisiti esterni: PREREQUISITES.md.

## Ruoli e basi giuridiche proposte

| Finalità | Ruolo proposto | Base da validare | Dati |
|---|---|---|---|
| Prenotazione/variazione/cancellazione | Ristorante titolare, piattaforma responsabile | Misure precontrattuali/contratto art. 6(1)(b) | Nome, recapito, orario, persone |
| Comunicazioni servizio | Stessi ruoli | Contratto; opt-in canale WhatsApp separato | Recapito, riferimento, stato |
| Lista attesa | Ristorante titolare | Richiesta esplicita e finalità del canale | Nome, email, intervallo desiderato |
| Sicurezza/audit | Ruoli distinti da definire | Interesse legittimo documentato, bilanciamento | Actor, azione, metadata redatti |
| Fatturazione SaaS B2B | Piattaforma titolare | Contratto e obblighi fiscali | Dati legali/billing del ristorante |

La checkbox web attesta presa visione, non consenso obbligatorio marketing. Opt-in WhatsApp è distinto e tracciato. Dati salute/allergie disabilitati, nessun campo note esposto; nessuna trascrizione sanitaria persistita, audio non registrato. Non inviare tali dati a modelli AI.

[ASSUNZIONE] Retention: identificativi prenotazioni 12 mesi, contenuti comunicazioni/metadati chiamate 90 giorni, eventuali note particolari 7 giorni dopo servizio (raccolta non abilitata). Worker anonimizza i clienti con ultima prenotazione >365 giorni, azzera destinazioni Notification e caller encrypted dopo 90 giorni e cancella ConversationMessage alla scadenza. Dati finanziari richiedono policy separata: non vengono inventati termini fiscali.

Export GDPR e anonimizzazione disponibili via endpoint manager, identità verificata esplicitamente, audit. Non si elimina un ospite con prenotazioni attive senza prima decidere gli obblighi; errore 409. Anonimizzazione rimuove nome, recapiti, opt-in, destinazioni, note, conversazioni e revoca token; statistiche prenotazione pseudonime rimangono. UUID/link a dati fiscali e coperture backup devono essere valutati per una cancellazione reale. Non chiamare questa funzione cancellazione certificata di tutti i dati. Rettifica recapiti e gestione richieste con SLA completo richiedono la console privacy successiva.

## Modello DPA

Da completare con parti/titolare e professionista: oggetto e durata, natura/finalità, categorie interessati/dati; istruzioni documentate e divieto uso autonomo; riservatezza, misure tecniche; autorizzazione subprocessori, notifica variazioni; assistenza diritti/DPIA/breach; tempi e canali notifica; cancellazione/restituzione inclusi backup; audit; trasferimenti e SCC/TIA ove applicabili. Il template non costituisce contratto sottoscritto.

## Registro subprocessori candidato

| Fornitore | Finalità | Stato e verifica |
|---|---|---|
| Hosting UE da scegliere | API, DB, Redis, backup | Non selezionato; DPA/regioni da verificare |
| Twilio | Voce/WhatsApp/SMS | Non collegato; contratti, sedi trattamento/trasferimenti da verificare |
| SMTP da scegliere | Email servizio | Non collegato |
| Stripe | Pagamenti ristorante e futuro billing | Non collegato; ruoli contrattuali separati da verificare |
| Provider voice AI | Eventuale audio in streaming | Non selezionato; minimizzazione, DPA e trasferimenti richiesti |

Checklist trasferimenti: localizzazione reale e subprocessori; basi trasferimento/SCC; TIA; cifratura e gestione chiavi; dati minimi; accessi supporto autorizzati e temporanei; retention/cancellazione del provider; portabilità; procedure incidente e audit.

Backup: demo dimostra dump cifrato e restore in DB separato; la chiave locale di test è conservata in work, NON è un modello operativo di custodia. Produzione richiede chiavi in secret/KMS separato, lifecycle, scadenza backup e registro cancellazioni da riapplicare dopo restore prima di riaprire traffico. Accesso super-admin indiscriminato è negato; lifecycle delle concessioni supporto non è ancora attivato.
