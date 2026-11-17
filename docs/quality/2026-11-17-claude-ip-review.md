# Onafhankelijke Claude Code review van de IP-testopzet

Datum: 17 november 2026. Uitgevoerd via WAIbroker met een zakelijke Claude Code-subscriptie, model `claude-opus-5-5`. Job `8b1056d2-b884-4e5f-99cb-685b09184ece`, status succeeded.

Dit was een review van het aangeleverde veiligheidsvoorstel en de kleine monitorscope. Het remote jobworkspace bevatte geen lokale repositorybestanden. Claude heeft geen productcode doorgelopen of Funda-experimenten uitgevoerd. Hieronder staat zijn ongewijzigde antwoord, geen lijst met bewezen feiten of automatisch goedgekeurde uitvoeringsinstructies.

## Beoordeling door de hoofdreviewer

Overgenomen: eerst eigen endpoints, volledige browser op een aparte testuitgang, netwerkmatig fail-closed, een canary van één zoekpagina, geen automatische herprobeer/IP-wissel na een block, duidelijke no-go bij ontbrekende egresscontrole, en onderzoeken van officiële meldingen/feeds.

Genuanceerd: de claim dat een niet-persistente context per definitie cookies op disk schrijft, is niet bewezen. Playwright documenteert juist dat zulke contexts geen browsingdata naar disk schrijven. De concrete browserbuild en foutartefacten blijven met fictieve secrets te controleren. `tmpfs` is geen algemene uitzondering op de persoonlijke regel dat secrets niet in bestanden buiten de vault mogen komen. Zie [Playwright BrowserContext](https://playwright.dev/python/docs/api/class-browsercontext).

Niet als feit overgenomen: een algemene kwalificatie van alle residential proxynetwerken; daarvoor is providerspecifiek bewijs nodig. Een eigen notitie vervangt geen benodigde toestemming. Een vaste zeven-dagenstop is hoogstens een conservatieve beleidskeuze, geen vastgestelde Funda-blokkeerduur. Camoufox vervangen door standaard Playwright is een mogelijke controleproef, geen bewezen oplossing.

De uitvoerbare vervolgvoorwaarden staan in [het bijgewerkte veiligheidsvoorstel](../superpowers/specs/2026-11-17-ip-isolated-test-plan.md). De route is nog niet ingericht en de nieuwe controles zijn nog niet uitgevoerd.

---

## Originele modelreview

# Second opinion: veilige testopzet voor een kleine Funda-/makelaarsmonitor

Ik heb alleen de aangeleverde tekst beoordeeld. Er is geen verkeer naar Funda gestuurd, er is niets geïmplementeerd en er zijn geen nieuwe testresultaten.

Labels: **[F]** = feit uit de input, **[A]** = aanname of iets wat nog geverifieerd moet worden, **[V]** = voorstel van mij.

---

## 1. Oordeel en bevindingen

**Oordeel:** de aanpak is in de kern goed. Eerst alles testen op eigen endpoints, daarna de hele browser op een aparte runner met een vaste test-uitgang (egress) die bij een storing dicht gaat. Dat is de juiste richting. Maar zonder de aanvullingen hieronder is het **nog geen go** voor een live test. Twee dingen blokkeren:

- er is geen toestemming geregeld;
- het is niet afgedwongen en bewezen dat browserverkeer alleen via de test-egress naar buiten kan.

Is er geen apart geverifieerde egress? Dan is mijn advies: **geen live test vanaf thuis of kantoor**. Willekeurig en weinig verkeer maakt het niet veilig.

**Bevindingen, op prioriteit:**

1. **Toestemming is een harde voorwaarde, geen voetnoot. [F/V]** Volgens de gebruiksvoorwaarden van Funda is voor scrapen vooraf schriftelijke toestemming nodig. Dat het om persoonlijk gebruik en weinig verkeer gaat, verandert daar niets aan.
   - [V] Zet "schriftelijke toestemming of expliciet gedocumenteerd besluit" als eerste go-criterium.
   - [V] Onderzoek eerst routes zonder scraping. [A] Funda lijkt e-mailmeldingen voor bewaarde zoekopdrachten te hebben; controleer of dat bestaat en geschikt is. Daarnaast: officiële feeds of API's van makelaars. Die routes lossen het blokkeerprobleem bij de bron op.

2. **Camoufox is een anti-detectbrowser; dat botst met de eigen uitgangspunten. [F/V]** Het voorstel claimt terecht "geen menselijke onzichtbaarheid". Camoufox is juist gemaakt om fingerprinting te omzeilen.
   - [V] Gebruik voor een canary met toestemming liever gewone Playwright Firefox of Chromium, met een herkenbare en eerlijke User-Agent.
   - Een transparante identificatie, zoals de onveranderlijke bot-headers van Cloudflare Browser Run [F], past beter bij geautoriseerd gebruik dan camouflage.
   - Ik adviseer dus geen residentiële proxypools om detectie te ontwijken. Die zijn gericht op omzeilen, en de herkomst van zulke IP's is vaak twijfelachtig.

3. **Een kill-switch in de applicatie is niet genoeg; dwing het af op netwerkniveau. [V]**
   - Laat de browser draaien onder een eigen OS-gebruiker of in een eigen netwerknamespace.
   - Firewall: standaard alles weigeren. Alleen toegestaan: het proxy- of tunnel-endpoint plus loopback. Dit voor IPv4 én IPv6.
   - DNS loopt via de tunnel of proxy (remote DNS), niet via de lokale resolver.
   - Zo kan "geen directe fallback" niet per ongeluk misgaan door een configfout, een redirect, een subresource, WebRTC of een tweede proces.

4. **Wat je wél en niet kunt beloven over het thuis-IP moet scherp geformuleerd worden. [V]** Zie het kader hieronder. Belangrijkste punt [A]: de eerdere live run met 15/15 resultaten en daarna een 403 had een onbekende herkomst. Als die vanaf thuis kwam, kan het thuis-IP al een slechte reputatie hebben. Test dat **niet** door Funda te bevragen.

5. **"In-memory context" schrijft toch naar schijf. [A/V]** Playwright met Firefox gebruikt ook voor een tijdelijke context een tijdelijke profielmap, met cache en cookies op disk.
   - [V] Zet die profiel- en tempmap op tmpfs en verwijder hem aantoonbaar na de run.
   - Zet core dumps uit.
   - Zet `DEBUG=pw:*` en protocol- of tracelogs uit.
   - Test dat stacktraces van proxyfouten (407, CONNECT) geen proxy-URL met inloggegevens tonen. Doe dat met een nep-secret als canary dat in geen enkele log of bestand mag terugkomen.

6. **De canary moet veel kleiner zijn dan het dagbudget in het voorstel. [V]** De limieten van 25 pogingen en 10 detailpagina's zijn bedoeld voor de monitor, niet voor de eerste meting. Een canary is: 1 browserstart, 1 zoekpagina, 0 detailpagina's, 0 retries bij een blokkade.

7. **Meet de duur van een blokkade niet door opnieuw te proberen. [V]** Na een 403 of CAPTCHA geen "nog eens kijken of het weer werkt". Elke probe is extra verkeer. De cooldown is een vaste beleidsperiode en wordt door een mens beslist.

8. **Testen zonder Funda dekken veel, maar niet alles. [F/V]** Stoppen, cooldown, budget, idempotentie, DST, crashes en het rapport zijn volledig te valideren op eigen fixtures met een nepklok. Niet te valideren: hoe de echte Funda-blokkadepagina eruitziet (de botleverancier is onbekend [F]), het werkelijke aantal requests en bytes per pagina, en hoe de pagina-opbouw verandert.
   - [V] Laat de classificatie daarom fail-closed werken: alles wat niet herkend wordt als geldige resultatenpagina geldt als "stop, geen nul-resultaat".

### Wat je over het thuis-IP wel en niet kunt beloven

**Wel te beloven, mits per run bewezen:**
- Het browserverkeer van deze monitor naar Funda komt niet van het thuis- of kantoor-IP. De browser draait op afstand, de firewall staat standaard dicht, de egress wordt vóór elke target-call gecontroleerd, en er is geen directe fallback.
- Bij een blokkade wordt niet automatisch van IP of fingerprint gewisseld.

**Niet te beloven:**
- Dat het thuis-IP nooit geblokkeerd wordt. Mogelijke oorzaken: eerdere runs, gewoon handmatig surfen, blokkades op range- of ASN-niveau als de "eigen NL ISP"-lijn in hetzelfde netwerk zit, of koppeling via een account of cookies. Die laatste vermijd je deels door geen account of profiel te gebruiken.
- Dat het test-IP of de fingerprint niet geblokkeerd wordt.
- Iets over de oorzaak of duur van de eerdere 403.

Een aparte egress beschermt de scheiding, niet de reputatie [F]. Een VPS-IP is datacenterverkeer en lost detectie niet op [F]. Een tweede ISP-lijn op hetzelfde adres is een zwakkere scheiding dan een externe locatie [A].

---

## 2. Herzien testplan in fases

**Fase 0: autorisatie en alternatieven (geen code)**
- Toestemming aanvragen, of een expliciet besluit vastleggen.
- Funda-meldingen en feeds/API's van makelaars onderzoeken.
- Uitkomst "geen toestemming": de monitor beperken tot bronnen met een toegestane route.

**Fase 1: functioneel, nul Funda-verkeer**
- Eigen fixtureserver die de volgende situaties nabootst: 200-pagina met kaarten, lege pagina, kapotte pagina, onbekende pagina, een CAPTCHA-achtige pagina met HTTP 200, 403, 429 met en zonder `Retry-After`, time-out, verbroken verbinding, redirect naar een vreemd domein, en een trage subresource.
- Een nepklok voor dagwissel, DST en herstart.
- Crashinjectie na persist en vóór afronden.
- Alle twaalf geplande scenario's uitvoeren.
- Extra assert: het budget telt mislukte starts en retries mee, en een 403 of CAPTCHA leidt tot exact nul vervolgnavigaties.

**Fase 2: egress en lekken, nul Funda-verkeer**
Op de runner, met eigen endpoints: een echo-server die het bron-IP teruggeeft (IPv4 én IPv6), een eigen STUN-server en een eigen DNS-log.

Testgevallen:
- tunnel of proxy uitgeschakeld;
- DNS-fout;
- 407 met nepgegevens;
- proxy weigert CONNECT;
- IPv6 aan;
- WebRTC-poging;
- redirect naar een niet-toegestane host;
- een tweede proces probeert direct naar buiten te gaan.

Verwacht resultaat telkens: harde stop vóór enige target-navigatie, en het echo-IP is uitsluitend de test-egress.

Daarnaast de secret-canary: een nepwaarde voor de proxy-inlog wordt alleen in het geheugen geïnjecteerd, en een grep over logs, rapport, tmp en crash-artefacten levert nul treffers op.

**Fase 3: eigen site via de echte remote stack**
De volledige runner, scheduler, SQLite en het rapport draaien een paar dagen tegen de eigen fixtureserver, via dezelfde egress. Daarmee check je planning, locks, idempotentie en het rapport onder echte omstandigheden.

**Fase 4: minimale live canary (alleen na go)**
- Dag 1: 1 browserstart, 1 resultatenpagina voor 1 stad, 0 detailpagina's, 0 retries. Vlak ervoor een egress-check tegen de eigen echo.
- Dag 2–3: precies hetzelfde.
- Daarna, alleen na 3 schone dagen achter elkaar: +1 detailpagina per dag.
- Na nog 3 schone dagen: een tweede ronde per dag.
- Pas na 2 schone weken richting de monitorlimieten, en nooit erboven.

**Stopcriteria (één is genoeg):**
- 403, 429 of een challenge- of CAPTCHA-pagina;
- een niet-herkende pagina;
- een onverwachte redirect;
- een egress-IP dat afwijkt van het verwachte;
- een egress-check die faalt;
- een budgetteller die niet klopt.

**Bij een stop:**
- Funda gaat op slot, minimaal 7 dagen, en alleen een mens kan dat opheffen.
- Geen nieuw IP, geen nieuwe sessie, geen andere fingerprint.
- Een tweede blokkade betekent: geen live Funda-fase meer zonder toestemmingsroute.

---

## 3. Go/no-go-checklist

- [ ] Toestemming of een gedocumenteerd besluit, en alternatieve routes bekeken
- [ ] Fase 1 en 2 groen; alle tests blijven groen
- [ ] Firewall op de runner staat standaard dicht (v4 en v6), alleen de proxy/tunnel is toegestaan, DNS gaat remote
- [ ] Echo-IP = verwachte test-egress, gecontroleerd in dezelfde run vlak vóór de target-call
- [ ] Geen fallbackpad in de code; config zonder proxy betekent: weigeren te starten
- [ ] Geen persoonlijk account, geïmporteerde cookies of browserprofiel; profiel op tmpfs en na afloop verwijderd
- [ ] Geen HAR, ruwe HTML, storage-state, screenshots van het target, trace- of debuglogs
- [ ] Secret-canary-scan levert nul treffers op
- [ ] De lock op het target is persistent en overleeft een herstart; IP- of fingerprintwissel ontbreekt aantoonbaar
- [ ] Browserkeuze bewust gemaakt (zie bevinding 2)
- [ ] Bij twijfel: no-go

---

## 4. Wat veilig opgeslagen mag worden

**[V] Wel opslaan:**
- run-id en UTC-tijden;
- een label voor de egress, plus pass/fail van de check (niet de proxy-URL);
- HTTP-status van de top-level navigatie;
- host en pad van de uiteindelijke URL;
- het classificatielabel (ok / challenge / blocked / unknown);
- aantal requests per domeincategorie en bytes (gemeten of onbekend);
- duur;
- aantal geparste kaarten;
- listing-ID's en URL's met publieke kaartvelden;
- foutcodes van de parser;
- browser- en Playwright-versie.

**Niet opslaan:** cookies, request- en response-headers met cookies of tokens, ruwe HTML, HAR, storage-state, en proxy- of providergegevens.

---

## 5. Resterende risico's en wat echt gemeten moet worden

- **Restrisico:** blokkade van het test-IP of de fingerprint; blokkade op range- of ASN-niveau; wijzigingen in het botbeleid van Funda; de onbekende oorzaak van de eerdere 403; mogelijk al een slechte reputatie van het thuis-IP; juridisch risico zolang er geen toestemming is.
- **Alleen live te meten (en dan alleen binnen de canary):** het werkelijke aantal requests en bytes per resultatenpagina, hoe vaak een challenge voorkomt bij dit minimale volume, en hoe stabiel de kaartstructuur is.
- **Niet te meten zonder extra verkeer, dus niet doen:** hoe lang een blokkade duurt, en wat Funda als drempel hanteert.

**Conclusie:** zonder bewezen gescheiden egress en zonder toestemmingsbesluit is mijn advies geen live test. Mét beide kan het, maar dan met een canary van één pagina per dag en een harde, handmatige stop.
