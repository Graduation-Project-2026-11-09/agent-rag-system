FROM node:22-bookworm-slim AS base
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# 開発用: ソースは compose でマウントする
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS build
COPY . .
RUN npm run build

# ステージング・本番用: ビルド結果を Caddy で配信する
FROM caddy:2.11.7-alpine AS prod
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
