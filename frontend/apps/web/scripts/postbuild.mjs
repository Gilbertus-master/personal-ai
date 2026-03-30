// Post-build: restore API routes and middleware if they were moved
import { existsSync, renameSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const apiDir = join(root, 'app', 'api');
const apiBackup = join(root, 'app', '_api_backup');
const middleware = join(root, 'middleware.ts');
const middlewareBackup = join(root, '_middleware_backup.ts');

if (existsSync(apiBackup)) {
  renameSync(apiBackup, apiDir);
  console.log('[postbuild] Restored app/api');
}
if (existsSync(middlewareBackup)) {
  renameSync(middlewareBackup, middleware);
  console.log('[postbuild] Restored middleware.ts');
}
