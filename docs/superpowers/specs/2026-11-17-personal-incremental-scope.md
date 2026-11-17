# Voorstel voor een kleine persoonlijke aanbodmonitor

Status: aangepaste scope voor bespreking, niet geïmplementeerd. Datum: 17 november 2026. Deze scope verfijnt het grotere [dienstontwerp](2026-11-16-reliable-funda-design.md): persoonlijk gebruik, één à twee gekozen steden, twee of drie controles per dag. Het eerste doel is nieuw ontdekt aanbod vinden, geen volledige landelijke kopie of complete prijshistorie.

## Aanbevolen eerste opzet

Eén altijd beschikbare runner, een lokale scheduler en SQLite voor voortgang/gevonden items zijn voor dit volume een passende eerste fase. Een proceslock voorkomt overlap. Atomische lokale exports en een leesbaar runrapport zijn voldoende. Cloudflare, een centrale D1-database, R2, distributed leases en meerdere machines blijven uitbreidingen; er komen geen dubbele actieve databases. Een eventuele latere overstap krijgt een expliciete migratie.

Begin met een vaste lijst bronnen en één à twee vaste steden. Wissel niet willekeurig tussen steden zonder actualiteitsrapport: een stad die vandaag niet is bezocht heeft geen controle van vandaag. Als we later steden roteren, bewaren we per stad de laatste succesvolle controle en de gemiste dekking. Nieuwe websites worden niet automatisch als uitvoerbare bronnen toegelaten; iedere makelaarbron krijgt een gecontroleerde adapter en scope.

## Dagplanning en limieten

Voorgestelde instellingen, geen gemeten Funda-limieten:

- Twee dagelijkse controles; optioneel een derde controle. Plan maximaal drie rondes per lokale kalenderdag, bijvoorbeeld binnen 08:00–09:00, 13:00–14:00 en 18:00–19:00 Europe/Amsterdam.
- Kies de tijdstippen één keer en bewaar ze. Een herstart mag niet opnieuw drie extra rondes plannen. Sla de daadwerkelijke uitvoertijden als UTC op.
- Maximaal één browserproces tegelijk en maximaal drie browserstarts per dag totaal, inclusief mislukte starts. Gebruik één browsercontext/tab binnen een ronde en houd netwerkroute en context gedurende die ronde samenhangend.
- Een Funda-ronde kan beide geselecteerde steden behandelen. De standaardopdracht bekijkt hoogstens één à twee zoekresultatenpagina’s per stad, bij voorkeur gesorteerd op nieuw aanbod waar de bron dat aantoonbaar ondersteunt.
- Maximaal 25 top-level browserpogingen per dag over alle rondes/bronnen, inclusief retries, en maximaal tien nieuwe/gewijzigde detailpagina’s per dag in de eerste proef. Deze teller is iets anders dan alle netwerkrequests: een pagina kan scripts, afbeeldingen en XHR’s laden. Meet daarom ook requests en bytes.
- Een dagelijkse limiet is cumulatief en overleeft herstarts. Een nieuw item boven de limiet blijft in de wachtrij met leeftijd en reden. Niet meer ophalen betekent niet meer vergeten.
- De spreiding dient een rustige belasting en bruikbare planning; er wordt geen menselijke onzichtbaarheid of gegarandeerde toelating mee geclaimd. Browserfingerprint en IP worden niet willekeurig per request gewijzigd.

Twee steden × drie rondes × twee zoekpagina’s betekent maximaal twaalf zoeknavigaties per dag. Met maximaal tien detailpagina’s blijven we vóór eventuele retries op 22 top-level navigaties. Dat is uitsluitend een rekenvoorbeeld, geen meting van bytes of toegestaan verkeer. Bij meer nieuw aanbod dan het budget kan de achterstand groeien; dan bespreken we prioriteit, dekking of een andere toegangsroute.

## Alleen verschillen verwerken

Fase 1 maakt een beperkte baseline van de bezochte resultaten. Bestaande gevonden URLs worden als baseline gemarkeerd, zonder ze allemaal als nieuw aanbod te presenteren. `first_seen_at` betekent nieuw ontdekt door onze monitor, niet bewezen nieuw gepubliceerd door de bron.

Bij latere rondes vergelijken we stabiele bron-ID/URL en de publieke kaartgegevens. Ongewijzigde bekende items krijgen geen nieuwe detailfetch. Een nieuwe URL of een relevante kaartwijziging zoals prijs/status komt in een begrensde detailwachtrij. Een detailfetch die faalt krijgt geen succesvolle seen-status die verdere verwerking onderdrukt. Ontbrekende velden en parserfouten blijven zichtbaar.

Stop niet na het eerste bekende item: betaalde plaatsingen, oude prominente advertenties en veranderende sortering kunnen ervoor staan. Gebruik een kleine begrensde overlap. Eén à twee pagina’s is geen bewijs voor dekking van de hele stad; veel aanbod of een storing tussen controles kan items aan het zicht onttrekken. Een advertentie die tussen twee controles verschijnt en verdwijnt kan deze monitor missen.

Voor makelaars kiezen we eerst een officiële feed/API als die beschikbaar en bruikbaar is, daarna eenvoudige HTTP-overzichten en alleen zo nodig een browser. Gebruik conditionele HTTP-requests als de bron ETag/Last-Modified ondersteunt; ook een 304 blijft een aanvraag. Voer iedere bron volgens zijn eigen rechten, regels en limieten uit. Bewaar bronprovenance. Een object op Funda en een makelaarswebsite wordt niet blind samengevoegd op een onvolledig adres.

## Stoppen en inzicht

Bij CAPTCHA/403 stopt het target en wordt het probleem gemeld; niet alsnog extra sessies of nieuwe IP’s openen. Bij 429 geldt zichtbaar cooldownbeleid. Een time-out/netwerkfout krijgt hoogstens één begrensde retry binnen het dagbudget. Onbekende HTML wordt niet als nul nieuwe woningen gemeld.

Ieder rapport toont: bezochte steden/bronnen, laatste succesvolle controle, bekende/nieuwe/gewijzigde items, opgehaalde details, wachtrij/achterstand, foutredenen, browserstarts, browserpogingen, bytes gemeten/geschat/onbekend en de volgende geplande ronde. Op een fout blijft de vorige goede export bestaan met zijn oorspronkelijke actualiteit.

Secrets blijven in vault/runtimegeheugen. Geen cookieprofiel, HAR, volledige HTML of secretwaarden op schijf/logs. De uitgaande-netwerk- en private-destination-controles uit het grotere ontwerp blijven een voorwaarde voor activering, ook bij een kleine private dienst. Persoonlijk gebruik en weinig verkeer zijn geen bewijs van toestemming of afwezigheid van blokkades; de actuele [Funda-voorwaarden](https://www.funda.nl/voorwaarden-en-beleid/gebruiksvoorwaarden/) blijven apart relevant.

## Eerste tests vóór een live proef

Deze twaalf scenario’s zijn gepland, nog niet gebouwd:

1. Eerste baseline veroorzaakt geen valse nieuw-aanbodmeldingen.
2. Drie ongewijzigde rondes veroorzaken nul extra detailfetches.
3. Eén nieuwe kaart veroorzaakt precies één detailfetch en één duurzame observatie.
4. Een relevante kaartwijziging wordt verwerkt; een niet-relevante wijziging veroorzaakt geen fetchstorm.
5. Crash na persist maar vóór afronden hervat zonder dubbel record of verlies.
6. Herstart/DST/dagwissel laat maxima en ingeplande rondes intact.
7. Een bekend prominent item vóór een nieuw item beëindigt discovery niet te vroeg.
8. CAPTCHA/403/429 geeft de juiste stop/cooldown en geen extra proxy/sessie.
9. Overschrijding bewaart werk in de wachtrij; achterstand wordt getoond.
10. Foutieve detailfetch wordt niet als succesvolle verwerking afgeboekt.
11. Meerdere bronnen bewaren provenance en verwarren appartementunits niet.
12. Een onbekende/lege/kapotte zoekpagina geeft geen valse melding nul nieuwe items en overschrijft geen goede export.

De relevante parser-, identiteit-, secret-, netwerk- en exportcontroles uit de bestaande matrix blijven daarnaast van toepassing. De grotere cloudarchitectuur wordt pas uitgewerkt wanneer deze kleine monitor aantoonbaar bruikbaar is. Er zijn in deze scope-aanpassing geen nieuwe productcode, Funda-aanvragen, proxyabonnementen of deployments uitgevoerd.
