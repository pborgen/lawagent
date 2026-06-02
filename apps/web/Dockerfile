# syntax=docker/dockerfile:1.7
#
# lawagent web image (Next.js 16 standalone server)
#
# Build context is apps/web (NOT the repo root) — this is a separate npm
# project with its own lockfile, so everything it needs is in this dir.
#   docker build -t lawagent-web -f apps/web/Dockerfile apps/web
#
# Three stages:
#   deps     — `npm ci` against the lockfile (cached unless deps change)
#   builder  — `next build` → emits .next/standalone (needs output:"standalone")
#   runtime  — slim node image carrying only the standalone bundle
#
# Auth is NOT required to build: getAuthConfig() is lazy (only the auth
# routes read Cognito env), so AUTH_DISABLED=true keeps `next build`
# hermetic. Real auth env is injected at runtime by App Runner.

ARG NODE_VERSION=22

# ---------- deps -------------------------------------------------------
FROM node:${NODE_VERSION}-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# ---------- builder ----------------------------------------------------
FROM node:${NODE_VERSION}-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . ./
ENV NEXT_TELEMETRY_DISABLED=1 \
    AUTH_DISABLED=true
RUN npm run build

# ---------- runtime ----------------------------------------------------
FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs

# The standalone bundle already contains a minimal node_modules and
# server.js. Static assets and public/ are NOT traced into it — copy
# them alongside so the server can serve them.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# Liveness probe. The landing page "/" is public (no auth, no Cognito env
# needed), so it answers 200 even before auth env is wired — which is why
# App Runner's health check targets "/" rather than an /api route.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
