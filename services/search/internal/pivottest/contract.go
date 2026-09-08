package pivottest

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/santhosh-tekuri/jsonschema/v6"
	"gopkg.in/yaml.v3"
)

// Contract compiles the component schemas of the published OpenAPI document and
// validates real handler responses against them. The point is not that the file
// parses: it is that the document and the running server agree, so a response
// that quietly grows or loses a field fails a test rather than a client.
type Contract struct {
	compiler *jsonschema.Compiler
	Document map[string]any
}

const specURI = "https://guidefold.example/openapi/management-v1.yaml"

// LoadContract reads services/search/openapi/management-v1.yaml.
func LoadContract(t *testing.T) *Contract {
	t.Helper()
	raw, e := os.ReadFile(filepath.Join(Root(t), "services/search/openapi/management-v1.yaml"))
	if e != nil {
		t.Fatal(e)
	}
	var parsed any
	if e := yaml.Unmarshal(raw, &parsed); e != nil {
		t.Fatalf("the OpenAPI document is not valid YAML: %v", e)
	}
	// Round-trip through JSON so the schema compiler sees the same value types a
	// decoded response has.
	encoded, e := json.Marshal(parsed)
	if e != nil {
		t.Fatal(e)
	}
	document, e := jsonschema.UnmarshalJSON(bytes.NewReader(encoded))
	if e != nil {
		t.Fatal(e)
	}
	c := jsonschema.NewCompiler()
	if e = c.AddResource(specURI, document); e != nil {
		t.Fatal(e)
	}
	root, _ := document.(map[string]any)
	if root == nil {
		t.Fatal("the OpenAPI document is not an object")
	}
	return &Contract{compiler: c, Document: root}
}

// Check validates one response body against one component schema.
func (c *Contract) Check(t *testing.T, schema string, value map[string]any) {
	t.Helper()
	compiled, e := c.compiler.Compile(specURI + "#/components/schemas/" + schema)
	if e != nil {
		t.Fatalf("compile %s: %v", schema, e)
	}
	raw, e := json.Marshal(value)
	if e != nil {
		t.Fatal(e)
	}
	decoded, e := jsonschema.UnmarshalJSON(bytes.NewReader(raw))
	if e != nil {
		t.Fatal(e)
	}
	if e = compiled.Validate(decoded); e != nil {
		t.Errorf("%s does not match the contract: %v\npayload: %s", schema, e, raw)
	}
}
