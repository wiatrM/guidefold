# syntax=docker/dockerfile:1
FROM golang:1.26-bookworm@sha256:9fdc884aacc3bec89b20ffc69f4bb369c78210e3e4f600387b5128b12c199f81 AS build
WORKDIR /src
COPY services/search/go.mod services/search/go.sum ./
RUN go mod download
COPY services/search/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/guidefold-search .
FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab
WORKDIR /app
COPY --from=build /out/guidefold-search /app/guidefold-search
COPY tools/serve_spike/contracts/harness-service-v1.1.schema.json /app/contract.json
# The 1.2 request schema sits next to the 1.1 one, which is where the service
# looks for it. Without the file a 1.2 request is refused rather than validated
# against 1.1 and granted guarantees the deployment cannot keep.
COPY tools/serve_spike/contracts/harness-service-v1.2.schema.json /app/harness-service-v1.2.schema.json
COPY skills/guidefold/scripts/guidefold /app/policy-source
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/guidefold-search"]
CMD ["serve"]
