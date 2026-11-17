import evidence from './evidence.json' with { type: 'json' };
const canonical = id => `https://www.funda.nl/detail/koop/lab/huis-teststraat-${id}/${10000000 + id}/`;
const ld = value => `<script type="application/ld+json">${JSON.stringify(value)}</script>`;
const headers = {
 'content-type': 'text/html; charset=utf-8',
 'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
 'x-content-type-options': 'nosniff', 'referrer-policy': 'no-referrer',
 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow'
};
const html = (body, status = 200) => new Response(body, {status, headers});
const json = value => new Response(JSON.stringify(value), {headers: {...headers, 'content-type':'application/json'}});
const stamp = evidence.generated_at ? new Intl.DateTimeFormat('nl-NL', {dateStyle:'long',timeStyle:'long',timeZone:'Europe/Amsterdam'}).format(new Date(evidence.generated_at)) : 'nog niet beschikbaar';
const fundaStatus = ['NOT_RUN','PASS','BLOCKED','STOPPED'].includes(evidence.funda.status) ? evidence.funda.status : 'NOT_RUN';
const fundaText = {NOT_RUN:'Er is nog geen actuele Funda-aanvraag uitgevoerd. De ontbrekende routecontroles staan in de meetgegevens.',PASS:'De eenmalige zoekpaginaproef kwam binnen. Er zijn geen detailpagina’s opgehaald en er draait nog geen periodieke woningcontrole.',BLOCKED:'De eenmalige remote proef ontving een blokkade en is gestopt. Er zijn geen automatische herhalingen of detailaanvragen uitgevoerd.',STOPPED:'De proef is afgebroken. De meetgegevens geven de reden en het aantal toegestane verzoeken.'}[fundaStatus];
const page = body => `<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Funda monitor · Testomgeving</title><style>body{font:17px/1.6 system-ui,sans-serif;max-width:960px;margin:50px auto;padding:0 24px;background:#f5f7fa;color:#17243b}h1{font-size:36px;line-height:1.15}h2{font-size:22px;margin:0}section{background:white;border:1px solid #dbe2eb;border-radius:12px;padding:22px;margin:16px 0}small{color:#4e5b6f}strong{font-weight:700}.badge{display:inline-block;background:#e8eef9;color:#233e74;padding:4px 10px;border-radius:6px;font-size:14px}a{color:#234da5}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px 0;border-bottom:1px solid #e4e8ef}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px} @media(max-width:600px){body{margin:24px auto}h1{font-size:28px}td,th{font-size:14px}}</style>${body}</html>`;
export default {
 async fetch(request) {
  const u = new URL(request.url);
  if (request.method !== 'GET' && request.method !== 'HEAD') return html('Method not allowed', 405);
  if (u.pathname === '/health') return json({status:'OK',mode:'synthetic',funda_enabled:false});
  if (u.pathname === '/report.json') return json(evidence);
  if (u.pathname === '/') return html(page(`<main><small>Persoonlijke woningmonitor · fase 1</small><h1>Testomgeving en meetresultaten</h1><p>Deze omgeving test het ophalen en verwerken van fictieve woningen. De Funda-monitor staat uit.</p><section><h2>Funda: <span class="badge">${fundaStatus}</span></h2><p>${fundaText} Deze momentopname geeft geen garantie op toekomstige toegang of bescherming tegen IP-blokkades.</p></section><section><h2>Laatste vastgelegde tests</h2><p>Een momentopname; er draait nog geen periodieke woningcontrole.</p><table><thead><tr><th scope="col">Controle</th><th scope="col">Resultaat</th></tr></thead><tbody><tr><td>Python en browser op eigen testpagina</td><td>${evidence.python.status} · ${evidence.python.passed} tests</td></tr><tr><td>Testpagina’s en HTTP-afhandeling</td><td>${evidence.worker.status} · ${evidence.worker.passed} tests</td></tr><tr><td>Gepubliceerde omgeving</td><td>${evidence.live.status} · ${evidence.live.passed} scenario’s</td></tr><tr><td>Remote browser en netwerkcontroles</td><td>${evidence.remote_route?.status || 'NOT_RUN'}</td></tr></tbody></table><p><small>Vastgelegd: <time datetime="${evidence.generated_at || ''}">${stamp}</time></small></p><a href="/report.json">Bekijk de meetgegevens (JSON)</a></section><section><h2>Wat we testen</h2><p>Nieuwe en gewijzigde items, dubbele vermeldingen, daglimieten na herstart, uitgestelde items en stoppen bij 403, 429 of een CAPTCHA. De testpagina’s bevatten uitsluitend fictieve woningen.</p><a href="/health">Controleer de beschikbaarheid</a></section></main>`));
  if (u.pathname === '/zoeken/koop' || /^\/detail\/koop\/lab\/huis-teststraat-[12]\/1000000[12]\/$/.test(u.pathname)) {
   const scenario = u.searchParams.get('scenario') || 'initial';
   if (!['initial','new','changed','empty','blocked','rate','captcha','unknown','redirect'].includes(scenario)) return html('Unknown scenario',400);
   if (scenario === 'blocked') return html('Synthetic access denied',403);
   if (scenario === 'rate') return html('Synthetic rate limit',429);
   if (scenario === 'captcha') return html('<title>Je bent bijna op de pagina die je zoekt [funda]</title>');
   if (scenario === 'unknown') return html('<title>Synthetic unexpected page</title>');
   if (scenario === 'redirect') return new Response(null,{status:302,headers:{...headers,location:'https://example.invalid/'}});
   const price = scenario === 'changed' ? 510000 : 500000;
   const offers = {price,priceCurrency:'EUR'};
   if (u.pathname === '/zoeken/koop') {
    const ids = scenario === 'empty' ? [] : scenario === 'new' ? [1,1,2] : [1];
    return html('<!doctype html><title>Synthetic search</title>' + ld({'@type':'ItemList',itemListElement:ids.map(id => ({url:canonical(id),name:'Synthetic home',offers}))}));
   }
   const id = u.pathname.includes('10000002') ? 2 : 1;
   return html('<!doctype html><title>Synthetic detail</title>' + ld({'@type':'House',url:canonical(id),address:{streetAddress:`Teststraat ${id}`,addressLocality:'lab'},offers,floorSize:{value:100}}));
  }
  return html('Not found',404);
 }
};
