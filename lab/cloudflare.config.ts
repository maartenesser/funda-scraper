import { defineConfig } from 'cf/config';
import * as entrypoint from './src/worker.js' with { type: 'cf-worker' };
export default defineConfig({
 accountId: 'ca1c3e97ff0a63340a6f72be720b0ff4',
 worker: {name:'funda-monitor-lab', entrypoint, compatibilityDate:'2026-11-17',
  observability: {enabled:true, traces:{enabled:true}}
 }
});
