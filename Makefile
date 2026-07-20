PACK            := busbar
ORG             := getbusbar
PROJECT         := github.com/$(ORG)/pulumi-$(PACK)
PROVIDER        := pulumi-resource-$(PACK)
TFGEN           := pulumi-tfgen-$(PACK)
NODE_MODULE_NAME:= @getbusbar/pulumi-$(PACK)
PYPI_PACKAGE    := pulumi_$(PACK)

VERSION         ?= 0.0.1

WORKING_DIR     := $(shell pwd)
PROVIDER_PATH   := provider
SCHEMA_PATH     := $(PROVIDER_PATH)/cmd/$(PROVIDER)/schema.json
SCHEMA_EMBED    := $(PROVIDER_PATH)/cmd/$(PROVIDER)/schema-embed.json

GOPATH          := $(shell go env GOPATH)
BIN             := $(GOPATH)/bin

LDFLAGS         := -X $(PROJECT)/provider/pkg/version.Version=$(VERSION)

.PHONY: default ensure tfgen provider build_sdks build_nodejs build_python build_go \
        clean lint schema drift help

default: provider build_sdks

# ---------------------------------------------------------------------------
# Build the tfgen and provider binaries.
# ---------------------------------------------------------------------------

tfgen:: ## Build the pulumi-tfgen-busbar binary
	cd $(PROVIDER_PATH) && go build -o $(BIN)/$(TFGEN) -ldflags "$(LDFLAGS)" ./cmd/$(TFGEN)

schema:: tfgen ## Generate the Pulumi Package Schema (schema.json)
	$(BIN)/$(TFGEN) schema --out $(PROVIDER_PATH)/cmd/$(PROVIDER)
	cp $(SCHEMA_PATH) $(SCHEMA_EMBED)

provider:: schema ## Build the pulumi-resource-busbar plugin binary (embeds the schema)
	cd $(PROVIDER_PATH) && go build -o $(BIN)/$(PROVIDER) -ldflags "$(LDFLAGS)" ./cmd/$(PROVIDER)

# ---------------------------------------------------------------------------
# Generate SDKs from the schema.
# ---------------------------------------------------------------------------

build_sdks:: build_nodejs build_python build_go ## Generate all language SDKs

build_nodejs:: tfgen ## Generate the TypeScript/JavaScript SDK
	$(BIN)/$(TFGEN) nodejs --out sdk/nodejs

build_python:: tfgen ## Generate the Python SDK
	$(BIN)/$(TFGEN) python --out sdk/python

build_go:: tfgen ## Generate the Go SDK
	$(BIN)/$(TFGEN) go --out sdk/go

# ---------------------------------------------------------------------------
# Housekeeping.
# ---------------------------------------------------------------------------

ensure:: ## Download Go module dependencies
	cd $(PROVIDER_PATH) && go mod download
	cd $(PROVIDER_PATH)/shim && go mod download
	cd sdk && go mod download

lint:: ## Vet the provider module
	cd $(PROVIDER_PATH) && go vet ./...

drift:: build ## Regenerate everything and fail if the tree changed (CI drift check)
	git diff --exit-code

build:: provider build_sdks ## Alias: build provider + all SDKs

clean:: ## Remove generated schema artifacts
	rm -f $(SCHEMA_PATH)

help:: ## Show this help
	@grep -hE '^[a-zA-Z_-]+::?.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
