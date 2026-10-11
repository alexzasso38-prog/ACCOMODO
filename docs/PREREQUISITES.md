# Elenco unico dei prerequisiti esterni

Questa è l'unica lista di attivazione esterna; gli altri documenti vi fanno riferimento. Nessun punto è dichiarato completato solo perché l'adapter esiste.

| Area | Prima dell'attivazione | Stato |
|---|---|---|
| Twilio Voice | Account sandbox, numeri autorizzati, routing account+numero verificato lato server, URL HTTPS stabile, test di trasferimento/callback/fallback/consumi e replay | Mancante |
| WhatsApp ufficiale | Sender/WABA approvato, template UTILITY approvati per lingua, opt-in documentato, policy/finestra inbound verificata, callback firmati e deduplicati | Mancante |
| SMS | Sender e account autorizzati, consenso/canale applicabile e fallback esplicito | Mancante |
| Email | SMTP con STARTTLS, dominio mittente, SPF/DKIM/DMARC, destinatari test autorizzati e prova sandbox | Mancante |
| Stripe | Chiavi test, Connected Account del ristorante supportato, webhook firmati, stato Connect/capabilities verificato, prove duplicati/fuori ordine/pagamento tardivo/rimborsi sul provider | Mancante |
| Acconti | Policy reale, aliquota del ristorante, cutoff/rimborsi/termini approvati e accettazione snapshot; riconciliazione tardiva gestita | Mancante |
| Voice AI | Provider configurato, italiano e handoff autorizzati, limiti, test chiamate reali autorizzate con riepilogo e tool server; audio disattivato | Mancante |
| Commerciale | Validare listino, costi effettivi, eccedenze e budget; accettazione esplicita per abbonamento dopo trial; eleggibilità offerta primi 5 | Mancante |
| Legale/privacy | Validare DPA, ruoli/base giuridica, informativa/titolare, retention e richieste diritti; elenco subprocessori effettivi e trasferimenti | Mancante |
| Fiscalità | Regole fiscali/IVA da professionista e eventuale connettore autorizzato. Quote e riepiloghi non sono documenti SdI | Mancante |
| Hosting UE | Scelta autorizzata, HTTPS, secret manager, DB/Redis gestiti privati, backup e chiavi separate, monitoraggio/alert, staging separato | Mancante |
| Identity ops | Enrollment e recovery MFA, rotazione segreti, gestione utenti/membership e concessioni supporto temporanee con approvazione tenant | Mancante |
| Agenda esterna | Dichiarare autorità; se esterna, conferme autonome bloccate finché integrazione affidabile non è validata | Nessuna agenda esterna configurata nella demo |
| Produzione | Completare test residui in ACCEPTANCE, audit sicurezza e load HTTP, esercitazione restore/RPO/RTO, rimuovere gate solo con review/autorizzazione | Bloccata |

Fino ad allora SEND_REAL_MESSAGES=false, Stripe e voce AI disattivati, nessuna eccedenza reale, nessun auto-convert trial, nessun deploy. Non viene affermata parità dell'intera suite Pienissimo né confronto prezzi verificato; non c'è integrazione Reserve with Google.
