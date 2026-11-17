import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';
import evidence from '../src/evidence.json' with {type:'json'};
const request = path => worker.fetch(new Request('https://lab.example' + path));
test('health makes the source gate explicit', async () => {
 const r = await request('/health'); assert.equal(r.status, 200);
 const j = await r.json(); assert.equal(j.funda_enabled, false); assert.equal(j.mode, 'synthetic');
});
test('baseline, new and changed scenarios differ', async () => {
 const get = async s => (await request('/zoeken/koop?scenario=' + s)).text();
 const initial = await get('initial'); const next = await get('new');
 assert.ok(!initial.includes('10000002')); assert.ok(next.includes('10000002'));
 assert.ok((await get('changed')).includes('510000'));
});
test('blocking responses and empty listings are explicit', async () => {
 assert.equal((await request('/zoeken/koop?scenario=blocked')).status, 403);
 assert.equal((await request('/zoeken/koop?scenario=rate')).status, 429);
 assert.match(await (await request('/zoeken/koop?scenario=captcha')).text(), /Je bent bijna/);
 assert.match(await (await request('/zoeken/koop?scenario=empty')).text(), /"itemListElement":\[\]/);
});
test('does not implement an arbitrary URL proxy or accept writes', async () => {
 assert.equal((await request('/fetch?url=https://www.funda.nl')).status, 404);
 assert.equal((await worker.fetch(new Request('https://lab.example/', {method:'POST'}))).status, 405);
});
test('detail fixture is labelled synthetic and has no external resources', async () => {
 const r = await request('/detail/koop/lab/huis-teststraat-2/10000002/');
 const html = await r.text(); assert.match(html, /Synthetic/); assert.match(html, /House/);
 assert.doesNotMatch(html, /<(?:img|script)[^>]+src=/);
 assert.ok(r.headers.get('content-security-policy').includes("default-src 'none'"));
});
test('dashboard distinguishes Funda from fixture results', async () => {
 const html = await (await request('/')).text();
 assert.ok(html.includes(evidence.funda.status)); assert.match(html, /Testomgeving/);
});
