// Package busbarshim re-exports the upstream terraform-provider-busbar
// provider factory so it can be consumed from outside the upstream module.
//
// The upstream provider implementation lives in its module's internal/provider
// package, which Go forbids importing from an unrelated module path. Because
// this package's import path descends from the same module root
// (github.com/GetBusbar/terraform-provider-busbar/...), it is permitted to
// import the internal package and re-export the public New factory. The Pulumi
// bridge program then depends on this shim instead of the internal package.
package busbarshim

import (
	"github.com/GetBusbar/terraform-provider-busbar/internal/provider"
	fwprovider "github.com/hashicorp/terraform-plugin-framework/provider"
)

// New returns a Terraform Plugin Framework provider factory for the given
// build version, mirroring provider.New in the upstream module.
func New(version string) func() fwprovider.Provider {
	return provider.New(version)
}
