# Pulumi Busbar Provider

A [Pulumi](https://www.pulumi.com) provider for [Busbar](https://getbusbar.com), the
LLM gateway. It manages Busbar resources through the gateway's admin API and is a
**bridge** of the upstream [`GetBusbar/terraform-provider-busbar`](https://github.com/GetBusbar/terraform-provider-busbar)
(a Terraform Plugin Framework provider, Terraform protocol 6), built with
[`pulumi-terraform-bridge`](https://github.com/pulumi/pulumi-terraform-bridge).

- **Pulumi package name:** `busbar`
- **Plugin / registry reference:** `getbusbar/busbar`
- **npm package:** `@getbusbar/pulumi-busbar`
- **PyPI package:** `pulumi_busbar`
- **Go module:** `github.com/getbusbar/pulumi-busbar/sdk/go/busbar`

## Installing

### Plugin

```bash
pulumi plugin install resource busbar --server github://api.github.com/getbusbar
```

### TypeScript / JavaScript

```bash
npm install @getbusbar/pulumi-busbar
```

### Python

```bash
pip install pulumi_busbar
```

### Go

```bash
go get github.com/getbusbar/pulumi-busbar/sdk/go/busbar
```

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
import * as busbar from "@getbusbar/pulumi-busbar";

const info = busbar.getInfo();

const key = new busbar.VirtualKey("primary", {
    // ...inputs matching the busbar_virtual_key schema...
});
```

## Building from source

This repository bridges a **local, unpublished** copy of the upstream Terraform
provider via `go.mod` `replace` directives (see `provider/go.mod` and
`provider/shim/go.mod`). The upstream provider's implementation lives in an
`internal/` package, so a small re-export shim
(`provider/shim/busbarshim`) whose import path descends from the upstream module
root is used to expose `provider.New` to the bridge.

```bash
make provider      # build tfgen, generate schema.json, build the plugin binary
make build_sdks    # generate the nodejs, python, and go SDKs
make drift         # regenerate everything and fail if the tree is dirty (CI)
```

## License

Apache-2.0. See [LICENSE](./LICENSE). The upstream Terraform provider is
distributed under MPL-2.0.
