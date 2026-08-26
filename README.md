# Pulumi Busbar Provider

[![CI](https://github.com/GetBusbar/pulumi-busbar/actions/workflows/build.yml/badge.svg)](https://github.com/GetBusbar/pulumi-busbar/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/GetBusbar/pulumi-busbar/branch/main/graph/badge.svg)](https://codecov.io/gh/GetBusbar/pulumi-busbar)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

A [Pulumi](https://www.pulumi.com) provider for [Busbar](https://getbusbar.com), the
LLM gateway. It manages Busbar resources through the gateway's admin API and is a
**bridge** of the upstream [`GetBusbar/terraform-provider-busbar`](https://github.com/GetBusbar/terraform-provider-busbar)
(a Terraform Plugin Framework provider, Terraform protocol 6), built with
[`pulumi-terraform-bridge`](https://github.com/pulumi/pulumi-terraform-bridge).

- **Pulumi package name:** `busbar`
- **Plugin reference:** `getbusbar/busbar`
- **Go module:** `github.com/getbusbar/pulumi-busbar/sdk/go/busbar` (published, usable today)
- **npm package:** `@getbusbar/pulumi-busbar` (NOT PUBLISHED YET, see below)
- **PyPI package:** `pulumi_busbar` (NOT PUBLISHED YET, see below)

## Installing

### What is actually published today

| Artifact | Where | Status |
| -------- | ----- | ------ |
| Provider plugin binaries (`pulumi-resource-busbar`, darwin/linux/windows on amd64 and arm64) | GitHub Releases of this repo | published |
| Go SDK | this git repo, consumed by module path | published |
| npm `@getbusbar/pulumi-busbar` | npmjs.com | NOT published |
| PyPI `pulumi_busbar` | pypi.org | NOT published |
| Pulumi registry entry `getbusbar/busbar` | registry.pulumi.com | NOT published |

The npm, PyPI and Pulumi-registry publications are blocked on credentials that only a
repository owner can provision (see "CI & release status" below). Everything in this
section describes what a user can install right now, with no credentials.

### Plugin

The plugin binaries live on this repo's GitHub Releases, and Pulumi can install them
straight from there with its GitHub plugin server. This is the supported install path
until the Pulumi registry entry exists:

```bash
pulumi plugin install resource busbar <version> --server github://api.github.com/getbusbar
# for example
pulumi plugin install resource busbar 0.1.3 --server github://api.github.com/getbusbar
```

To pin it inside a project instead, add the same server to `Pulumi.yaml`:

```yaml
plugins:
  providers:
    - name: busbar
      version: 0.1.3
      server: github://api.github.com/getbusbar
```

Or download a release tarball directly and install from the unpacked path:

```bash
curl -fsSLO https://github.com/GetBusbar/pulumi-busbar/releases/download/v0.1.3/pulumi-resource-busbar-v0.1.3-darwin-arm64.tar.gz
mkdir -p busbar-plugin && tar -xzf pulumi-resource-busbar-v0.1.3-darwin-arm64.tar.gz -C busbar-plugin
pulumi plugin install resource busbar 0.1.3 --file busbar-plugin/pulumi-resource-busbar
```

### Go

The Go SDK needs no package registry; it is consumed straight from the git tag:

```bash
go get github.com/getbusbar/pulumi-busbar/sdk/go/busbar@v0.1.3
```

`sdk/` is its own Go module, so each release also carries a `sdk/vX.Y.Z` tag
which is what the Go toolchain actually resolves. A freshly pushed tag can take
a little while to appear on proxy.golang.org and sum.golang.org; until it does,
`GOPROXY=direct go get ...` fetches it straight from GitHub.

### TypeScript / JavaScript, Python

`npm install @getbusbar/pulumi-busbar` and `pip install pulumi_busbar` DO NOT WORK yet.
Nothing has been published under those names. Both SDKs are generated and committed in
this repo (`sdk/nodejs`, `sdk/python`) and are built on every release, but the publish
steps are credential-gated and self-skip. Until they are armed, consume the SDKs from
source in the release tarball of this repo, or use the Go SDK, or drive the provider
from a language of your choice against the installed plugin.

## Configuration

The provider reads the same settings as the upstream Terraform provider. Set them
with `pulumi config set busbar:<key>` or via environment variables:

| Config key        | Env var               | Description                                              |
| ----------------- | --------------------- | -------------------------------------------------------- |
| `busbar:endpoint` | `BUSBAR_ENDPOINT`     | Admin listener URL, e.g. `https://busbar-admin:8081`.    |
| `busbar:token`    | `BUSBAR_ADMIN_TOKEN`  | Operator admin token (sent as `x-admin-token`; secret).  |
| `busbar:clientCertPem` |                  | PEM client certificate for mTLS.                         |
| `busbar:clientKeyPem`  |                  | PEM private key for the client certificate (secret).     |
| `busbar:caCertPem`     |                  | PEM CA certificate to trust a private admin server.      |
| `busbar:insecure`      |                  | Skip TLS verification (development only).                |

## Resources & functions

| Terraform type       | Pulumi token                     |
| -------------------- | -------------------------------- |
| `busbar_virtual_key` | `busbar:index:VirtualKey`        |
| `busbar_hook`        | `busbar:index:Hook`              |
| `busbar_config`      | `busbar:index:Config`            |
| `busbar_info` (data) | `busbar:index:getInfo` (function)|

## Example (TypeScript)

```ts
// NOTE: this import resolves only once @getbusbar/pulumi-busbar is published to npm.
// Today the nodejs SDK is available from sdk/nodejs in this repo.
import * as busbar from "@getbusbar/pulumi-busbar";

const info = busbar.getInfo();

const key = new busbar.VirtualKey("primary", {
    // ...inputs matching the busbar_virtual_key schema...
});
```

## Building from source

This repository bridges the upstream Terraform provider as a published Go
module, pinned in `provider/shim/go.mod` (a released upstream tag; the
release-on-upstream workflow advances it automatically). The upstream
provider's implementation lives in an `internal/` package, so a small re-export
shim (`provider/shim/busbarshim`) whose import path descends from the upstream
module root is used to expose `provider.New` to the bridge; the shim itself is
wired in with a local `replace` directive in `provider/go.mod`.

To move to a newer upstream provider, run
`go get github.com/GetBusbar/terraform-provider-busbar@<ref>` in both
`provider/shim` and `provider`, then regenerate the SDKs.

Building requires Go 1.26+ and the [Pulumi CLI](https://www.pulumi.com/docs/install/)
(tfgen uses its language hosts for SDK codegen).

```bash
make provider      # build tfgen, generate schema.json, build the plugin binary
make build_sdks    # generate the nodejs, python, and go SDKs
make drift         # regenerate everything and fail if the tree is dirty (CI)
```

## CI & release status (honest)

- **build workflow** (`.github/workflows/build.yml`): compiles and vets the
  bridged provider and the Go SDK on every push/PR. No secrets needed; this is
  real coverage.
- **release workflow** (`.github/workflows/release.yml`): the build path
  (provider binary + all SDK codegen + nodejs `tsc` compile + python
  wheel/sdist build) has been exercised and works. The **publish** steps are
  gated on secret presence and currently **self-skip with a loud warning**
  because no publishing credentials are provisioned. To arm them, add repo
  secrets:
  - `NPM_TOKEN` - npm token with publish rights to `@getbusbar/pulumi-busbar`.
  - `PYPI_API_TOKEN` - PyPI API token for `pulumi_busbar`.

  ```bash
  gh secret set NPM_TOKEN      --repo GetBusbar/pulumi-busbar
  gh secret set PYPI_API_TOKEN --repo GetBusbar/pulumi-busbar
  ```

  Once set, the next release publishes both SDKs with no further code change.
- **Plugin binary publication works.** Every release since v0.1.0 uploads the six
  `pulumi-resource-busbar` platform tarballs to the GitHub Release using the
  built-in `GITHUB_TOKEN`, and `pulumi plugin install resource busbar <version>
  --server github://api.github.com/getbusbar` installs from them. This has been
  verified end to end against a published release.
- **Pulumi registry** (`getbusbar/busbar` on registry.pulumi.com): not submitted.
  The registry lists packages from a separate submission process, so the
  `--server github://` form above is the install path until that happens.
- **release-on-upstream workflow**: re-pins the upstream Terraform provider and
  cuts this repo's next version. On a fan-out dispatch it waits for the upstream
  terraform-provider release before deciding, because the fleet dispatch can
  arrive before that sibling release is published.

## License

Apache-2.0. See [LICENSE](./LICENSE). The upstream Terraform provider is
distributed under MPL-2.0.
