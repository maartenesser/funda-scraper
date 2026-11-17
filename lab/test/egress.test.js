import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/egress.js';
const env = {TRIAL:'00000000-0000-4000-8000-000000000001',EXPIRES_AT:'2099-01-01T00:00:00Z'};
const call = (path,headers={},extra={}) => worker.fetch(new Request('https://observer.example'+path,{headers}),{...env,...extra});
test('expired or wrong trial does not touch storage',async()=>{
 assert.equal((await call('/identity?trial=wrong')).status,404);
 assert.equal((await call('/identity?trial='+env.TRIAL,{}, {EXPIRES_AT:'2000-01-01T00:00:00Z'})).status,410);
});
test('identity returns a salted digest, never the source IP',async()=>{
 const r = await call('/identity?trial='+env.TRIAL,{'cf-connecting-ip':'192.0.2.1'});
 const text=await r.text();assert.ok(!text.includes('192.0.2.1'));
 const d=JSON.parse(text);assert.equal(d.source_hash.length,64);assert.equal(d.cloudflare_egress,false);
});
test('missing source identity fails closed',async()=>{
 assert.equal((await call('/identity?trial='+env.TRIAL)).status,503);
});
test('rejects unbounded counter buckets and writes',async()=>{
 assert.equal((await call('/observe?trial='+env.TRIAL+'&bucket=arbitrary')).status,400);
 assert.equal((await worker.fetch(new Request('https://observer.example/',{method:'POST'}),env)).status,405);
 assert.equal((await call('/fetch?url=https://www.funda.nl')).status,404);
});
test('counter stores only bounded bucket and remote boolean',async()=>{
 let captured;
 const DB={prepare:()=>({bind:(...args)=>({run:async()=>{captured=args;}})})};
 const r=await call('/observe?trial='+env.TRIAL+'&bucket=allowed',{'cf-connecting-ip':'192.0.2.9'},{DB});
 assert.equal(r.status,200);assert.deepEqual(captured,[env.TRIAL,'allowed',0]);
});
