package busbarshim

import (
	"context"
	"testing"

	fwprovider "github.com/hashicorp/terraform-plugin-framework/provider"
)

func TestNewReexportsUpstreamProvider(t *testing.T) {
	provider := New("1.2.3")()
	var response fwprovider.MetadataResponse
	provider.Metadata(context.Background(), fwprovider.MetadataRequest{}, &response)
	if response.TypeName != "busbar" || response.Version != "1.2.3" {
		t.Fatalf("metadata = %q %q; want busbar 1.2.3", response.TypeName, response.Version)
	}
	if len(provider.Resources(context.Background())) != 3 {
		t.Fatal("shim must expose the upstream virtual key, hook and config resources")
	}
}
