"use strict";

const addonPath = process.argv[2];
if (!addonPath) {
  throw new Error("usage: diagnose_codex_hid.js <hid-topology-watcher.node>");
}

const addon = require(addonPath);
console.log("exports:", Object.keys(addon));
console.log(
  "findCodexMicroInterfaces:",
  JSON.stringify(addon.findCodexMicroInterfaces(), null, 2),
);
