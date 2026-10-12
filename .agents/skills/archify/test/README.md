# Vendored package tests

Run the isolated package regression with Node.js 18 or newer:

```sh
npm test
```

This portable smoke suite uses only Node.js built-ins. It checks the package's
`doctor` command and renders the synthetic demo into a temporary directory; it
does not need `npm install`, credentials, network access, or repository product
services.

The broader imported upstream suite remains available as source provenance,
but tests that expect the original Archify monorepo root-level `scripts/`,
documentation, browser harness, or package layout are not the test entry point
for this vendored skill. Local generator checks and the WebM-specific test
remain available as separate package scripts; generator checks need the declared
development dependencies installed, and the WebM test also needs Chrome or
Chromium. Run the full upstream suite only from a matching upstream checkout.
