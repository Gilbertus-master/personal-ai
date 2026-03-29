#!/bin/bash
set -e

echo "=== Step 1/3: TypeScript type check ==="
pnpm --filter @gilbertus/web exec tsc --noEmit

echo "=== Step 2/3: ESLint ==="
pnpm --filter @gilbertus/web lint

echo "=== Step 3/3: Next.js build ==="
pnpm --filter @gilbertus/web build

echo "All frontend checks passed!"
