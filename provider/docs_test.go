package busbar

import (
	"strings"
	"testing"

	"github.com/pulumi/pulumi-terraform-bridge/v3/pkg/tfbridge"
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

func TestGeneratedDocumentationLeavesCodeBlocksLiteral(t *testing.T) {
	input := "Set BUSBAR_CONFIG_OVERLAY.\n```hcl\nissue_aws_credential = true\n```\nThen issue_aws_credential."
	var edit tfbridge.DocsEdit
	for _, candidate := range Provider().DocRules.EditRules(nil) {
		if candidate.Path == "*" {
			edit = candidate
		}
	}
	if edit.Edit == nil {
		t.Fatal("documentation edit must apply to every upstream page")
	}
	output, err := edit.Edit("virtual_key.md", []byte(input))
	if err != nil {
		t.Fatal(err)
	}
	want := "Set `BUSBAR_CONFIG_OVERLAY`.\n```hcl\nissue_aws_credential = true\n```\nThen `issue_aws_credential`."
	if string(output) != want {
		t.Fatalf("documentation = %q; want %q", output, want)
	}
}
