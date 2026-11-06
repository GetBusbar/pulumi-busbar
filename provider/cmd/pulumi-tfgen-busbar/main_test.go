package main

import (
	"io"
	"os"
	"strings"
	"testing"
)

// Smoke test: the generator entry point builds the provider mapping and hands
// control to tfgen without panicking or exiting. Full generation needs the
// pinned Pulumi CLI for example conversion, so it is exercised by `make build`.
func TestMainStartsGenerator(t *testing.T) {
	arguments := os.Args
	stdout := os.Stdout
	t.Cleanup(func() { os.Args, os.Stdout = arguments, stdout })
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Args = []string{arguments[0], "--help"}
	os.Stdout = writer
	main()
	writer.Close()
	output, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(output), "generates Pulumi package metadata from a Terraform provider") {
		t.Fatalf("usage = %q", output)
	}
}
