# The developer portal, self-hosted: the Markdown in portal/content built to static HTML and served by
# an unprivileged nginx. The same files are Mintlify's source (portal/content/docs.json), so a team that
# prefers Mintlify hosting points `mint` at this directory instead and does not build this image.
#
# Build from the repository root:  docker build -f portal/Dockerfile -t guidefold-portal .

FROM python:3.12-slim-bookworm AS build
WORKDIR /src
# mkdocs-material pins mkdocs and pymdown-extensions (the mermaid fence) itself.
RUN pip install --no-cache-dir --root-user-action=ignore "mkdocs-material==9.5.39"
COPY portal/ /src/portal/
RUN cd /src/portal && mkdocs build --strict && test -f /src/.portal-site/index.html

FROM nginxinc/nginx-unprivileged:1.27-alpine
# Nested under docs/, not the document root: the guidefold.cloudfloo.io deployment
# mounts this at /docs (the hosted UI owns /, see ui/Dockerfile) via a plain,
# non-rewriting ingress path (deploy/k8s/chart/templates/portal.yaml) — nginx's own
# directory-redirect (evidence -> evidence/) only comes out with the right Location
# if nginx's own view of the path already includes /docs. A standalone deployment
# at domain root would need this COPY destination changed back to the plain root.
COPY --from=build /src/.portal-site/ /usr/share/nginx/html/docs/
# Correct directory-redirect Location headers behind ingress — see the file's own
# comment. Without this, e.g. /evidence -> /evidence/ redirects to a port nothing
# outside the cluster can reach.
COPY portal/nginx-absolute-redirect-off.conf /etc/nginx/conf.d/absolute-redirect-off.conf
# nginx-unprivileged listens on 8080 as uid 101; nothing here needs more.
EXPOSE 8080
