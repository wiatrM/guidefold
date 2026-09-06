# syntax=docker/dockerfile:1
ARG GUIDEFOLD_IMAGE
FROM ${GUIDEFOLD_IMAGE}
# Context must contain only the reviewed snapshot and optional embeddings bundle.
COPY snapshot.json /input/snapshot.json
# For GPU publication add: COPY embeddings.json /input/embeddings.json
