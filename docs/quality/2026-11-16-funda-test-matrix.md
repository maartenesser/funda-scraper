# Testmatrix en bewijs voor de Funda-dienst

Status: voorgestelde controles; de nieuwe testgevallen zijn nog niet geïmplementeerd. De bestaande baseline omvat 44 gevallen. De [specificatie](../superpowers/specs/2026-11-16-reliable-funda-design.md) is leidend. Een checkbox of testnaam is geen geslaagde test: elke release bewaart commit, artifact-digest, omgeving, policyversie, testresultaat en bekende uitzonderingen.

## Testlagen

| Laag | Omgeving | Doel | Wanneer |
|---|---|---|---|
| Library-regressie | Bestaande Python-matrix 3.9–3.13 | Huidige API niet ongemerkt breken | Iedere PR |
| Collector-unit | Python 3.12, fake clock en synthetische data | Classificatie, normalisatie, budget- en retrybeleid | Iedere PR |
| Browserintegratie | Echte gepinde Camoufox, lokale eigen HTTP/HTTPS-fixtures | DOM, consent, lifecycle en netwerkgedrag | Iedere relevante PR; digest/cache expliciet vastzetten |
| Contracttest | Gedeelde JSON-payloads, Python en TypeScript | Zelfde schema-interpretatie aan beide kanten | Iedere PR met contract/consumerwijziging |
| Control-integratie | Workers-runtime met echte lokale D1/R2-bindingsemulatie | SQL-constraints, claimen, rollen en publicatie | Iedere control-PR |
| Staging herstel | Afgeschermde cloudomgeving, eigen oorsprong | Uitval, echte bindings, auth, leases en restore | Voor release en na relevante infra-/schemamigratie |
| Live canary | Toegestane Funda-scope, begrensd budget | Toegang en broncompatibiliteit | Expliciet gepland; niet bij iedere commit |
| Productiechecks | Geaggregeerde status, geen raw secrets/HTML | Actualiteit, drift, blokkades, kosten | Gedurende de dienst |

Mocks vervangen een netwerkprovider of klok, niet de parser of de database die we juist willen testen. Lokale browser- en D1-tests bewijzen geen proxykwaliteit of Funda-toegang. Op eigen endpoints mag belasting worden gesimuleerd; Funda is geen loadtestdoel.

## Bronherkenning en datakwaliteit

| ID | Testgeval | Verwacht bewijs |
|---|---|---|
| C01 | HTTP 200 met CAPTCHA-HTML | `BLOCKED`, nul observaties, circuit open; geen lege succesvolle export |
| C02 | 401/403 en 429 afzonderlijk | Juiste toegang/rate-limitcategorie; geen automatische proxyhop |
| C03 | Zoekcanonical met rijk genest House-object | `SEARCH_REDIRECT`, nooit dat andere House als gevraagde woning |
| C04 | Onbekende of deels geladen DOM | Renderdeadline of `UNRECOGNIZED`; nooit empty success |
| C05 | Geldige lege primaire ItemList met aanbevelingen | Alleen herkenbaar leeg zoekresultaat; aanbevelingen tellen niet |
| C06 | ID verschilt, expliciete canonical, zelfde volledige adresroute | Alias geregistreerd, één object; requested én canonical ID bewaard |
| C07 | Andere stad, markt, adres of appartementunit | Quarantaine/identity mismatch; canonical maskeert niets |
| C08 | Makelaar/Organization vóór Residence in JSON-LD | Woningdocument gekozen; geen makelaarsadres als object |
| C09 | Layoutvariant met gewijzigde selectors | Herkende JSON-LD/labels werken of expliciete drift; geen verzonnen waarden |
| C10 | Prijs op aanvraag, ontbrekende prijs, echte nulprijs, verkeerd bedrag | Verschillende betekenissen/reason codes; nooit alles als prijs nul |
| C11 | Laatste vraagprijs versus vraagprijs versus koopsom | Afzonderlijke prijssoort; geen koopsom uit advertentie afgeleid |
| C12 | Oppervlakte integer/decimal/thousands en ontbrekende waarde | Goede normalisatie of `INCOMPLETE`; geen stil weggefilterde woning |
| C13 | Ontbrekend bouwjaar/energie/kamers en loginveld | Null met passende reden/provenance; geen jaar nul of afgeleide bronstad |
| C14 | Alle bronrecords verliezen een analytisch verplicht veld | Observaties en redenen blijven aanwezig; run/exports zichtbaar gedeeltelijk |
| C15 | Huur met maand/jaar en servicekosten | Contractfixture vóór huur activeren; periode/bedrag niet vermengen |
| C16 | Unicode, HTML-entiteiten, lange tekst en spreadsheetformule | Begrensde, correct geëncodeerde data; veilige CSV; bronwaarde ongewijzigd |
| C17 | Lege primaire JSON-LD tegenover positief primair resultaattotaal | Bronconflict/drift; geen EMPTY_CONFIRMED |

C01–C09 bouwen voort op bestaande regressies maar testen de nieuwe uitkomstcontracten. C10–C14 vervangen de interpretatie dat een lege clean-DataFrame voldoende succesbewijs is. De oude library mag compatibel blijven; de service moet de redenen tonen.

## Netwerk, sessie en levensduur

| ID | Testgeval | Verwacht bewijs |
|---|---|---|
| N01 | Twee navigaties binnen één context | Cookiejar/context en gekozen proxyroute worden hergebruikt |
| N02 | Providercredentials fout / HTTP 407 | Configuratiefout, geen targetretry; fout/log/artifact zonder geheim |
| N03 | Uitgang verandert binnen sticky sessie | Context stopt, route-uitval gemeld, hervatten met nieuwe context/run |
| N04 | 503 dan 200; netwerkfout tot exhaustion | Maximaal twee pogingen per URL, backoff en totaalbudget afgedwongen |
| N05 | `Retry-After` als seconden, HTTP-datum, ongeldig, ontbrekend | Geldig beleid gevolgd; fallback zichtbaar; nooit eerder opnieuw sturen |
| N06 | 403/CAPTCHA terwijl andere jobs wachten | Domeincircuit stopt alle nieuwe targetpogingen; beheer-canary vereist |
| N07 | Start, navigatie of renderen loopt vast | Gedeelde deadlines stoppen; browserproces binnen grace beëindigd |
| N08 | Failure na manager/browser/context/page allocatie | Alle al verkregen resources sluiten; herhaald close is veilig |
| N09 | Annulering, leaseverlies, processtop, netwerkpartition | Geen verdere geautoriseerde publicatie; werk hervat vanaf ledger |
| N10 | Consent komt vertraagd; weigeren ontbreekt; consentklik faalt | Alleen bekende weigering; geen automatische acceptatie van tracking; uitkomst verklaard |
| N11 | Browsercrash/OOM/schijf niet schrijfbaar | Begrensde fout, geen infinite retry; diagnostiek bevat geen core/session dump |
| N12 | Meerdere synthetische runs op eigen oorsprong | Geen achtergebleven browserprocessen/FD’s; geheugen binnen vastgestelde hostlimiet |
| N13 | HTTP, DNS, IPv6, WebRTC en subresources via gekozen route | Uitgangstest op eigen endpoint; meetgrenzen en onbekende resultaten expliciet |
| N14 | Cache/resourcebeleid wijzigt bytes of rendering | Zelfde verwachte velden op fixtures; bytes vergelijken; scripts niet blind blokkeren |
| N15 | Requeststorm, streaming/te grote response, download, achtergrondrequests | Per-page/job request-/byte-/concurrencygrenzen en procesafsluiting aantoonbaar |
| N16 | Geheugen/PID/FD-uitputting en oplopende achtergrondactiviteit | OS-grenzen houden host beschikbaar; fout zichtbaar; geen opvolgend targetwerk |

Fake clocks testen timing; gewone tests wachten niet minuten op een cooldown. N13 is noodzakelijk vóór een proxyprovider als route wordt toegelaten. Geen synthetische browserfingerprint wordt per request gewijzigd om een geblokkeerd circuit te omzeilen.

## Taken, tellingen en herstel

| ID | Testgeval | Verwacht bewijs |
|---|---|---|
| J01 | Twee Cron-events voor hetzelfde scope/tijdslot | Eén job door database-unique constraint |
| J02 | Twee runners claimen tegelijk | Eén eigenaar per workitem, monotone fence; echte SQL-concurrencytest |
| J03 | Job-/targetlease vervalt; oude runner komt later terug | Oude collector-heartbeat/discovery/observatie/closure afgewezen; runner heeft geen publicatierechten; actuele publisher mag gesealde snapshot afronden |
| J04 | Crash na recordpersist, vóór checkpoint/ack | Hervatten zonder dubbel logisch record of verloren voortgang |
| J05 | Zelfde observatie tweemaal ingestuurd | Idempotente ontvangst, geen tweede versie door transportretry |
| J06 | Zelfde object als meerdere URL-aliassen of in twee partities | Eén logische observatie met herleidbare aliasresolutie; URL-tellingen blijven sluiten |
| J07 | 404/410/zoekredirect of object ontbreekt in volgende crawl | Alleen waargenomen uitkomst; geen automatische verkocht/verwijderd-status |
| J08 | Budget op laatste toegestane poging, retry, parallelle claim | Geen navigatiestart zonder reservering; retries verbruiken budget |
| J09 | Run afgebroken met nog queued URLs | Tellerinvariant sluit; `BLOCKED/PARTIAL/CANCELLED`, niet `COMPLETE` |
| J10 | Recordvalidatie faalt halverwege responsebatch | Gedefinieerde batchsemantiek; geen cursor vóór duurzame erkenning |
| J11 | Scopewijziging, DST/tijdslot, achterstallige jobs | UTC-slot/dedupsleutel consistent; geen onbeperkte catch-up |
| J12 | Veranderende paginering, overlap en herhaalde laatste pagina | Begrensde ontdekking, overlap gemeld; geen oneindige lus of volledigheidsclaim |
| J13 | Oud resultaat arriveert na nieuwere observatie | Geen terugschrijven van actuele view; waarnemingstijden/versies blijven correct |
| J14 | Restore van metadata en exports naar staging | Historische tellingen, identities, aliases en hashes gelijk; verse recovery-epoch en oude bevoegdheden ongeldig |
| J15 | Discovery-crash vóór/na child-insert/cursor/receipt | Kinderen/checkpoint atomisch; herhalen idempotent; geen complete partition zonder kinderen; ontbrekende/geconsumeerde/verwisselde reservering geweigerd |
| J16 | Twee scopes/jobs claimen hetzelfde target tegelijk | Eén Funda-eigenaar; target-fence/circuit niet per scope te omzeilen |
| J17 | Circuit-open terwijl andere route reserveert; dubbele canary | Lineair verklaarbare race; geen post-open reservering; maximaal één canary |
| J18 | Resume, budgetexhaustion, policywijziging, stale collectie | Cumulatieve budgets en provenance behouden; wijziging geeft nieuwe job; zesuurgrens zichtbaar |
| J19 | Cancel/reclaim/expiry tussen validation en SQL-write | Na verloren guard nul writes; tijdens transactie alles vóór of na de mutatie, geen gemengde toestand |
| J20 | Oud resultaat/alias arriveert later; clientklok springt | Actuele view volgt server attempt_sequence, niet ontvangstmoment of clienttijd |

Unieke URL-toestanden en pogingtellers hebben verschillende noemers. Elke test met fouten controleert beide. De database is het bewijs, niet een losse logregel dat een taak “klaar” was.

## Publicatie en beheer

| ID | Testgeval | Verwacht bewijs |
|---|---|---|
| P01 | Lokale CSV-write/flush/replace faalt | Oude goede export ongewijzigd; tijdelijk bestand niet als latest zichtbaar |
| P02 | R2-upload faalt of één deel ontbreekt | Export niet gepubliceerd; geen onvolledig `LATEST_VERIFIED` |
| P03 | Data-upload klaar, D1-finalisatie faalt | Private orphan opruimbaar; retry publiceert maximaal één manifest |
| P04 | Publisher-leaseverlies tijdens schrijven/finalisatie | Oude publisher kan geen publicatiereferentie veranderen; runner heeft geen upload/finalisatierechten |
| P05 | Gedeeltelijke of verdachte run naast oude geldige export | Oude verified pointer blijft; status toont nieuwe fout en oude actualiteit |
| P06 | Manifest met verkeerd aantal, hash, schema of volgorde | Download/publicatie afgewezen; fout onafhankelijk van interne publisher berekend |
| P07 | CSV bevat =, +, -, @ of meerregelige formule als tekst | Veilige tekstweergave, zonder wijzigingen aan gestructureerde brondata |
| P08 | Goedkope upload gevolgd door accountquota-/providerfout | Afzonderlijke kosten-/storagefout; geen targetretry |
| P09 | Statusrapportage en alarmmelding met gecontroleerde rode run | Juiste reden, teller/noemer, tijd en actie; geen groen alleen op exitcode |
| P10 | Dashboard/API heeft oude verified export maar recente mislukte run | Freshness én failure zichtbaar; geen suggestie dat oude data actueel is |
| P11 | Correct aantal/hash met substitutie van een woning | Serveroutput komt uit immutable observation-membership; afwijking afgewezen |
| P12 | Oudere observatieversie, duplicate in plaats van ontbrekende rij, ander profiel | Exact membership/versie/ordering en profiel nageleefd; golden exportwaarden onafhankelijk vastgesteld |
| P13 | Late observatie tijdens sealing; oude export voltooit later | Geen mutatie na seal; snapshot onveranderd; latest wijst niet terug in tijd |
| P14 | Verloren finalisatiereceipt of een replay na restore | Idempotente publicatie in actuele epoch; oude publisher/request kan niets wijzigen |

Er bestaat geen atomaire transactie over R2 en D1. Tests P02–P04 moeten de gekozen commitvolgorde daadwerkelijk onderbreken, niet alleen een happy-path storage-mock controleren.

## Beveiliging en artefacten

| ID | Testgeval | Verwacht bewijs |
|---|---|---|
| S01 | Geen, vervalste, verlopen of verkeerde-audience Access-identiteit | Afwijzing vóór mutatie; directe workers.dev/preview-ingang niet bruikbaar |
| S02 | Runner doet beheeractie of claimt andere identiteit | Rolbinding afgedwongen; bodyvelden geven geen rechten |
| S03 | Geheime fictieve waarden in config/error/proxy-URL/query/body | Geen terugkeer in API, repr, logs, traces, files, exports of manifests |
| S04 | Persistente browserstate/HAR/HTML/core dump wordt aangezet | Configuratie afgewezen of gecontroleerde beveiligingstest rood |
| S05 | Arbitrary URL, userinfo, port, scheme, redirect naar private host | Afwijzing in productie; geen metadata-, loopback- of link-local-verkeer |
| S06 | Private subresource, DNS-rebinding en proxy-side DNS | Ook browserresources gecontroleerd; onvoldoende providercontrole zichtbaar rood |
| S07 | Te groot request, te veel URLs, SQL/HTML/CSV-injectie | Schemalimieten en prepared statements; geen onveilige interpretatie |
| S08 | Rechtstreekse R2-URL of export van ander scope | Private opslag en objectautorisatie aantoonbaar |
| S09 | Scope- of policywijziging door onbevoegde identiteit | Geen effect; geredigeerd auditevent zonder credentialvelden |
| S10 | Versie-update van browser, driver of image | Artifact-hash klopt; fixtures en hersteltests slagen vóór canary |
| S11 | Private deployment met onveilige route; rebinding/IPv6/WebSocket/popup/service worker | Route blijft uit; beschermde endpointtellers bewijzen nul verbindingen, niet alleen client-error |
| S12 | Geldig scope-A-token tegen alle scope-B claim/write/exportroutes; verwisselde objectIDs | Geen cross-scope bevoegdheid; machine-/mens-/publisherrollen niet uitwisselbaar |
| S13 | Oude runner leeft tijdens restore of rollback van appversie | Oud epoch ongeldig voor heartbeat, reserve, resultaat en publicatie; nieuwe epoch behouden |

Voor S03 gebruiken we herkenbare fictieve waarden, geen echte credentials als testdata. Geen secretwaarde wordt naar een transcript geprint om te bewijzen dat hij bestaat. Een mislukte secretcheck meldt uitsluitend de categorie en het aantal getroffen artefacten.

## Vrijgavecriteria en bewijsstukken

Een release is geen testtelling. De matrix benoemt 80 scenario’s, niet 80 reeds gebouwde of geslaagde tests. Vereiste bewijslijst:

- Alle bestaande library-regressies groen; compatibiliteit aantoonbaar.
- Alle voorgeschreven kern- en foutscenario’s uit deze matrix gekoppeld aan uitvoerbare tests.
- Nul fout geaccepteerde objectidentiteiten, stille drops, dubbele publicaties en onverklaarde URL-tellingen in de gecontroleerde dataset.
- Geen gecontroleerde secretlekkage; autorisatie-, SSRF- en fencingtests groen.
- Eén restore en één echte staging-uitvalproef geslaagd.
- Echte lokale browsertest groen op dezelfde Linux-image/digest als de beoogde runner; macOS-succes is geen Linux-bewijs.
- Voor live activering: afgesproken toestemming/scope/budget, geregistreerd panel, drie afgesproken tijdvensters en verklaarde live-uitkomsten.

Het panel wordt handmatig vastgesteld voordat de resultaten worden bekeken. Een voorgestelde toegangsgate van 95% is hoogstens een productbeslissing; zij bewijst geen landelijke recall. Alle geaccepteerde records moeten op de gecontroleerde identiteits- en prijsbetekenisvelden kloppen. Geblokkeerde panels tellen als mislukte toegangsproef en worden niet uit de noemer verwijderd.

Voor ieder test-ID bewaart het implementatieteam het testpad, de commithash, omgeving, resultaat en beperking in `ops/release-evidence/<release-id>.json` (alleen gesaniteerde metadata). Niet uitgevoerde cloud-, provider- of livegevallen zijn expliciet `NOT_RUN` met reden; nooit groen op basis van een mock.

## Operationele weergave voor één run

```text
Run: <id>    Scope: <regio/markt>    Policy: <versie>
Resultaat: COMPLETE / PARTIAL / BLOCKED / FAILED / CANCELLED
Toegang: pogingen, geldige pagina’s, 403, 429, challenges, netwerkfouten
Verwerking: unieke ontdekt, queued, leased en iedere einduitkomst
Kwaliteit: geldige/incomplete/quarantaine-records en ontbreekredenen
Dekking: benoemde partities afgewerkt; landelijke volledigheid: UNKNOWN
Publicatie: kandidaat / geweigerd / gepubliceerd; manifesthash
Actualiteit: laatste gecontroleerde observatie en export
Kosten: providerbytes gemeten/geschat/onbekend; navigatiebudget over
Actie: niets / handmatig controleren / toegangspilot stoppen / hervatten
```

Dit is het gewenste informatiecontract voor API/CLI. Een uitgebreid dashboard kan later dezelfde gegevens gebruiken; het is geen voorwaarde om de eerste runner veilig en verklaarbaar te testen.
