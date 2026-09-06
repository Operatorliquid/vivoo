FROM node:22-alpine AS build

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.12.4 --activate

COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN pnpm install --frozen-lockfile
RUN pnpm --filter @courtvision/frontend build

FROM nginx:1.30.4-alpine3.24
RUN apk upgrade --no-cache \
    && chown -R nginx:nginx /var/cache/nginx /var/run /etc/nginx/conf.d /usr/share/nginx/html
COPY --chown=nginx:nginx infra/deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chown=nginx:nginx --from=build /app/apps/frontend/dist /usr/share/nginx/html
EXPOSE 8080
USER nginx
