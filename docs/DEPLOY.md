# Staging UE — piano riproducibile, non pubblicato

Nessun hosting scelto/acquistato e nessun deploy eseguito. Prerequisiti unici in PREREQUISITES.md. Il Compose è un ambiente demo locale, non una configurazione pubblicabile. Il server fail-fast fuori APP_ENV=demo anche con credenziali valorizzate: gate esplicito finché acceptance e review non sono completate.

Per una staging autorizzata UE: build dalle versioni lock, immagini con digest registrato, frontend statico HTTPS dietro reverse proxy, API privata, PostgreSQL/Redis gestiti e privati, worker e un solo scheduler. Secrets in secret manager: session/encryption/provider, chiavi backup separate. `.env.example` non è configurazione produzione. Runtime DB senza superuser/BYPASSRLS, credenziale migrazione temporanea separata, roles identity/routing da review. Migrazioni una tantum prima del rollout; mai downgrade distruttivo. Connessioni tenant riferiscono secret manager, non credenziali browser.

TLS, cookie Secure/HttpOnly/SameSite, Origin+CSRF; CORS e frame-ancestors da allowlist reale dei domini widget. Nginx demo permette solo self/localhost. Aggiungere un dominio necessita aggiornamento esplicito del proxy CSP e ALLOWED_WIDGET_ORIGINS, non wildcard. Widget usa token in header e non dipende dal cookie terze parti; offrire sempre link diretto. Non includere token in query o telemetria.

Procedura: completare test in ACCEPTANCE; creare ambiente staging separato e DB nuovo; configurare secrets/allowlist; backup pre-migrazione; migrare con role appropriato; verificare /ready e RLS; rolling update API/worker; verificare contratti/provider solo con destinatari/account autorizzati; osservare errori e code; autorizzazione finale alla pubblicazione prima di aprire traffico.

Rollback: ripristinare immagine precedente solo se compatibile con schema, bloccare dispatch per evitare duplicati; per breaking migration restore in DB nuovo dal backup verificato, controllare RLS/consistenza/GDPR, riconciliare provider, switch endpoint controllato. Non acquistare servizi o cambiare DNS autonomamente. Gli obiettivi 99,5%, p95<500ms, reminder<2min, RPO/RTO non sono SLA raggiunti senza monitoraggio e prove realistiche.
