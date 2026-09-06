# syntax=docker/dockerfile:1
ARG GUIDEFOLD_IMAGE
ARG TEI_IMAGE=ghcr.io/huggingface/text-embeddings-inference@sha256:e47e625ced2385d3dbfdee79ba0380204578e0b27ef1a926783f9b3486aaf109
FROM ${GUIDEFOLD_IMAGE} AS verifier
FROM ${TEI_IMAGE}
ARG ENCODER_ID
COPY --from=verifier /app/guidefold-search /usr/local/bin/guidefold-verify
# Build context is the verified adapter directory produced by gpu.py prepare.
COPY . /model/
RUN GUIDEFOLD_ENCODER_ID=${ENCODER_ID} /usr/local/bin/guidefold-verify verify-model /model
