package sdktests

import (
	"context"
	"testing"

	"github.com/getbusbar/pulumi-busbar/sdk/go/busbar/config"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi/internals"
)

func TestTokenEnvironmentFallbackIsSecret(t *testing.T) {
	t.Setenv("BUSBAR_ADMIN_TOKEN", "environment-token")
	err := pulumi.RunErr(func(ctx *pulumi.Context) error {
		result, err := internals.UnsafeAwaitOutput(context.Background(), config.GetToken(ctx))
		if err != nil {
			return err
		}
		if !result.Secret || result.Value != "environment-token" {
			t.Errorf("token = %#v, secret %v", result.Value, result.Secret)
		}
		return nil
	}, pulumi.WithMocks("project", "stack", argumentMocks{}))
	if err != nil {
		t.Fatal(err)
	}
}
