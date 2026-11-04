package busbar

import (
	"strings"
	"testing"
)

func TestGeneratedDocumentationInputs(t *testing.T) {
	input := []byte("admin_token = var.busbar_admin_token\nBUSBAR_CONFIG_OVERLAY and issue_aws_credential; `issue_aws_credential`")
	edits := Provider().DocRules.EditRules(nil)
	output, err := edits[0].Edit("config.md", input)
	if err != nil {
		t.Fatal(err)
	}
	text := string(output)
	for _, want := range []string{`admin_token = "replace-with-your-admin-token"`, "`BUSBAR_CONFIG_OVERLAY`", "`issue_aws_credential`"} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q in documentation: %s", want, text)
		}
	}
	if strings.Contains(text, "var.busbar_admin_token") || strings.Contains(text, "``") {
		t.Fatal("unresolved variable or duplicated inline-code delimiter")
	}
}
