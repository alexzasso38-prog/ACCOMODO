# Accomodo — Meta Cloud API con numero di test

Preparato per superare l’incompatibilità del nuovo trial Twilio con le risposte TwiML XML. Il webhook Twilio già presente resta separato: la sua ricezione HTTP 200 non dimostra consegna del messaggio. Vedere la documentazione Twilio: https://www.twilio.com/docs/usage/trials/try-out-whatsapp#receive-and-reply-to-whatsapp-messages .

Questa integrazione usa il numero TEST assegnato da Meta, non migra il numero Iliad e non abilita telefonate. Nessun abbonamento/provider AI, acquisto o template a pagamento. L’invio resta bloccato senza credenziali Meta, firma valida, destinatari autorizzati e conferma Graph `account_mode=SANDBOX` del mittente. Un numero LIVE o un campo di verifica mancante blocca l’invio. Il risultato della verifica dipende dalle API e dai permessi Meta effettivamente assegnati: non è stato ancora validato con un account reale.

## Cosa è automatico

GET/POST `https://accomodo.onrender.com/api/whatsapp/meta` verifica la sottoscrizione e acquisisce eventi JSON firmati HMAC-SHA256. Le risposte sono inviate con l’API Meta `/{version}/{phone-number-id}/messages` dopo il commit della conversazione. Non si restituisce TwiML al provider Meta.

Percorso: PRENOTA → informativa/SI → DOMANI o GG/MM/AAAA → persone → orario disponibile → nome fittizio → CONFERMO. Disponibilità e prenotazione dal backend PostgreSQL. Il numero viene cifrato nello stato; l’indice conversazione è un digest. Il tenant è selezionato dal server. Il riepilogo non crea una prenotazione. La conferma è atomica con lo stato; lo stesso ID webhook non crea nuove prenotazioni o invii.

Invio in background con recupero del pending dal worker. Il record viene marcato sending prima della richiesta esterna; dopo un timeout o esito incerto non si ripete automaticamente l’invio e non si avanza ulteriormente nella conversazione. Un HTTP 200 di Graph significa submitted, non delivered. Gli eventi status non generano risposte. Nessun invio per messaggi vecchi oltre 10 minuti, numeri fuori allowlist, risorse diverse o messaggi non testuali. Un limite locale di 50 risposte per ristorante/demo blocca ulteriori risposte. Solo risposte testuali a messaggi recenti del tester: nessun template proattivo. Anche il nome del tester deve essere fittizio.

## Autorizzazione Meta necessaria

Il plugin Render permette di gestire hosting e configurazione, non il login/consenso dell’account Meta. Nessun plugin WhatsApp Cloud API utilizzabile è collegato alla conversazione. Serve quindi l’azione del proprietario su https://developers.facebook.com/apps/ : creare un’app per WhatsApp nel proprio portfolio, ottenere il numero di TEST e verificare il proprio numero destinatario nella sezione di configurazione/test API. Le etichette cambiano con la versione della dashboard. Non inserire un metodo di pagamento e non migrare/disinstallare il WhatsApp personale per questa prova.

Le credenziali vanno inserite privatamente in Render Environment, mai in chat/GitHub:

| Variabile | Origine |
| --- | --- |
| META_ACCESS_TOKEN | Token di prova Meta con permessi WhatsApp; se temporaneo, scade secondo Meta |
| META_APP_SECRET | Segreto dell’app Meta per la firma dei webhook |
| META_TEST_PHONE_NUMBER_ID | ID del numero di TEST Meta, non il numero telefonico |
| META_TEST_RECIPIENTS | Numero destinatario verificato, formato internazionale senza `+`; fino a 5 separati da virgola |
| META_VERIFY_TOKEN | Generato e predisposto in Render; da copiare privatamente nel campo verify token della configurazione webhook Meta |
| META_DEMO_ENABLED | `true` solo dopo il completamento della configurazione |
| META_GRAPH_VERSION | Versione Graph, default `v23.0`; usare una versione supportata dai permessi dell’app |
| META_DEMO_VENUE | `osteria-demo` per default; `giardino-demo` per approvazione manuale |

In Meta configurare callback `https://accomodo.onrender.com/api/whatsapp/meta`, token di verifica uguale alla variabile privata Render, sottoscrizione campo `messages` per WhatsApp Business Account e corretta associazione dell’app alla WABA. Meta verifica la challenge in GET. Poi aprire Accomodo per risvegliare Render Free prima della prova e scrivere PRENOTA al numero di test Meta. Le prove con account e messaggi reali non sono state ancora eseguite.

## Stato e limiti

GET senza query mostra enabled/configured e delivery_verified=false: la presenza delle variabili non certifica consegna. I log Meta distinguono webhook acquisito, mittente test non verificato, invio submitted/failed/uncertain e blocco budget, senza body, numeri o segreti. Eventuali limiti/test-policy/costi di Meta vanno verificati sulla dashboard dell’account prima di abilitare l’invio; il codice non aggiunge carte e blocca mittenti LIVE. Resta una demo temporanea: un riavvio di Render rigenera database e chiavi, azzerando prenotazioni, stato e contatore locale. Non costituisce una garanzia generale di utilizzo gratuito di WhatsApp in produzione.
