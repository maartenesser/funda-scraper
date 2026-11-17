# Controleverslag van het ontwerpvoorstel

Datum: 16 november 2026. Status: bespreekbaar voorstel, niet geïmplementeerd of gedeployed.

## Bestaand bewijs

De planning is gebaseerd op fork/main `96d4e4c`. De bestaande code is in een aparte worktree opnieuw gecontroleerd met pytest en de opt-in echte browserintegratie tegen een eigen lokale server. Resultaat: **44 passed in 13.24s**. Er zijn in deze planfase geen nieuwe Funda-aanvragen gedaan en geen betaalde proxy/cloudresources aangemaakt.

Deze testuitslag betreft de bestaande scraper. Zij bewijst niet dat het nieuwe jobregister, de proxylaag, cloud-autorisatie of publicatieflow al bestaat. De nieuwe matrix heeft **80 voorgestelde scenario’s**; de implementatie moet daarvoor nog uitvoerbaar testbewijs leveren.

## Onafhankelijke beoordeling en wijzigingen

Een builder/architectuurreview en een afzonderlijke securityreview beoordeelden de specificatie, het bouwplan en de testmatrix. De belangrijkste gevonden gaten zijn verwerkt:

| Gevonden risico | Vastgelegde oplossing |
|---|---|
| Discovery had geen duurzaam protocol | SearchPageResult/DiscoverySubmission, work-next en atomische child-URLs plus cursor/receipt |
| Lease per job voorkwam geen overlap tussen scopes | Funda-brede targetlease/fence/circuit en één canary-permit |
| Goede exporthash met verkeerde records bleef mogelijk | Server-side immutable observation-membership en interne exportgeneratie |
| Oude responses/clientklok konden actuele data terugdraaien | Server-issued attempt_sequence en dezelfde ordering bij aliases |
| Resume kon budget/policy/snapshot mengen | Eén bevroren logische job, cumulatief verbruik, expliciete sealing en zesuurgrens |
| Privé service was een mogelijke uitzondering op SSRF-eisen | Onveilige netwerkroute blijft uit, ook privé; egressisolatie en beschermde-endpointtests |
| Tijd/navigatiebudget begrensde niet alle resources | Page/job request-/byte-/concurrencylimieten en OS-limieten |
| Leasecontrole en mutatie konden uit elkaar vallen | Dezelfde atomische conditionele guard/writes plus interleavingtests |
| Restore kon oude bevoegdheden herstellen | Gepauzeerde restore met verse externe recovery-epoch en ingetrokken leases |
| Rollen waren niet per scope/handeling scherp | Principal×scope×route-matrix, vaste identityconfig en cross-scope tests |

De herbeoordeling vond geen resterende architectuurblocker en geen resterende High/Medium securitybevinding in de voorgestelde grenzen. Daarna zijn de genoemde consistentiepunten gecorrigeerd: publisher heeft eigen lease; sealing-schema ontstaat vóór publicatiecode; runner mag geautoriseerd collection-close doen; discovery is aan een specifieke reservering gebonden. Dit is documentreview, geen goedkeuring van nog niet gebouwde software.

## Wat nog moet worden bewezen

- De gekozen Linux/browser/egress-combinatie werkt en beschermt netwerk en secrets op eigen testendpoints.
- Cloudflare-auth, D1-mutaties, R2-publicatie en restore functioneren in echte staging.
- Een gekozen uitgang geeft binnen de toegestane scope herhaalbare Funda-toegang.
- Data- en discoverykwaliteit voldoen aan het afgesproken panel en later aan afzonderlijke regionale/landelijke controles.
- Middelen- en providerkosten zijn gemeten; projectlimieten zijn niet hetzelfde als een extern gegarandeerd factuurplafond.

Planbestanden: [ontwerp](../superpowers/specs/2026-11-16-reliable-funda-design.md), [bouwplan](../superpowers/plans/2026-11-16-reliable-funda-plan.md), [testmatrix](2026-11-16-funda-test-matrix.md). Bespreking moet scope, host, budget, rechten, frequentie, velden en operationele eigenaar vastleggen vóór uitvoering.
