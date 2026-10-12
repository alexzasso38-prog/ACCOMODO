# Demo chat WhatsApp — Twilio Trial

Questo modulo risponde a webhook Twilio firmati con TwiML. Non effettua chiamate all’API outbound e non usa un servizio AI a pagamento. Le risposte sono messaggi reali gestiti da Twilio: consumano il contingente trial secondo le condizioni del provider. Non attiva telefonate, inoltro Iliad, richiamata all’operatore o il numero personale come mittente. Il trial impone propri vincoli ai destinatari e richiede la loro adesione. Non garantisce accesso a qualsiasi numero.

## Render, senza terminale

Environment → Add Environment Variable:

- `WHATSAPP_DEMO_ENABLED`: `true`
- `TWILIO_ACCOUNT_SID`: Account SID della console Twilio.
- `TWILIO_AUTH_TOKEN`: Auth Token privato della stessa console. Mai in chat, GitHub o screenshot.
- `TWILIO_WHATSAPP_FROM`: numero From mostrato nel trial, formato `whatsapp:+…`.
- `WHATSAPP_DEMO_VENUE`: `osteria-demo` (opzionale, default; `giardino-demo` per approvazione manuale).

Salvare e distribuire l’ultimo commit, attendendo Live. GET `/api/whatsapp/demo` mostra solo se configurato, senza segreti. Aprire l’app prima di provare: il risveglio del piano Free può superare il timeout webhook di Twilio. Tutti i dati demo si azzerano con un riavvio/deploy.

Twilio → Try out WhatsApp → Receive a message → Custom. URL esatto `https://accomodo.onrender.com/api/whatsapp/demo`, metodo HTTP POST. Save solo dopo il deploy. L’origine configurata dell’app deve corrispondere a questo dominio HTTPS per verificare la firma.

## Percorso

Scrivere PRENOTA sul WhatsApp trial già collegato. Informativa → SI → DOMANI o GG/MM/AAAA → persone → orario offerto HH:MM → nome fittizio → CONFERMO. Disponibilità effettiva dal motore PostgreSQL; riesame alla conferma. L’esito distingue conferma automatica, richiesta manuale e acconto simulato. Il link personale permette modifica/cancellazione. ANNULLA azzera il percorso incompleto; non cancella prenotazioni già inviate. RICOMINCIA avvia un’altra prenotazione. Dopo 30 minuti d’inattività il percorso riparte.

Conversazioni e risposte cifrate con Fernet, numero indicizzato tramite digest, isolamento RLS tenant. Il lock venue e la transazione memorizzano prenotazione e risposta insieme; replay dello stesso MessageSid restituisce la medesima risposta senza nuove prenotazioni. Il token booking compare solo nel link personale e nella risposta cifrata. Nessun body/numero nei log applicativi. Gli eventi outbox rimangono simulati: solo la risposta al webhook viene inviata da Twilio. Non è un agente linguistico generativo: è un assistente guidato.
