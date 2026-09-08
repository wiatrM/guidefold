# The developer portal, self-hosted: the Markdown in portal/ built to static HTML and served by
# an unprivileged nginx. The same files are Mintlify's source (portal/docs.json), so a team that
# prefers Mintlify hosting points `mint` at this directory instead and does not build this image.
#
# Build from the repository root:  docker build -f portal/Dockerfile -t guidefold-portal .

FROM python:3.12-slim-bookworm AS build
WORKDIR /src
RUN pip install --no-cache-dir --root-user-action=ignore "mkdocs-material==9.5.39" "pymdownx==0.0.1" 2>/dev/null || \
    pip install --no-cache-dir --root-user-action=ignore "mkdocs-material==9.5.39"
COPY portal/ /src/portal/
RUN cd /src/portal && mkdocs build --strict && test -f /src/.portal-site/index.html

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /src/.portal-site/ /usr/share/nginx/html/
# nginx-unprivileged listens on 8080 as uid 101; nothing here needs more.
EXPOSE 8080
