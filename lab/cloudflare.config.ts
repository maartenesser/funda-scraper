import {bindings, defineConfig} from 'cf/config';
import * as dashboard from './src/worker.js' with {type:'cf-worker'};
import * as observer from './src/egress.js' with {type:'cf-worker'};
import trial from './egress-trial.json' with {type:'json'};
export default defineConfig(({mode}) => ({
 accountId:'ca1c3e97ff0a63340a6f72be720b0ff4',
 worker: mode==='egress' || mode==='denied' ? {
  name: mode==='denied' ? 'funda-egress-denied' : 'funda-egress-observer',
  entrypoint:observer,compatibilityDate:'2026-11-17',
  env:{DB:bindings.d1({id:'7c0afe61-2e7a-4528-9f8c-148aefcac279',name:'funda-egress-observations'}),TRIAL:bindings.text(trial.trial),EXPIRES_AT:bindings.text(trial.expires_at)},
  observability:{enabled:true,traces:{enabled:true}}
 } : {name:'funda-monitor-lab',entrypoint:dashboard,compatibilityDate:'2026-11-17',observability:{enabled:true,traces:{enabled:true}}}
}));
