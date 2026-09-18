FROM node:24-bookworm-slim AS build
RUN npm install --global pnpm@10.11.0
WORKDIR /workspace
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm build
FROM caddy:2.10-alpine
COPY --from=build /workspace/apps/web/dist /srv
COPY infra/Caddyfile /etc/caddy/Caddyfile
