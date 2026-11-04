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
