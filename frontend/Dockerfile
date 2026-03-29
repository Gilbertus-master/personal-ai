# Multi-stage Dockerfile for Gilbertus Frontend (Next.js monorepo)
# Usage: docker build -t gilbertus-web ./frontend
#
# Build args:
#   GILBERTUS_API_URL — backend URL for SSR (default: http://api:8000)

# ── Stage 1: Dependencies ────────────────────────────────────────────
FROM node:20-alpine AS deps

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

# Copy workspace config first (layer cache)
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY apps/desktop/package.json ./apps/desktop/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
COPY packages/i18n/package.json ./packages/i18n/package.json
COPY packages/rbac/package.json ./packages/rbac/package.json
COPY packages/ui/package.json ./packages/ui/package.json

RUN pnpm install --frozen-lockfile

# ── Stage 2: Build ───────────────────────────────────────────────────
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=deps /app/apps/desktop/node_modules ./apps/desktop/node_modules
COPY --from=deps /app/packages/api-client/node_modules ./packages/api-client/node_modules
COPY --from=deps /app/packages/i18n/node_modules ./packages/i18n/node_modules
COPY --from=deps /app/packages/rbac/node_modules ./packages/rbac/node_modules
COPY --from=deps /app/packages/ui/node_modules ./packages/ui/node_modules

# Copy all source
COPY . .

# Build-time env vars
ARG GILBERTUS_API_URL=http://api:8000
ENV GILBERTUS_API_URL=${GILBERTUS_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm --filter web build

# ── Stage 3: Production runner ───────────────────────────────────────
FROM node:20-alpine AS runner

LABEL maintainer="Sebastian Jablonski <sebastian@gilbertus.local>"
LABEL description="Gilbertus Frontend — Next.js web application"

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone output
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public

USER nextjs

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
