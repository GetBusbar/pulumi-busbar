package busbar

import (
	"context"
	"github.com/getbusbar/pulumi-busbar/provider/pkg/version"
	"github.com/pulumi/pulumi/sdk/v3/go/common/resource"
	"testing"
)

func TestConfigDocumentSecret(t *testing.T) {
	resource := Provider().Resources["busbar_config"]
	field := resource.Fields["document"]
	if field == nil || field.Secret == nil || !*field.Secret {
		t.Fatal("config documents must retain secret metadata when regenerating SDKs")
	}
}

func TestPythonUsesBuildVersion(t *testing.T) {
	if !Provider().Python.RespectSchemaVersion {
		t.Fatal("Python SDK must use the provider build version rather than 0.0.0")
	}
}

func TestHookIdentityUsesName(t *testing.T) {
	compute := Provider().Resources["busbar_hook"].ComputeID
	if compute == nil {
		t.Fatal("hook identity must delegate to the Terraform name field")
	}
	id, err := compute(context.Background(), resource.PropertyMap{
		"name": resource.NewStringProperty("audit-hook"),
	})
	if err != nil || id != "audit-hook" {
		t.Fatalf("hook identity = %q, %v", id, err)
	}
}

func TestVirtualKeyCredentialsMayBeAbsent(t *testing.T) {
	fields := Provider().Resources["busbar_virtual_key"].Fields
	for _, name := range []string{"aws_access_key_id", "aws_secret_access_key", "secret"} {
		field := fields[name]
		if field == nil || field.MarkAsOptional == nil || !*field.MarkAsOptional {
			t.Errorf("%s must be optional for non-AWS keys and imports", name)
		}
	}
}

func TestGoImportPathUsesModuleMajor(t *testing.T) {
	original := version.Version
	t.Cleanup(func() { version.Version = original })
	for _, test := range []struct{ version, want string }{
		{"0.0.1", "github.com/getbusbar/pulumi-busbar/sdk/go/busbar"},
		{"2.0.0", "github.com/getbusbar/pulumi-busbar/sdk/v2/go/busbar"},
	} {
		version.Version = test.version
		if got := Provider().Golang.ImportBasePath; got != test.want {
			t.Errorf("version %s import = %q; want %q", test.version, got, test.want)
		}
	}
}
