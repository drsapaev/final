# HEIC Service Worker Reliability Plan

Date: 2026-05-22

Scope: report-only follow-up for the HEIC upload plan. No runtime code,
service worker code, frontend components, tests, dependencies, Vite config,
backend code, routes, RBAC, upload contracts, or clinical workflow behavior
changed in this PR.

## Why This Plan Exists

The HEIC upload optimization review confirmed that the application bundle
already keeps `heic2any-*` behind a lazy fallback chunk. The remaining concern
is different: `frontend/public/sw.js` currently handles `CONVERT_HEIC` messages
by dynamically importing `https://cdn.skypack.dev/heic2any` inside the service
worker.

That remote import does not inflate the initial app bundle, but it creates a
separate reliability and security decision for clinic deployments, especially
offline-capable or restricted-network installs.

## Files Inspected

- `frontend/public/sw.js`
- `frontend/src/utils/heicConverter.js`
- `frontend/src/components/ui/FileUpload.jsx`
- `frontend/src/components/dermatology/PhotoUploader.jsx`
- `frontend/src/components/ui/__tests__/FileUpload.test.jsx`
- `frontend/src/components/dermatology/__tests__/PhotoUploader.test.jsx`
- `docs/audits/uiux-hard-audit-2026-05-20/heic-upload-optimization-plan-2026-05-22.md`
- `docs/runbooks/CLINIC_RELEASE_ARTIFACT_POLICY.md`
- `docs/runbooks/LOCAL_ONLY_CLINIC_MASTER_CHECKLIST.md`

## Current Behavior

The main-thread converter in `frontend/src/utils/heicConverter.js` follows this
order:

1. Check for service worker support.
2. Send `{ type: 'CONVERT_HEIC', file, quality }` to the active service worker.
3. If service worker conversion fails, fall back to dynamic
   `import('heic2any')` in the app bundle.

The service worker path in `frontend/public/sw.js` currently does this:

```js
const heic2any = (await import('https://cdn.skypack.dev/heic2any')).default;
```

The merged test guards now prove the caller boundary:

- `FileUpload` does not invoke the HEIC fallback dependency for non-HEIC images.
- `FileUpload` still converts HEIC uploads through the shared converter.
- `PhotoUploader` does not invoke HEIC conversion for non-HEIC photos.
- `PhotoUploader` uploads converted JPEG output for HEIC photos.

## Risk Assessment

### P1 - Remote Worker Dependency

The service worker can attempt to load executable code from a third-party CDN at
conversion time. For a clinic system, this is a deployment and supply-chain
decision, not just a performance detail.

Risks:

- restricted clinic networks may block the CDN
- offline installs cannot rely on the CDN
- CDN availability can affect HEIC conversion success
- remote dependency behavior may change outside the approved release artifact
- debugging failures is harder because service worker import failures surface
  through an async message channel

### P2 - Offline Artifact Mismatch

The release runbooks prefer an approved artifact model that can be delivered
online or offline. A service worker conversion path that depends on a live CDN
does not fully match that offline-friendly posture.

### P2 - Dual Conversion Path Ambiguity

The app currently has two conversion dependency paths:

- service worker path: remote CDN import
- app fallback path: local bundled lazy `heic2any-*` chunk

This is useful for resilience, but it should be documented and tested before
changing because the two paths can fail differently.

## Options

### Option A - Keep Current Service Worker CDN Path

Pros:

- no runtime change
- preserves current off-main-thread first attempt
- no risk of changing upload behavior

Cons:

- keeps third-party CDN dependency
- weak offline story
- leaves supply-chain behavior outside the approved build artifact

Decision: acceptable only as a temporary state with documented risk.

### Option B - Disable Service Worker CDN Conversion And Use App Fallback

Pros:

- removes third-party CDN execution from service worker conversion
- uses already bundled lazy `heic2any-*` artifact
- aligns better with approved release artifacts and offline delivery

Cons:

- HEIC conversion may happen on the main thread fallback path
- browser UX and large-file behavior need proof
- service worker message semantics must remain safe and explicit

Decision: likely the smallest future runtime candidate, but only after browser
proof on real HEIC/HEIF input and confirmation that the fallback is acceptable.

### Option C - Local Service Worker Conversion Asset

Pros:

- keeps off-main-thread conversion intent
- avoids remote CDN dependency
- aligns with offline artifact delivery

Cons:

- may require bundler/service worker architecture changes
- can duplicate `heic2any` payload or complicate cache/versioning
- higher implementation risk than Option B

Decision: consider only if browser proof shows main-thread fallback is too slow
or causes visible UI stalls for clinic upload workflows.

## Recommended Next PR

Do not edit `frontend/public/sw.js` yet.

Next smallest safe runtime preparation:

1. Add a focused test or browser proof that service worker conversion failure
   falls back to local app `heic2any` without changing accepted file types,
   output filename, output MIME type, or upload `FormData`.
2. Run a browser smoke on the affected upload flow with service worker available
   and with service worker conversion failure simulated.
3. Only then choose Option B or Option C.

Preferred future PR name:

```text
test(frontend): prove heic service worker fallback path
```

## Runtime Stop Conditions

Stop before editing runtime code if any future implementation would:

- change accepted file types or HEIC/HEIF detection
- change JPEG output type or generated filename semantics
- change `/visits/{visitId}/files`
- change upload `FormData` fields: `file`, `kind`, `visit_id`, `metadata`
- change route registry, RBAC, payment, queue, EMR, lab, or backend behavior
- require a broad service worker rewrite
- require production secrets or live clinic data

## Validation Plan For Future Runtime PR

Minimum local validation:

```powershell
cd frontend
npm.cmd run test:run -- src/components/ui/__tests__/FileUpload.test.jsx src/components/dermatology/__tests__/PhotoUploader.test.jsx
npm.cmd run lint:check
npm.cmd run build
```

Browser proof, if authenticated route access is available:

- `/doctor/dermatology`
- photos tab
- non-HEIC upload path
- HEIC/HEIF upload path
- service worker success or explicit fallback failure path

Report:

- whether remote CDN was contacted
- whether local fallback was used
- upload request shape
- conversion status/error UI
- console errors

## Current Decision

The current merged state is acceptable because non-HEIC workflows do not pay for
HEIC conversion, and HEIC conversion remains guarded. However, the service
worker CDN import should not be considered final for offline-capable clinic
deployment. It needs a separate runtime decision with browser evidence.
