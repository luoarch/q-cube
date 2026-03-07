FROM node:22-alpine AS base
RUN corepack enable && corepack prepare pnpm@latest --activate

# --- Build stage ---
FROM base AS builder
WORKDIR /app

# Copy workspace manifests
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json tsconfig.base.json ./
COPY packages/shared-contracts/package.json packages/shared-contracts/
COPY packages/shared-types/package.json packages/shared-types/
COPY apps/api/package.json apps/api/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source
COPY packages/shared-contracts/ packages/shared-contracts/
COPY packages/shared-types/ packages/shared-types/
COPY apps/api/ apps/api/

# Build shared-contracts first, then API
RUN pnpm --filter @q3/shared-contracts build && \
    pnpm --filter @q3/api build

# --- Production stage ---
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copy built artifacts
COPY --from=builder /app/pnpm-lock.yaml /app/pnpm-workspace.yaml /app/package.json /app/tsconfig.base.json ./
COPY --from=builder /app/packages/shared-contracts/ packages/shared-contracts/
COPY --from=builder /app/packages/shared-types/ packages/shared-types/
COPY --from=builder /app/apps/api/package.json apps/api/
COPY --from=builder /app/apps/api/dist/ apps/api/dist/

RUN pnpm install --frozen-lockfile --prod

EXPOSE 4000

CMD ["node", "apps/api/dist/main.js"]
