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
	"bytes"
	_ "embed"
	"path"

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

//go:embed docs/info.md
var infoDocs []byte

// upstreamLicense is the license the upstream Terraform provider is distributed
// under, as recorded in the published provider module LICENSE.
var upstreamLicense = tfbridge.Apache20LicenseType

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
		PluginDownloadURL: "github://api.github.com/getbusbar",
		MetadataInfo:      tfbridge.NewProviderMetadata(bridgeMetadata),
		DocRules: &tfbridge.DocRuleInfo{
			EditRules: func(defaults []tfbridge.DocsEdit) []tfbridge.DocsEdit {
				return append(defaults, tfbridge.DocsEdit{Path: "*", Edit: prepareUpstreamDocs})
			},
		},

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
			"busbar_virtual_key": {
				Tok: tfbridge.MakeResource(mainPkg, mainMod, "VirtualKey"),
				Fields: map[string]*tfbridge.SchemaInfo{
					"aws_access_key_id":     {MarkAsOptional: tfbridge.True()},
					"aws_secret_access_key": {MarkAsOptional: tfbridge.True()},
					"secret":                {MarkAsOptional: tfbridge.True()},
				},
			},
			"busbar_hook": {
				Tok:       tfbridge.MakeResource(mainPkg, mainMod, "Hook"),
				ComputeID: tfbridge.DelegateIDField("name", mainPkg, "https://github.com/getbusbar/pulumi-busbar"),
				Fields: map[string]*tfbridge.SchemaInfo{
					// Keep the canonical field name instead of pluralizing this list.
					"phase": {Name: "phase"},
				},
			},
			"busbar_config": {
				Tok: tfbridge.MakeResource(mainPkg, mainMod, "Config"),
				Fields: map[string]*tfbridge.SchemaInfo{
					"document": {Secret: tfbridge.True()},
				},
			},
		},

		DataSources: map[string]*tfbridge.DataSourceInfo{
			"busbar_info": {
				Tok:  tfbridge.MakeDataSource(mainPkg, mainMod, "getInfo"),
				Docs: &tfbridge.DocInfo{Markdown: infoDocs},
			},
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
			PackageName:          "pulumi_busbar",
			RespectSchemaVersion: true,
			Requires: map[string]string{
				"pulumi": ">=3.0.0,<4.0.0",
			},
		},
		Golang: &tfbridge.GolangInfo{
			ImportBasePath: path.Join(
				"github.com/getbusbar/pulumi-busbar/sdk",
				tfbridge.GetModuleMajorVersion(version.Version),
				"go",
				"busbar",
			),
			GenerateResourceContainerTypes: true,
		},
	}

	info.SetAutonaming(255, "-")

	return info
}

// prepareUpstreamDocs runs before the bridge translates HCL examples and parses
// Markdown. Keep examples self-contained and literal API names out of emphasis.
func prepareUpstreamDocs(_ string, content []byte) ([]byte, error) {
	content = bytes.ReplaceAll(content, []byte("var.busbar_admin_token"), []byte(`"replace-with-your-admin-token"`))
	lines := bytes.Split(content, []byte("\n"))
	inCode := false
	for i, line := range lines {
		if bytes.HasPrefix(bytes.TrimSpace(line), []byte("```")) {
			inCode = !inCode
			continue
		}
		if inCode {
			continue
		}
		for _, name := range []string{"BUSBAR_CONFIG_OVERLAY", "issue_aws_credential"} {
			line = bytes.ReplaceAll(line, []byte(name), []byte("`"+name+"`"))
			line = bytes.ReplaceAll(line, []byte("``"+name+"``"), []byte("`"+name+"`"))
		}
		lines[i] = line
	}
	return bytes.Join(lines, []byte("\n")), nil
}
