package main

import (
	"encoding/json"
	"flag"
	"os"
	"os/exec"
	"testing"
)

// The plugin entry point exits the process, so it runs in a child copy of the
// test binary. The child shares the coverage directory when coverage is on.
func TestMainDumpsProviderInfo(t *testing.T) {
	if os.Getenv("BUSBAR_PROVIDER_MAIN") == "1" {
		os.Args = []string{"pulumi-resource-busbar", "-get-provider-info"}
		main()
		return
	}
	command := exec.Command(os.Args[0], "-test.run=^TestMainDumpsProviderInfo$")
	command.Env = append(os.Environ(), "BUSBAR_PROVIDER_MAIN=1")
	if directory := flag.Lookup("test.gocoverdir"); directory != nil && directory.Value.String() != "" {
		command.Env = append(command.Env, "GOCOVERDIR="+directory.Value.String())
	}
	output, err := command.Output()
	if err != nil {
		t.Fatalf("provider main: %v", err)
	}
	var info struct {
		Name      string                     `json:"name"`
		Resources map[string]json.RawMessage `json:"resources"`
	}
	if err := json.Unmarshal(output, &info); err != nil {
		t.Fatalf("provider info %q: %v", output, err)
	}
	if info.Name != "busbar" || len(info.Resources) != 3 {
		t.Fatalf("provider info = %s %d resources", info.Name, len(info.Resources))
	}
}
