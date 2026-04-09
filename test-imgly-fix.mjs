import assert from 'node:assert';
import * as mod from '@imgly/background-removal';

try {
  console.log("Starting unit test for @imgly/background-removal import resolution...");
  
  // Test 1: Ensure module exports removeBackground
  assert.strictEqual(typeof mod.removeBackground, 'function', "removeBackground was not exported as a function!");
  console.log("✓ Verified module manually exports removeBackground successfully");

  // Test 2: Ensure there is NO default export (proving the earlier bug's root cause)
  assert.strictEqual(mod.default, undefined, "Expected no default export, but one was found.");
  console.log("✓ Confirmed no default export exists (Root cause of TypeError verified)");

  console.log("\nAll unit tests passed successfully!");
} catch (err) {
  console.error("Test failed:", err.message);
  process.exit(1);
}
