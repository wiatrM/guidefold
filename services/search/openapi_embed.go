package main

import _ "embed"

// managementSpec is the versioned contract served at GET /api/v1/openapi.yaml.
//
//go:embed openapi/management-v1.yaml
var managementSpec []byte
