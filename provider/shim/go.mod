// This module intentionally uses an import path that descends from the upstream
// terraform-provider-busbar module root, so its package may import the
// upstream internal/provider package. It is wired into the bridge program via a
// go.mod replace directive; it is never published.
module github.com/GetBusbar/terraform-provider-busbar/shim

go 1.26

replace github.com/GetBusbar/terraform-provider-busbar => ../../../../terraform-provider-busbar

require (
	github.com/GetBusbar/terraform-provider-busbar v0.0.0-00010101000000-000000000000
	github.com/hashicorp/terraform-plugin-framework v1.19.0
)

require (
	github.com/apapsch/go-jsonmerge/v2 v2.0.0 // indirect
	github.com/fatih/color v1.18.0 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/hashicorp/go-hclog v1.6.3 // indirect
	github.com/hashicorp/go-uuid v1.0.3 // indirect
	github.com/hashicorp/terraform-plugin-go v0.31.0 // indirect
	github.com/hashicorp/terraform-plugin-log v0.10.0 // indirect
	github.com/mattn/go-colorable v0.1.14 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/mitchellh/go-testing-interface v1.14.1 // indirect
	github.com/oapi-codegen/runtime v1.6.0 // indirect
	github.com/vmihailenco/msgpack/v5 v5.4.1 // indirect
	github.com/vmihailenco/tagparser/v2 v2.0.0 // indirect
	golang.org/x/sys v0.47.0 // indirect
)
