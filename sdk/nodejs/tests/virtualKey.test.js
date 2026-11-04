const assert = require("node:assert/strict");
const test = require("node:test");
const pulumi = require("@pulumi/pulumi");
const { VirtualKey } = require("../bin/virtualKey");

pulumi.runtime.setMocks({
    newResource(args) {
        return { id: args.name, state: args.inputs };
    },
    call(args) {
        return args.inputs;
    },
}, "project", "stack", false);

test("virtual key keeps budget and rate limits distinct", { timeout: 10000 }, async () => {
    const key = new VirtualKey("budgeted", { maxBudgetCents: 1000, rpmLimit: 5000 });
    const values = await new Promise(resolve => {
        pulumi.all([key.maxBudgetCents, key.rpmLimit]).apply(resolve);
    });
    assert.deepEqual(values, [1000, 5000]);
});
