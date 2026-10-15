# Ishchi server: frontend yig'iladi va Caddy bilan beriladi (Caddy HTTPS ni ham o'zi oladi)
FROM docker.io/library/node:24 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM docker.io/library/caddy:2.10.0
COPY --from=build /app/dist /srv/app
COPY Caddyfile /etc/caddy/Caddyfile
