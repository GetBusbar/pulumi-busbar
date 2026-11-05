package sdktests

import (
	"fmt"
	"github.com/getbusbar/pulumi-busbar/sdk/go/busbar"
	"reflect"
	"sync"
	"testing"

	"github.com/pulumi/pulumi/sdk/v3/go/common/resource"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
)

type argumentMocks struct{}

func (argumentMocks) Call(args pulumi.MockCallArgs) (resource.PropertyMap, error) {
	return args.Args, nil
}

func (argumentMocks) NewResource(args pulumi.MockResourceArgs) (string, resource.PropertyMap, error) {
	return args.Name, args.Inputs, nil
}

func TestConstructorsPreserveSharedArguments(t *testing.T) {
	err := pulumi.RunErr(func(ctx *pulumi.Context) error {
		providerArgs := &busbar.ProviderArgs{Token: pulumi.StringPtr("test-token"), ClientKeyPem: pulumi.StringPtr("test-key")}
		originalProvider := *providerArgs
		configArgs := &busbar.ConfigArgs{Document: pulumi.String(`{"config":{}}`)}
		originalConfig := *configArgs
		options := make([]pulumi.ResourceOption, 1, 4)
		options[0] = pulumi.Protect(true)
		errors := make(chan error, 4)
		var group sync.WaitGroup
		for i := 0; i < 2; i++ {
			group.Add(1)
			go func(i int) {
				defer group.Done()
				_, err := busbar.NewProvider(ctx, fmt.Sprintf("provider-%d", i), providerArgs, options...)
				errors <- err
				_, err = busbar.NewConfig(ctx, fmt.Sprintf("config-%d", i), configArgs, options...)
				errors <- err
			}(i)
		}
		group.Wait()
		close(errors)
		for err := range errors {
			if err != nil {
				return err
			}
		}
		if !reflect.DeepEqual(*providerArgs, originalProvider) || !reflect.DeepEqual(*configArgs, originalConfig) {
			return fmt.Errorf("constructors mutated shared arguments")
		}
		for _, option := range options[len(options):cap(options)] {
			if option != nil {
				return fmt.Errorf("constructors mutated the caller's option backing array")
			}
		}
		return nil
	}, pulumi.WithMocks("project", "stack", argumentMocks{}))
	if err != nil {
		t.Fatal(err)
	}
}

type budgetMocks struct{ argumentMocks }

func (budgetMocks) NewResource(args pulumi.MockResourceArgs) (string, resource.PropertyMap, error) {
	if args.TypeToken == "busbar:index/virtualKey:VirtualKey" {
		budget, ok := args.Inputs["maxBudgetCents"]
		if !ok || !budget.IsNumber() || budget.NumberValue() != 123 {
			return "", nil, fmt.Errorf("maxBudgetCents did not reach the resource registration")
		}
	}
	return args.Name, args.Inputs, nil
}

func TestVirtualKeyBudgetSerialization(t *testing.T) {
	err := pulumi.RunErr(func(ctx *pulumi.Context) error {
		_, err := busbar.NewVirtualKey(ctx, "budgeted", &busbar.VirtualKeyArgs{MaxBudgetCents: pulumi.IntPtr(123)})
		return err
	}, pulumi.WithMocks("project", "stack", budgetMocks{}))
	if err != nil {
		t.Fatal(err)
	}
}

const hookSettings = `{"token":"hook-secret"}`

type hookArgumentMocks struct {
	argumentMocks
	expectProtect bool
}

func (m hookArgumentMocks) NewResource(args pulumi.MockResourceArgs) (string, resource.PropertyMap, error) {
	if args.TypeToken == "busbar:index/hook:Hook" {
		settings, ok := args.Inputs["settings"]
		if !ok || !settings.IsSecret() || !settings.SecretValue().Element.IsString() ||
			settings.SecretValue().Element.StringValue() != hookSettings {
			return "", nil, fmt.Errorf("hook settings must reach registration unchanged and secret")
		}
		secretOutput := false
		for _, name := range args.RegisterRPC.GetAdditionalSecretOutputs() {
			secretOutput = secretOutput || name == "settings"
		}
		if !secretOutput || (m.expectProtect && !args.RegisterRPC.GetProtect()) {
			return "", nil, fmt.Errorf("hook registration lost required resource options")
		}
	}
	return args.Name, args.Inputs, nil
}

func newHookArguments() *busbar.HookArgs {
	return &busbar.HookArgs{
		Kind:     pulumi.String("gate"),
		Module:   pulumi.String("test-hook"),
		Settings: pulumi.StringPtr(hookSettings),
	}
}

func TestHookConstructorsPreserveSharedArguments(t *testing.T) {
	err := pulumi.RunErr(func(ctx *pulumi.Context) error {
		args := newHookArguments()
		original := *args
		for i := 0; i < 2; i++ {
			if _, err := busbar.NewHook(ctx, fmt.Sprintf("hook-reused-%d", i), args); err != nil {
				return err
			}
		}
		errors := make(chan error, 2)
		var group sync.WaitGroup
		for i := 0; i < 2; i++ {
			group.Add(1)
			go func(i int) {
				defer group.Done()
				_, err := busbar.NewHook(ctx, fmt.Sprintf("hook-shared-%d", i), args)
				errors <- err
			}(i)
		}
		group.Wait()
		close(errors)
		for err := range errors {
			if err != nil {
				return err
			}
		}
		if !reflect.DeepEqual(*args, original) {
			return fmt.Errorf("Hook constructor mutated caller-owned arguments")
		}
		return nil
	}, pulumi.WithMocks("project", "stack", hookArgumentMocks{}))
	if err != nil {
		t.Fatal(err)
	}
}

func TestHookConstructorsPreserveOptionBackingArray(t *testing.T) {
	err := pulumi.RunErr(func(ctx *pulumi.Context) error {
		options := make([]pulumi.ResourceOption, 1, 4)
		options[0] = pulumi.Protect(true)
		for i := 0; i < 2; i++ {
			if _, err := busbar.NewHook(ctx, fmt.Sprintf("hook-options-reused-%d", i), newHookArguments(), options...); err != nil {
				return err
			}
		}
		errors := make(chan error, 2)
		var group sync.WaitGroup
		for i := 0; i < 2; i++ {
			group.Add(1)
			go func(i int) {
				defer group.Done()
				_, err := busbar.NewHook(ctx, fmt.Sprintf("hook-options-shared-%d", i), newHookArguments(), options...)
				errors <- err
			}(i)
		}
		group.Wait()
		close(errors)
		for err := range errors {
			if err != nil {
				return err
			}
		}
		for i, option := range options[len(options):cap(options)] {
			if option != nil {
				return fmt.Errorf("Hook constructor mutated caller option backing array at %d", len(options)+i)
			}
		}
		return nil
	}, pulumi.WithMocks("project", "stack", hookArgumentMocks{expectProtect: true}))
	if err != nil {
		t.Fatal(err)
	}
}
