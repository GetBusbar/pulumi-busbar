# busbar_info (Data Source)

Read the gateway version, compiled plugin proof, uptime, and topology through the admin API.

## Example Usage

```typescript
import * as busbar from "@getbusbar/pulumi-busbar";

const current = busbar.getInfo();
export const busbarVersion = current.then(info => info.version);
export const compiledAuthModules = current.then(info => info.authModules);
```

```python
import pulumi
import pulumi_busbar as busbar

current = busbar.get_info()
pulumi.export("busbarVersion", current.version)
pulumi.export("compiledAuthModules", current.auth_modules)
```

```go
package main

import (
    "github.com/getbusbar/pulumi-busbar/sdk/go/busbar"
    "github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

func main() {
    pulumi.Run(func(ctx *pulumi.Context) error {
        current, err := busbar.GetInfo(ctx)
        if err != nil {
            return err
        }
        ctx.Export("busbarVersion", pulumi.String(current.Version))
        ctx.Export("compiledAuthModules", pulumi.ToStringArray(current.AuthModules))
        return nil
    })
}
```
