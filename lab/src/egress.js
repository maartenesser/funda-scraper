// Owned, bounded network observer. Never forwards a request or stores IPs/headers.
const baseHeaders = {'cache-control':'no-store','content-type':'application/json',
 'content-security-policy':"default-src 'none'; frame-ancestors 'none'",'x-content-type-options':'nosniff'};
const reply=(body,status=200,extra={})=>new Response(JSON.stringify(body),{status,headers:{...baseHeaders,...extra}});
const buckets=['allowed','forbidden','subresource','worker','script','redirect','worker-control'];
export default {
 async fetch(request,env) {
  if (request.method!=='GET') return reply({error:'METHOD_NOT_ALLOWED'},405);
  const u=new URL(request.url);
  const routes=['/identity','/observe','/counts','/redirect','/script-check','/probe-page','/redirect-self'];
  if (!routes.includes(u.pathname) || !env.TRIAL || u.searchParams.get('trial')!==env.TRIAL) return reply({error:'NOT_FOUND'},404);
  const expires=Date.parse(env.EXPIRES_AT);
  if (!Number.isFinite(expires) || Date.now()>expires) return reply({error:'TRIAL_EXPIRED'},410);
  if (u.pathname==='/redirect-self') return new Response(null,{status:302,headers:{...baseHeaders,location:`https://funda-egress-observer.maartenjr-esser.workers.dev/observe?trial=${env.TRIAL}&bucket=redirect`}});
  if (u.pathname==='/redirect') return new Response(null,{status:302,headers:{...baseHeaders,location:`https://funda-egress-denied.maartenjr-esser.workers.dev/observe?trial=${env.TRIAL}&bucket=forbidden`}});
  if (u.pathname==='/probe-page') return new Response('<!doctype html><body>Owned guardrail probe</body>',{headers:{...baseHeaders,'content-type':'text/html','content-security-policy':"default-src 'none'; img-src https://funda-egress-denied.maartenjr-esser.workers.dev; worker-src blob:; script-src 'unsafe-eval'; connect-src https://funda-egress-denied.maartenjr-esser.workers.dev https://funda-egress-observer.maartenjr-esser.workers.dev; frame-ancestors 'none'"}});
  if (u.pathname==='/script-check') return new Response('<!doctype html><body data-executed="no"><script>document.body.dataset.executed="yes"</script></body>',{headers:{...baseHeaders,'content-type':'text/html','content-security-policy':"default-src 'none'; script-src 'unsafe-inline'; frame-ancestors 'none'"}});
  if (u.pathname==='/counts') {
   const {results}=await env.DB.prepare('SELECT bucket,total,remote FROM observations WHERE trial=? ORDER BY bucket').bind(env.TRIAL).all();
   return reply({counts:results});
  }
  const bucket=u.searchParams.get('bucket');
  if (u.pathname==='/observe' && !buckets.includes(bucket)) return reply({error:'UNKNOWN_BUCKET'},400);
  const ip=request.headers.get('cf-connecting-ip');
  if (!ip) return reply({error:'SOURCE_UNAVAILABLE'},503);
  const cloudflare_egress=request.cf?.asn===13335;
  if (u.pathname==='/identity') {
   const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(env.TRIAL+'|'+ip));
   const source_hash=Array.from(new Uint8Array(digest),x=>x.toString(16).padStart(2,'0')).join('');
   return reply({source_hash,cloudflare_egress});
  }
  await env.DB.prepare('INSERT INTO observations(trial,bucket,total,remote) VALUES(?,?,1,?) ON CONFLICT(trial,bucket) DO UPDATE SET total=total+1, remote=remote+excluded.remote').bind(env.TRIAL,bucket,cloudflare_egress?1:0).run();
  return reply({observed:true,cloudflare_egress});
 }
};
