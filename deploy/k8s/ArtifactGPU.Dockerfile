# syntax=docker/dockerfile:1
ARG GUIDEFOLD_IMAGE
FROM ${GUIDEFOLD_IMAGE}
COPY snapshot.json embeddings.json /input/
