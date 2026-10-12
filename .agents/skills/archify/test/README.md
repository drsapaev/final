# Vendored package tests

Run the package regression with Node.js 18 or newer:

```sh
npm test
```

`npm test` runs two suites:

- `test:portable` uses only Node.js built-ins. It checks the package's `doctor`
  command and renders the synthetic demo into a temporary directory. It does
  not need `npm install`, credentials, network access, or repository product
  services.
- `test:integration` exercises the browser-backed `finalize` pipeline through
  `deliver`, `check`, and `browser-check`, then runs a standalone
  provenance-required `browser-check`.

The browser integration test is skipped locally when `ARCHIFY_CHROME` is unset.
Set `ARCHIFY_CHROME` to a Chrome or Chromium executable to run it. The focused
GitHub Actions workflow locates Chrome, sets `ARCHIFY_CHROME`, and fails if no
browser is available, so this suite is required there and does not silently
skip.

The broader imported upstream suite remains available as source provenance,
but tests that expect the original Archify monorepo root-level `scripts/`,
documentation, or package layout are not the test entry point for this vendored
skill. Local generator checks and the WebM-specific test remain available as
separate package scripts; generator checks need the declared development
dependencies installed, and the WebM test also needs Chrome or Chromium. Run
the full upstream suite only from a matching upstream checkout.
