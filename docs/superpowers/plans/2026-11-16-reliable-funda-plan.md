# Reliable Funda collection implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:executing-plans or, after an explicit choice, superpowers:subagent-driven-development. Execute task-by-task with the checkboxes below. This is a proposal for discussion, not authorization to build or deploy.

**Goal:** een bestuurbare Funda-dienst waarin toegang, datakwaliteit, voortgang en kosten afzonderlijk aantoonbaar zijn en een mislukte run nooit stilzwijgend goed resultaat vervangt.

**Architecture:** één Python-browserrunner haalt begrensde taken via HTTPS bij een Cloudflare Worker op. D1 bewaart het gezaghebbende werkregister; private R2-exports worden server-side uit een vaste observatieselectie gegenereerd en pas zichtbaar na gefencete validatie. Eén netwerkroute per browsercontext; de bestaande library blijft als adapter behouden.

**Tech stack:** Python 3.12 voor de runner; bestaande librarymatrix 3.9–3.13; TypeScript Worker met cf CLI, D1, Access, private R2; JSON Schema-contracten; pytest en Workers-runtime/Vitest-tests. Geen openbaar runner-endpoint nodig.

**Spec:** [ontwerp](../specs/2026-11-16-reliable-funda-design.md). **Testcatalogus:** [matrix](../../quality/2026-11-16-funda-test-matrix.md). **Baseline:** fork/main `96d4e4c`; de 44 bestaande gevallen zijn startbewijs, geen implementatie van dit plan.

## Global constraints

- Start met actieve koop in één afgesproken regio; huur/historie zijn afzonderlijke uitbreidingsgates.
- Nieuwe echte Funda-proeven alleen binnen vastgelegde toestemming, scope en budget. Geen live Funda-tests in gewone CI.
- Eén runner/context/tab voor het target, minimaal vijf seconden tussen top-level pogingen, 0–2 seconden spreiding; dit zijn ontwerpinstellingen, geen bewezen veilige Funda-norm.
- Per logische pilotjob cumulatief maximaal 25 gereserveerde navigatiepogingen en 15 actieve minuten over alle resumes; maximaal twee pogingen per URL, alleen een retry bij tijdelijke netwerk-/5xx-fout.
- Eén pagina krijgt samen maximaal 45 seconden navigatie/renderen; browserstart maximaal 60 seconden. Redirectketens zijn begrensd en afzonderlijk geteld; subresources vallen binnen de paginadeadline.
- D1 is productieautoriteit; geen dubbele onafhankelijke SQLite/D1-writes. SQLite is uitsluitend lokale test-/pilotadapter en geen impliciete productiemigratie.
- Lease 90 seconden, heartbeat 15 seconden; cancelcontrole maximaal elke vijf seconden, met begrensde proces-grace zodat binnen tien seconden geen nieuwe navigatie wordt gestart.
- Geen secretwaarden, cookies, HAR, browserstate of volledige HTML in logs of gewone bestanden; credentials via vault/runtime-injectie. API- en proxycredentialvelden zijn geen jobdata.
- Een geldige observatie wordt vóór exportspecifieke filtering opgeslagen. Alle geweigerde of incomplete records krijgen redenen. Een zoekredirect of ontbrekende advertentie is geen bewijs van verkoop/verwijdering.
- De publicatiepointer verandert alleen na complete, gecontroleerde, actuele gefencete publicatie. Data-objecten zijn private en onveranderlijk.

## Review focus

Deze vijf foutklassen moeten aantoonbaar door de bijbehorende taak worden getest:

1. Funda levert HTTP 200 met challenge of een rijke zoekpagina terug: taak 2 / C01–C09.
2. Opschoning verwijdert alle woningen, terwijl de run groen lijkt: taak 1 / C10–C14 en taak 7 / P05/P09.
3. Leaseverlies of dubbele aflevering schrijft oude/dubbele observaties of exports: taak 4 / J01–J05/J13 en taak 6 / P03–P04.
4. Een blokkade of providerfout veroorzaakt verkeer/betalingen buiten de grenzen: taak 3 / N02–N07 en taak 5 / J08–J09.
5. SDK-errors, redirects of browserresources lekken secrets of bereiken private hosts: taak 3 / N13 en taak 4 / S01–S07.

## Interfacecontracten

Definieer deze publieke namen in taak 1; latere taken gebruiken dezelfde namen. Schema’s zijn versie 1 en krijgen gedeelde voorbeelden in `contracts/examples/`.

- `ScopePolicy`: scope-ID, markt/regio, veldprofiel, toegestane routes, route-ID, policyversie en limieten.
- `ClassifiedPage`: `kind`, requested/canonical URL, identity-key, gestructureerde `source_fields`, optionele `SearchPageResult` en reason-code. HTML blijft een tijdelijk inputargument en wordt geen serialiseerbaar veld.
- `ObservationDecision`: `state` (`VALID/INCOMPLETE/QUARANTINED`), toegestane velden met herkomst/ontbreekreden, bronidentiteit en versies.
- `AttemptResult`: `attempt_id`, `work_item_id`, uitkomst, geredigeerde metadata, eventuele `ObservationDecision`; geen headers, HTML of vrij providerantwoord.
- `SearchPageResult`: partition-ID, page/cursor, primaire genormaliseerde links, primair totaal of UNKNOWN, volgende cursor, bronconflict/termination-code en publieke-lijstsignature.
- `DiscoverySubmission`: workitem-ID, attempt/reservation-ID en sequence, actuele owner/scope/job/run/epoch/target-/jobfences, idempotency key en SearchPageResult. Alleen een bij deze search/cursor passende ongebruikte reservering kan geaccepteerd worden.
- `WorkItem`: server-owned ID, `SEARCH_PAGE/PROPERTY`, gecontroleerde URL, partition/cursor en scope-/policyversie.
- `Reservation`: attempt-ID, monotone server-issued `attempt_sequence`, workitem, actuele lease-identiteit en deadline.
- `Lease`: `job_id`, `run_id`, `owner`, recovery-epoch, target-fence, job-fence, server-expiry en resterend cumulatief budget. Fence/IDs zijn consistentiemetadata, geen bearerrechten.
- `Receipt`: `accepted`, `duplicate`, `server_version`; alleen ontvangst na duurzame erkenning staat cursorvoortgang toe.
- `RunManifest`: scope/versies/tijden, gesloten URL-tellingen, object- en veldkwaliteit, benoemde ontdekkingspartities, kostenstatus en exportdelen/hashes.

Alle API-routes vereisen afzonderlijke authenticatie. Producer en consumer valideren beide. Resultaatbatches bevatten maximaal 50 observaties én maximaal 1 MiB encoded JSON; de producer splitst op de eerste bereikte grens. Exportdelen maximaal 8 MiB. Deze limieten zijn pilotkeuzes die op eigen fixtures worden getoetst.

## Taak 1: uitkomsten en normalisatie zonder stille wegval

**Bestanden:** nieuw `contracts/collector-v1.schema.json`, `contracts/examples/`, `funda_collector/contracts.py`, `funda_collector/normalize.py`, `tests/collector/test_contracts.py`, `tests/collector/test_normalize.py`; wijzig package-discovery in `pyproject.toml` zodat `funda_collector*` wordt opgenomen.

**Produceert:** `normalize(page: ClassifiedPage, policy: ScopePolicy) -> ObservationDecision` en de bovenstaande contracten. JSON Schema is de bron voor uitwisseling; geen onbedoelde serialisatie van runtimecredentials.

- [ ] Schrijf eerst tests voor C10–C16 en J10 met handmatig vastgestelde waarden. Bijvoorbeeld:

```python
def test_missing_area_is_retained_with_reason(page_without_area, buy_policy):
    result = normalize(page_without_area, buy_policy)
    assert result.state == "INCOMPLETE"
    assert result.fields["living_area"].missing_reason == "NOT_ON_PAGE"
    assert result.identity_key == "koop/amsterdam/huis-teststraat-1"
```

- [ ] Run `python -m pytest tests/collector/test_contracts.py tests/collector/test_normalize.py -q`; bevestig falen door ontbrekend gewenst gedrag.
- [ ] Implementeer contractvalidatie en normalisatie. `ON_REQUEST` heeft geen numeriek bedrag; nul/missend/ongeldig zijn verschillende uitkomsten. Derived querywaarden worden niet als paginabron gemarkeerd. Bewaar alle identificeerbare bronobservaties en veldredenen.
- [ ] Test dezelfde geldige en ongeldige contractvoorbeelden later ook in TypeScript; geef nu vereiste payloads, grootte- en versiegrenzen mee.
- [ ] Run de gerichte en volledige bestaande Python-suite; commit de beperkte contract-/normalisatiewijziging.

**Gereed wanneer:** geen synthetisch record verdwijnt alleen door een kwaliteitsfilter; prijsbetekenis en ontbreekreden zijn controleerbaar. Huurfixture C15 blijft een activeringsgate zolang huur niet wordt ondersteund.

## Taak 2: documentherkenning en objectidentiteit als servicecontract

**Bestanden:** nieuw `funda_collector/classify.py`, `tests/collector/test_classify.py`, `tests/fixtures/collector/`; wijzig de extractor alleen waar een herbruikbaar publiek broncontract nodig is, met behoud van oude API.

**Consumeert:** taak 1. **Produceert:** `classify(html: str, requested_url: str, expected_kind: str) -> ClassifiedPage`.

- [ ] Schrijf C01–C09 en C17: CAPTCHA200, 403/ratecategorie, rijke zoekredirect, onbekende DOM, geldige empty versus aanbeveling, ID-alias en ander unit/adres. Bijvoorbeeld:

```python
def test_rich_search_is_not_a_property(rich_search_html):
    page = classify(rich_search_html, EXPECTED_PROPERTY_URL, "detail")
    assert page.kind == "SEARCH_REDIRECT"
    assert page.source_fields == {}
```

- [ ] Run `python -m pytest tests/collector/test_classify.py -q` en observeer de bedoelde failures.
- [ ] Implementeer de adapter op bestaande parsing. Canonical-search is geen woning; expliciete canonical alias alleen voor dezelfde volledige route-identiteit. Onvolledige DOM en sourceconflicten blijven verklaarbaar onbekend/quarantaine.
- [ ] Voeg een lege primaire lijst tegenover een positief primair resultaattotaal toe: bronconflict/drift, geen zero-success. Aanbevelingen buiten de primaire resultaten zijn iets anders.
- [ ] Run gericht plus alle library-regressies. Commit met cases en bronvormen; fixtures blijven synthetisch en bevatten geen echte sessiedata.

**Gereed wanneer:** een verkeerd huis kan niet worden geaccepteerd doordat een canonical of een genest House-object op het eerste gezicht geldig lijkt.

## Taak 3: netwerkroute, sessie, beleid en procesgrenzen

**Bestanden:** nieuw `funda_collector/network.py`, `session.py`, `policy.py`, `tests/collector/test_network.py`, `test_policy.py`, `test_session.py`, `test_egress.py`, `funda_collector/egress.py`, `ops/runner-image/`, `ops/egress-policy.toml`; wijzig `funda_scraper/transport.py` met optionele compatibele route-injectie en gedeelde deadlines.

**Produceert:** `make_transport(route, policy, secret_resolver)`, `decide(outcome, budget, now) -> Action` en een sessieadapter met begrensde `close`. Routeconfig is serialiseerbaar zonder credentialwaarden; geheime runtimeobjecten niet.

- [ ] Schrijf N01–N16, S03–S06/S10/S11 eerst tegen eigen endpoints/fake klok. Test maximaal twee pogingen, correct `Retry-After`, geen herhaling bij 407/403/CAPTCHA, contextbinding, fout bij allocatiestap en stop bij veranderde uitgang. Bijvoorbeeld:

```python
def test_captcha_does_not_request_a_new_route(policy, budget, clock):
    action = decide(Outcome("BLOCKED"), budget, clock.now())
    assert action.kind == "OPEN_TARGET_CIRCUIT"
    assert action.retry_at is None
```

- [ ] Run `python -m pytest tests/collector/test_policy.py tests/collector/test_network.py tests/collector/test_session.py -q`; verifieer de failures.
- [ ] Implementeer de geharde netwerkadapter en de supervisorgrenzen. De service schakelt verborgen `RequestsTransport`-retries uit (`retries=0`): elke echte nieuwe poging wordt door de collector gereserveerd en geteld. Geen dubbele retrylagen.
- [ ] Implementeer geïsoleerde Linux-jobnetwerken plus een gecontroleerde CONNECT/egress-forwarder met strikte host- en publieke-IP-binding. De browser heeft geen directe bypass. Maak pagina/job-request-, byte-, concurrency-, download-, geheugen-, PID- en FD-grenzen uit de spec afdwingbaar. Provider-/wiremeetgrenzen blijven apart. Een niet aantoonbaar veilige route blijft uitgeschakeld, ook privé.
- [ ] Laat iedere context één route/providersessie gebruiken. Secrets worden vlak vóór consumptie geïnjecteerd via de bestaande vault/pipe-regel; `repr`, foutbericht, tracing en serialisatie zijn allowlisted. Geen secretwaarden in CLI-argumenten of `.env`.
- [ ] Draai een echte lokale browserproef met vertraagde DOM, consent, HTTPS, redirects en procesuitval. Test de uitgekozen proxy later op een eigen endpoint; markeer die providerproef `NOT_RUN` totdat er een gekozen route is.
- [ ] Run alle Python-tests en commit. Geen nieuwe Funda-aanvragen als onderdeel van deze stap.

**Gereed wanneer:** softwaredeadlines, cleanup en attempt-budget aantoonbaar gelden; ongeteste route- of private-destination-beveiliging blijft een rode gate.

## Taak 4: Cloudflare-regelpunt met authentieke, idempotente opslag

**Bestanden:** nieuw `control/package.json`, lockfile, `cloudflare.config.ts`, `src/auth.ts`, `src/jobs.ts`, `src/observations.ts`, `src/discovery.ts`, `src/targets.ts`, `src/ledger.ts`, `src/index.ts`, `migrations/0001_collection.sql`, `migrations/0002_sealing_and_membership.sql`, `tests/auth.test.ts`, `jobs.test.ts`, `observations.test.ts`, `discovery.test.ts`, `races.test.ts`, `contracts.test.ts`.

**API:** beheer `POST /v1/jobs`, `GET /v1/runs/:id`, `POST /v1/runs/:id/cancel`, `POST /v1/targets/funda/request-canary` en `/resume`; machine `POST /v1/leases/claim`, `POST /v1/leases/:job_id/heartbeat`, `POST /v1/work/next`, `POST /v1/attempts/reserve`, `POST /v1/discovery-pages`, `POST /v1/observations`, `POST /v1/collections/:job_id/close`. Rolbinding bepaalt beschikbare routes.

- [ ] Schrijf J01–J06/J10/J11/J13/J15–J20, S01/S02/S07/S09/S12/S13 en de schema-voorbeelden uit taak 1 vóór implementatie. Bijvoorbeeld:

```typescript
it("weigert een resultaat met een verlopen fence", async () => {
  const response = await submitResultWithExpiredFence();
  expect(response.status).toBe(409);
  expect(await storedObservationCount()).toBe(0);
});
```

- [ ] Run `npm --prefix control run test:unit` en `test:integration`; verwacht de vastgelegde failures. Gebruik Workers-runtime met D1/R2-bindingen, niet een map-mock als SQL-bewijs. Testhelpers in `control/tests/support/` maken echte lokale toestand en fixtures aan.
- [ ] Implementeer rollen, audience/signaturevalidatie, begrensde input en gebonden SQL-parameters. Schakel prod-bypass via workers.dev/previews uit. De rol×scope×route-matrix uit de spec wordt server-side afgedwongen, inclusief vaste issuer/audience/JWKS/exp/nbf-controle. Een geclaimde worker-ID is gekoppeld aan de geverifieerde machine-identiteit, niet aan body/headerclaims van de client.
- [ ] Leg unieke jobs, idempotency keys en observaties vast met databaseconstraints. Claim en target-/jobfenceverhoging gebeuren in één atomaire mutatie. Het Funda-brede target-slot en circuit gelden over alle scopes/routes. Canary geeft exact één reservering vrij; gewone jobs blijven geblokkeerd. Elke ontvangen batch van maximaal 50 items wordt vooraf volledig op schema gecontroleerd; schemafout geeft 422 zonder writes. Daarna worden items idempotent verwerkt en retourneert de API receipts per item; een verloren response mag veilig opnieuw worden ingestuurd.
- [ ] Implementeer discovery als gefencete idempotente transactie op DiscoverySubmission; controleer workitem/attempt/sequence/partition/cursor tegen dezelfde serverreservering. Test ontbrekende, al gebruikte of verwisselde reserveringen. Vervolgens: primaire URLs toevoegen, partitionstatus/cursor bijwerken en receipt vastleggen als één operatie. Een partition is nooit complete vóór zijn child-workitems bestaan. Work/next komt alleen uit deze ledger.
- [ ] Een observatie mag alleen schrijven bij actuele epoch/target- en jobfence, scope, owner, expiry, jobtoestand en geldige reservering, gecontroleerd binnen dezelfde conditionele D1-mutatie/transactie als de writes. Geen voorafgaande losse auth-read met later onvoorwaardelijk schrijven. Meng geen IDs uit verschillende runs.
- [ ] Reserve geeft een monotone attempt_sequence. Actuele views volgen deze ordering; clientklok/responsevolgorde geeft geen recencyrechten. Aliasmerge rekent de actuele view opnieuw op dezelfde volgorde uit. Circuit-open blokkeert reserveringen, maar de terminale blokkade-uitkomst en gecontroleerde release moeten binnen een expliciet toegestane state-transition kunnen worden vastgelegd.
- [ ] Leg de jobgrens vast: scope/policy/budget bevroren per logische job; resume behoudt observations/ledger/verbruik; ouder dan zes uur wordt partial/expired. Policywijziging geeft een nieuwe job. Sealing sluit late mutaties uit en maakt vaste export-membership.
- [ ] Een observatie mag alleen schrijven bij actuele fence en voldoende geldige reservering. Checkpoint pas na receipt. Bewaar canonieke aliases, veldredenen en geversioneerde uitkomsten. Finalisatie van een run sluit latere mutaties uit.
- [ ] Run unit/integratie/typecheck/build; test de gedeelde contractvoorbeelden aan beide kanten. Commit. Werkende lokale emulatie is nog geen bewijs van Access in staging.

**Gereed wanneer:** twee gelijktijdige claims en een terugkerende oude runner geen gedeelde eigenaar, dubbele observatie of teruggeschreven actuele view veroorzaken.

## Taak 5: pullrunner en herstel zonder verloren of dubbel werk

**Bestanden:** nieuw `funda_collector/client.py`, `runner.py`, `tests/collector/test_client.py`, `test_runner.py`, `ops/runner-example.toml` zonder secrets, service-entrypoint in `pyproject.toml`.

**Consumeert:** taak 1–4. **Produceert:** `RunnerClient.claim() -> Lease | None`, `next_work(lease) -> WorkItem | None`, `heartbeat(lease) -> LeaseStatus`, `reserve(lease, work_item_id) -> Reservation`, `submit_discovery(lease, submission: DiscoverySubmission) -> Receipt`, `submit(lease, result, idempotency_key) -> Receipt`, `close_collection(lease) -> CollectionReceipt`; plus `run_job(lease, client, session_factory)`.

- [ ] Schrijf J04/J05/J07–J13/J15–J20 en N07–N12. Test crash na persist vóór ack, ontbrekende reservering, cancel, nieuwere observatie, gemiste heartbeat en canonieke duplicaten. Bijvoorbeeld:

```python
def test_crash_after_acceptance_is_idempotent(resume_scenario):
    outcome = resume_scenario.crash_after_persist_then_resume()
    assert outcome.logical_observations == 1
    assert outcome.unexplained_urls == 0
```

- [ ] Run `python -m pytest tests/collector/test_client.py tests/collector/test_runner.py -q` en verifieer de failures.
- [ ] Implementeer een supervisor die heartbeat/cancelcontrole uitvoert terwijl een apart browserjobproces werkt. Browserhang kan de control-loop niet blokkeren. Control- en workerthreads/processen delen geen onveilige requests.Session; hun clients en geheime runtime-injectie hebben een expliciete levensduur.
- [ ] Reserveer vóór iedere top-level navigatiepoging. Teller inclusief retry, geen terugbetaling na mogelijk verzonden verkeer. Voor redirects geldt een maximale keten van vijf hops; echte request/subresourcebytes worden apart gemeten.
- [ ] Verwerk zowel SEARCH_PAGE als PROPERTY via work/next. Discovery-receipt komt pas na child+cursor-commit; crash/replay kan geen URLs verliezen of verdubbelen. Een None workitem is niet automatisch een complete collectie: de server beoordeelt partitions en totale ledger.
- [ ] Stuur alleen gestructureerde bron-/uitkomstdata terug. Bewaar cursor na duurzame receipts. Gebruik servertijd voor leasebesluiten en monotone lokale timers met veiligheidsmarge; test een springende systeemklok.
- [ ] Laat een geblokkeerd target alle andere targetjobs pauzeren. Heropenen vereist de beheersroute en één begrensde canary; een providerroutewissel is geen impliciete reset.
- [ ] Run alle tests, inclusief echt lokaal crash/resume, en commit.

**Gereed wanneer:** een job verklaarbaar herstart, nooit verder navigeert zonder geldig budget/lease, en geen verdwenen advertentie als verkocht markeert.

## Taak 6: atomische export en gefencete zichtbaarheid

**Bestanden:** nieuw `funda_collector/export.py`, `control/src/publication.ts`, migratie `0003_publication.sql`, `tests/collector/test_export.py`, `control/tests/publication.test.ts`.

**API:** alleen geautoriseerde readers gebruiken `GET /v1/scopes/:id/latest` en `GET /v1/exports/:id`. De service seal/finalisatie uit taak 4 maakt een exportkandidaat. Alleen de interne Worker-publisher schrijft delen en finaliseert; er is geen runner-CSV-uploadroute. Een aparte exportlease/fence+epoch beschermt de publisher nadat de browserlease is vrijgegeven; dit is geen afhankelijkheid van een nog levende runner. Sealing/membership zijn reeds in taak 4 aanwezig; deze taak voegt R2-publicatiemetadata toe.

- [ ] Schrijf P01–P08/P11–P14, S08 en J03/J19 vóór implementatie. Bijvoorbeeld:

```python
def test_failed_replace_preserves_old_export(export_fault):
    export_fault.fail_on_replace()
    assert export_fault.latest_bytes() == b"previous verified export"
    assert export_fault.published_new_manifest() is False
```

- [ ] Run `python -m pytest tests/collector/test_export.py -q` en `npm --prefix control run test:integration` met de bedoelde failures.
- [ ] Maak export_membership server-side tijdens sealing met observatie-ID/versie, veldprofiel, vaste ordering en selectiedigest. Genereer CSV/JSON vanuit die vaste records, nooit vanuit door de runner aangeleverde exportbytes. Test juiste hash/telling met verwisselde/gedupliceerde/verouderde rijen.
- [ ] Implementeer immutable exportdelen met maximaal 8 MiB, digest en rijtellingen. De Worker berekent/verifieert hashes, rijen en publicatieregels tegenover de immutable membership; hij vertrouwt geen clientmelding “valid”.
- [ ] Laat de interne publisher private delen schrijven, valideer manifest, finaliseer conditioneel met eigen publicatiefence+epoch in D1 en maak pas daarna de API-referentie zichtbaar. Idempotente finalisatie; late/stale publicatie kan geen pointer aanpassen. Orphans worden na gecontroleerde bewaartermijn opgeruimd.
- [ ] Koppel publicatieregels aan echte URL- en kwaliteitsnoemers. `PARTIAL/BLOCKED` vervangt nooit `LATEST_VERIFIED`; optioneel partial-resultaat blijft expliciet gelabeld. Maak CSV-cellen veilig zonder brondata te muteren.
- [ ] Run fouten op iedere grens, herstel dezelfde publicatie opnieuw, run suite en commit.

**Gereed wanneer:** disk-full, D1-/R2-uitval, verdwenen R2-schrijfreceipt van de interne publisher en oude runners geen halve of dubbele goede export opleveren.

## Taak 7: meetbare gezondheid en operationele bediening

**Bestanden:** nieuw `control/src/status.ts`, `control/src/alerts.ts`, `control/tests/status.test.ts`, `tests/collector/test_accounting.py`, `ops/runbooks.md`, `ops/release-evidence/schema.json`.

**Produceert:** statuspayload uit de testmatrix, redacted events en een releaserapport. Beheerders krijgen een status-API en een eenvoudige leesbare CLI; een uitgebreid dashboard is optioneel.

- [ ] Schrijf J08/J09/J12, P05/P09/P10 en S03. Bijvoorbeeld:

```python
def test_blocked_run_never_looks_complete(accounting):
    report = accounting.with_blocked_and_queued_urls()
    assert report.status == "BLOCKED"
    assert report.discovered == sum(report.url_state_counts.values())
    assert report.latest_verified_is_new_run is False
```

- [ ] Run gerichte tests en verifieer falen op onverklaarde tellers, valse freshness en foutieve groene status.
- [ ] Implementeer toegang/verwerking/kwaliteit/dekking/kosten afzonderlijk. Processing ratio gebruikt ontdekte URLs; nationwide discovery recall blijft UNKNOWN zolang geen externe referentie bestaat. Providerbytes zijn gemeten/geschat/onbekend; onbekend is geen nul.
- [ ] Maak overdue-, heartbeat-, circuit-, drift-, budget- en publicatiealarm. Geen automatische berichten naar teamkanalen; het eerste doel is een gecontroleerd status-/alarmrecord en een geautoriseerde statusweergave.
- [ ] Runbooks beschrijven: pause, cancel, één canary, resume, credentialrotatie zonder waardelogging, browserrollback, orphancleanup en restore. Alarm- en stopcriteria zijn mechanisch gekoppeld aan de uitkomstcodes.
- [ ] Run suite; commit. Het releaserapport noemt NOT_RUN voor ontbrekende provider/staging/liveproeven.

**Gereed wanneer:** iemand zonder toegang tot paginabodies kan zien wat goed ging, wat faalde, hoeveel er ontbreekt en welke actie volgt.

## Taak 8: release-, herstel- en toegangsgates

**Bestanden:** nieuw `tests/system/`, `control/tests/system/`, `ops/browser-lock.json`, `ops/release-evidence/<release-id>.json`; wijzig `.github/workflows/tests.yml` en voeg een gecontroleerde staging-workflow toe.

- [ ] Voeg eerst uitvoerbare foutscenario’s toe voor J14/J15–J20, P02–P04/P11–P14 en S01–S13, plus de complete matrixkoppeling. Bewijs dat restore van één gekozen checkpoint dezelfde historische recordset, aliases, tellers en manifesthashes teruggeeft, terwijl alle oude leases/reserveringen/publisherfences ongeldig zijn. Start gepauzeerd, verhoog een recovery-epoch buiten de snapshot en test een nog levende oude runner; rollback moet de nieuwe epoch bewaren.
- [ ] Run op eigen oorsprong 1.000 synthetische URLs met lege/rijke/kapotte pagina’s, duplicaten en ingeplande fouten. Pacing mag alleen in deze gesloten testomgeving een fake clock gebruiken. Verifieer nul stille drops, nul verkeerde identiteiten en idempotente publicatie; dit is geen Funda-loadtest.
- [ ] CI: bestaande librarymatrix 3.9–3.13; collector/security/contracts op 3.12; Worker typecheck en lokale D1/R2; echte Linux-browserfixture op de gepinde image; package/install-smoke. Browser-/dependencyupdates komen via aparte gecontroleerde PR.
- [ ] Staging: echte Access-verificatie, directe worker-/preview-bypass, private R2, quotas, uploadonderbreking, runnerkill en D1-/netwerkstoring testen. Geen nieuwe betaalde resources of deploy zonder de daarvoor afgesproken uitvoering.
- [ ] Registreer elke matrixregel als PASS/FAIL/NOT_RUN met artifact, commithash en beperking. Een mock maakt een cloud-/provider-/livecheck niet groen.
- [ ] Na scope/toestemming/netwerkkeuze: maximaal twintig panelobjecten plus twee zoekpagina’s per run; drie vooraf vastgelegde vensters op verschillende dagen. Onmiddellijk stoppen bij blokkade volgens circuitbeleid. Meet de voorgestelde 95%-toegangsgate zonder foutcases uit de noemer weg te poetsen; identiteit/prijsbetekenis moet voor geaccepteerde records kloppen.
- [ ] Besluit vóór productie: single-region actief koop groen; vervolgens apart huurcontract, extra regio’s en discovery/reconciliatie. Geen automatische landelijke opschaling op basis van één goed venster.
- [ ] Leg aantoonbare grenzen en restpunten vast; commit bewijs zonder geheimen. Opschalen is een apart besluit, geen standaardactie van een geslaagde test.

**Gereed wanneer:** alle relevante voorgeschreven scenario’s groen zijn, niet-geteste claims zichtbaar blijven en iemand een herstelproef zelfstandig via het runbook kan uitvoeren.

## Voorgestelde uitvoeringsvolgorde

Eerst taak 1–3: broncorrectheid en beheersbaar netwerk op eigen testinfrastructuur. Daarna taak 4–5: duurzame opdrachten en hervatten. Daarna taak 6–7: betrouwbare publicatie en inzicht. Taak 8 sluit iedere fase af met passende bewijsgates; een beperkte toegangspilot kan na lokale/staging-basiscontrole, vóór verdere landelijke functionaliteit.

Indicatieve inspanning, geen offerte: circa 2–4 ontwikkelwerkdagen voor taak 1–3, 2–4 voor taak 4–5, 2–3 voor taak 6–7 en 1–2 voor eerste staging/herstelwerk. De toegangspilot vraagt daarnaast meerdere kalenderdagen; providerkeuze, bronwijzigingen en toestemming kunnen de duur bepalen. Scherp de schatting aan na taak 1 en de eerste Linux-browserproef. Eerst een klein betrouwbaar systeem, daarna volume.

## Review en gesprek

De inhoudelijke bespreking moet vooral datasetdoel, toestemming, host, budget, velden, actualiteit en alarmverantwoordelijke vastleggen. Het voorstel kiest een pullmodel, één bron van waarheid en gefencete publicatie als technische standaard. Implementatie start pas na ons gesprek; er is in deze planfase geen nieuwe productcode of cloudinfrastructuur aangebracht.
