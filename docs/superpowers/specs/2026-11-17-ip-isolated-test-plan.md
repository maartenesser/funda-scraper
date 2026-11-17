# IP beschermen tijdens de eerste monitortests

Status: veiligheidsvoorstel na onafhankelijke Claude Code-review, nog niet geïmplementeerd. Datum 17 november 2026. Dit document heeft voor de eerste toegangstest voorrang op het voorstel om de eigen thuisverbinding als baseline te gebruiken. De [kleine monitorscope](2026-11-17-personal-incremental-scope.md) blijft het latere gebruiksdoel.

## Wat we kunnen afschermen

Geen testmethode garandeert dat Funda geen enkel IP, account of netwerkbereik blokkeert. We kunnen wel eisen dat deze monitor zijn Funda-verkeer uitsluitend vanaf een gescheiden testuitgang verstuurt. Thuis- en kantoornetwerken zijn dan geen onderdeel van dat requestpad. Het test-IP kan alsnog geblokkeerd worden. Oorzaak en duur van de eerdere 403 zijn onbekend; een extra thuisrequest om dit te controleren is geen veilige diagnosetest.

Voor deze proef draait de volledige browser op een remote, geïsoleerde runner. De lokale computer bestuurt alleen die runner. Geen persoonlijke browserprofielen, geïmporteerde Funda-cookies of persoonlijke Funda-login in de scraper. Een proxy alleen op een lokale browser is niet de gekozen bescherming; de remote plaatsing voorkomt dat een proxyfout een lokale browser terug laat vallen op het thuisnetwerk. Een VM-IP is wel datacenterverkeer en bewijst geen betere toelating door Funda.

De remote runner heeft een expliciet gekozen uitgaande route, met optioneel een vaste testproxy. Een Tunnel, VPN of Gateway-route mag die browserverbinding niet alsnog via thuis/kantoor laten uitgaan. Bron-/subresourcenavigatie, IPv4/IPv6 en andere browserprocessen moeten onder hetzelfde netwerkbeleid vallen.

## Eerst een optie zonder geautomatiseerde Funda-aanvragen

Voor persoonlijk nieuw-aanbod volgen zijn officiële bewaarde zoekopdrachten met e-mailmeldingen een serieuze eerste optie. Funda documenteert deze functie. We kunnen ontvangen meldingen twee of drie keer per dag verwerken zonder daarbij automatisch de Funda-links, afbeeldingen of trackingpixels op te halen. De mailbezorgfrequentie bepaalt de actualiteit; twee of drie mailboxcontroles garanderen niet evenveel nieuwe bronupdates. E-mails bevatten niet noodzakelijk alle gewenste detailvelden.

Bron: [Funda over bewaarde zoekopdrachten en e-mailmeldingen](https://www.funda.nl/meer-weten/kopen/hoe-haal-ik-het-maximale-uit-mijn-zoektocht-op-funda/). De accountinstelling en daadwerkelijke mailinhoud zijn hier nog niet ingericht/getest. Ontvangen mail wordt als onbetrouwbare tekst behandeld; er worden geen volledige mailbodies, loginlinks of geheime mailinhoud gedumpt. Makelaarsfeeds/meldingen zijn aanvullingen als de betreffende bron ze aanbiedt.

## Fase 1: volledig oefenen op eigen endpoints

Geen Funda-verkeer. Synthetische pagina’s leveren: geldige kaarten, lege resultaten, onbekende HTML, CAPTCHA200, 403, 429, time-outs, kapotte verbindingen, redirects, trage of grote subresources. Fake clocks controleren planning, jitter, dagbudget, herstart en DST. Een crash na persist geeft bij hervatten geen dubbele verwerking.

Vereist: nul extra navigaties na een blokkade, geen lege succesvolle export uit onbekende HTML en geen verhoging van het dagelijkse budget bij herstart. De twaalf scenarios uit het persoonlijke scopevoorstel plus relevante identiteit-, secret-, egress- en exportcontroles gelden. Bestaande groene librarytests vervangen deze nieuwe servicecontroles niet.

## Fase 2: de echte remote route op eigen endpoints controleren

Gebruik een eigen observer/echo-endpoint en eigen gecontroleerde DNS-/netwerktests. Bewaar route-ID en pass/fail, niet credential-URLs of ruwe netwerklogs. Controleer dat de geobserveerde bron uitsluitend de goedgekeurde testuitgang is en niet thuis/kantoor. Eén geslaagde HTTP-IPcheck is niet genoeg.

Verplicht foutinjecteren: proxy/tunnel uit, fout credential/407, CONNECT geweigerd, DNS-fout, IPv6, WebRTC/STUN-poging, private of afwijkende redirect/subresource, achtergrondverkeer en een tweede proces dat direct probeert te verbinden. De jobnetwerknamespace/firewall/policy-forwarder weigert standaard alle niet-goedgekeurde uitwegen. Een applicatiecheck alleen is onvoldoende. De beschermde eigen endpoints moeten nul verboden verbindingen tellen: een client-error bewijst dit niet.

Geen directe fallback. Een ontbrekende proxyconfig in een proxyprofiel is een startupfout; die wordt niet geïnterpreteerd als directe verbinding. De routecontrole gebeurt bij het begin van iedere canarysessie en opnieuw na een routefout, op eigen endpoints. Geen publieke IP-check per Funda-resource.

De resultatenweergave is tekst/gestructureerde data. Externe Funda-afbeeldingen, iframes, scripts, trackingpixels, linkpreviews of achtergrondverrijking mogen niet vanaf de computer van de gebruiker worden geladen. Test ook dit kijkpad met een eigen observer. Anders kan een volledig remote scraper alsnog lokaal verkeer veroorzaken.

Geheime waarden blijven in vault/runtimegeheugen. Geen HAR, storage-state, tracing/protocoldebug, volledige HTML of profieldumps. Gebruik een niet-persistente context en controleer met fictieve canary-cookies/credentials de concrete build, foutpaden en geproduceerde artefacten. tmpfs wordt niet als vrijstelling gebruikt voor het verbod op secretbestanden buiten de vault. Playwright zegt dat non-persistent contexts geen browsingdata naar disk schrijven; dit zegt niet dat ieder OS-artefact onafhankelijk is gecontroleerd. [Documentatie](https://playwright.dev/python/docs/api/class-browsercontext)

## Fase 3: gecontroleerde eerste live canary

Alleen na een groene functionele test, bewezen gescheiden route en de benodigde toestemming/scope. Zonder die route komt er geen live test vanaf thuis of kantoor.

Begin met één browserstart, één zoekpagina voor één stad, nul detailpagina’s en nul automatische retries. Dat is een voorgestelde conservatieve canary, geen bewezen veilige Funda-drempel. Een pagina kan meerdere requests veroorzaken; meet geaggregeerde aantallen en bytes.

Herhaal alleen in vooraf geplande, afzonderlijke vensters nadat de vorige canary zonder rode signalen is afgerond. Eerst enkele dagen dezelfde kleine proef, dan expliciet beslissen over één detailpagina of een tweede ronde. Het latere maximum van 25 paginapogingen/dag is geen doel voor dag één.

Bij 403, CAPTCHA, herhaalde/afgesproken 429, onbekende HTML, onverwachte route/redirect, falende egresscontrole of een onverklaarde teller stopt het target. Geen automatische nieuwe proxy, fingerprint, sessie of test of de blokkade alweer weg is. Alleen beheer bepaalt een volgende proef; een wachttijd op zichzelf is geen bewijs dat een blokkade voorbij is. Geldig Retry-After is minimaal te respecteren, geen garantie op latere toegang.

Voor een geautoriseerde baseline is gewone Playwright een zinvolle extra controle naast de bestaande Camoufox-combinatie. Een verschil in browser is een aparte experimentele variabele; het wordt geen onbewezen bypassclaim. Cloudflare Browser Run heeft eigen herkenningsheaders; Cloudflare uitsluitend als besturing voor een aparte runner is een andere route. [Cloudflare FAQ](https://developers.cloudflare.com/browser-run/faq/)

## Go/no-go voor de eerste live aanvraag

- Benodigde toestemming/scope en budget vastgelegd; een eigen notitie vervangt geen toestemming.
- Geen Funda-testaanvragen vanuit thuis/kantoor; volledige browser remote met gescheiden testuitgang.
- Foutinjecties en eigen-endpointcontroles groen, inclusief fail-closed en geen verboden verbindingen.
- Geen persoonlijke scraperlogin/cookies; geen impliciete credential- of artefactopslag.
- Resultatenweergave veroorzaakt geen lokale externe requests.
- Eerste opdracht beperkt tot één pagina; stopstatus en budget overleven herstart.
- Route-/provider-/Linux- en privacychecks die nog niet zijn uitgevoerd staan NOT_RUN; NOT_RUN is geen groen.

## Claude Code second opinion

De [volledige review met onze beoordeling](../../quality/2026-11-17-claude-ip-review.md) is daadwerkelijk via een zakelijke WAIbroker Claude Code-job uitgevoerd. Claude beoordeelde aangeleverde tekst en stelde vooral netwerkmatige uitsluiting, een veel kleinere canary en minder herproberen voor. Enkele claims zijn expliciet genuanceerd; de modelreview is geen vervanging voor documentatie of uitgevoerde tests.

In deze ronde zijn geen nieuwe Funda-experimenten, aankopen, deployments of productcodewijzigingen uitgevoerd. De reviewjob en dit bijgewerkte testvoorstel zijn de concrete resultaten.
