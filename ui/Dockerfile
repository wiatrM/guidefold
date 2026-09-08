# The hosted U4 React app, static-built and served by an unprivileged nginx behind
# ingress-nginx. Same-origin by design (src/api/client.ts: "same-origin /api/v1 unless
# VITE_GUIDEFOLD_API points elsewhere") — the ingress routes /api and /v1 to the API
# service directly, so this container is a plain static file server, not a proxy.
#
# Build from the repository root:  docker build -f ui/Dockerfile -t guidefold-ui .

FROM node:22.14.0-bookworm-slim AS build
WORKDIR /src
RUN corepack enable
COPY ui/package.json ui/pnpm-lock.yaml /src/
RUN corepack use pnpm@10.30.3 && pnpm install --frozen-lockfile
COPY ui/ /src/
RUN pnpm build && test -f /src/dist/index.html

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /src/dist/ /usr/share/nginx/html/
COPY ui/nginx-spa.conf /etc/nginx/conf.d/default.conf
# nginx-unprivileged listens on 8080 as uid 101; nothing here needs more.
EXPOSE 8080
