// Copyright 2024, GetBusbar.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//	http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package busbar

import (
	_ "embed"
	"path/filepath"

	tfpf "github.com/GetBusbar/terraform-provider-busbar/shim/busbarshim"
	pf "github.com/pulumi/pulumi-terraform-bridge/v3/pkg/pf/tfbridge"
	"github.com/pulumi/pulumi-terraform-bridge/v3/pkg/tfbridge"

	"github.com/getbusbar/pulumi-busbar/provider/pkg/version"
)

// mainPkg is the name of the Pulumi package this provider ships.
const mainPkg = "busbar"

// mainMod is the primary namespace tokens live under.
const mainMod = "index"

//go:embed cmd/pulumi-resource-busbar/bridge-metadata.json
var bridgeMetadata []byte

// upstreamLicense is the license the upstream Terraform provider is distributed
// under (the Terraform Plugin Framework itself is MPL 2.0).
var upstreamLicense = tfbridge.MPL20LicenseType

// Provider returns the tfbridge.ProviderInfo mapping the upstream
// terraform-provider-busbar (a Terraform Plugin Framework provider, protocol 6)
// into a Pulumi provider.
func Provider() tfbridge.ProviderInfo {
	info := tfbridge.ProviderInfo{
		// Wire the upstream Plugin Framework provider via the pf shim. The
		// upstream factory is provider.New(version) which returns a
		// func() provider.Provider.
		P: pf.ShimProvider(tfpf.New(version.Version)()),

		Name:              "busbar",
		DisplayName:       "Busbar",
		Publisher:         "GetBusbar",
		Description:       "A Pulumi package for creating and managing Busbar LLM gateway resources through its admin API.",
		Keywords:          []string{"pulumi", "busbar", "llm", "gateway", "ai", "category/utility"},
		License:           "Apache-2.0",
		Homepage:          "https://getbusbar.com",
		Repository:        "https://github.com/getbusbar/pulumi-busbar",
		GitHubOrg:         "GetBusbar",
		TFProviderLicense: &upstreamLicense,
		Version:           version.Version,
		MetadataInfo:      tfbridge.NewProviderMetadata(bridgeMetadata),

		// Environment fallbacks matching the upstream provider.
		Config: map[string]*tfbridge.SchemaInfo{
			"endpoint": {
				Default: &tfbridge.DefaultInfo{
					EnvVars: []string{"BUSBAR_ENDPOINT"},
				},
			},
			"token": {
				Secret: tfbridge.True(),
				Default: &tfbridge.DefaultInfo{
					EnvVars: []string{"BUSBAR_ADMIN_TOKEN"},
				},
			},
		},

		Resources: map[string]*tfbridge.ResourceInfo{
			"busbar_virtual_key": {Tok: tfbridge.MakeResource(mainPkg, mainMod, "VirtualKey")},
			"busbar_hook":        {Tok: tfbridge.MakeResource(mainPkg, mainMod, "Hook")},
			"busbar_config":      {Tok: tfbridge.MakeResource(mainPkg, mainMod, "Config")},
		},

		DataSources: map[string]*tfbridge.DataSourceInfo{
			"busbar_info": {Tok: tfbridge.MakeDataSource(mainPkg, mainMod, "getInfo")},
		},

		JavaScript: &tfbridge.JavaScriptInfo{
			PackageName: "@getbusbar/pulumi-busbar",
			Dependencies: map[string]string{
				"@pulumi/pulumi": "^3.0.0",
			},
			DevDependencies: map[string]string{
				"@types/node": "^18",
			},
		},
		Python: &tfbridge.PythonInfo{
			PackageName: "pulumi_busbar",
			Requires: map[string]string{
				"pulumi": ">=3.0.0,<4.0.0",
			},
		},
		Golang: &tfbridge.GolangInfo{
			ImportBasePath: filepath.Join(
				"github.com/getbusbar/pulumi-busbar/sdk/go",
				tfbridge.GetModuleMajorVersion(version.Version),
				"busbar",
			),
			GenerateResourceContainerTypes: true,
		},
	}

	info.SetAutonaming(255, "-")

	return info
}
