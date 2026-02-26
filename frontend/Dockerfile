# ── deps: shared install layer ───────────────────────────────────────────────
FROM node:22 AS deps

WORKDIR /app

COPY package*.json ./

RUN npm install

# ── dev: Vite dev server (used by compose.override.yml) ──────────────────────
FROM deps AS dev

COPY . .

EXPOSE 80

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]

# ── build: production static bundle ──────────────────────────────────────────
FROM deps AS build

COPY . .

RUN npm run build

# ── prod: nginx serving the static bundle (default) ──────────────────────────
FROM nginx:1

COPY --from=build /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
