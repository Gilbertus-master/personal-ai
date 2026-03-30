// Pre-build: for Tauri static export, move API routes and middleware out of the way
import { existsSync, renameSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const apiDir = join(root, 'app', 'api');
const apiBackup = join(root, 'app', '_api_backup');
const middleware = join(root, 'middleware.ts');
const middlewareBackup = join(root, '_middleware_backup.ts');

if (process.env.TAURI_BUILD === '1') {
  if (existsSync(apiDir)) {
    renameSync(apiDir, apiBackup);
    console.log('[prebuild] Tauri: moved app/api → app/_api_backup');
  }
  if (existsSync(middleware)) {
    renameSync(middleware, middlewareBackup);
    console.log('[prebuild] Tauri: moved middleware.ts → _middleware_backup.ts');
  }
} else {
  console.log('[prebuild] Standard build, no changes needed');
}
