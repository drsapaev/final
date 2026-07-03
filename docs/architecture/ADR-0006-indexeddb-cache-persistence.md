# ADR-0006: IndexedDB Cache Persistence Layer

**Status:** Proposed
**Date:** 2026-07-04
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-2, ADR-0001 (centralized caching)

## Context

The frontend cache (`frontend/src/core/cache/cacheService.js`) is **in-memory only** — a `Map` that lives in the JavaScript heap:

```javascript
class CacheService {
    constructor() {
        this.cache = new Map();           // ← lost on page reload
        this.tagIndex = new Map();        // ← lost on page reload
        this.stats = { hits: 0, misses: 0, sets: 0, invalidations: 0 };
        this.startAutoCleanup();
    }
}
```

When the user presses F5 (or the browser tab is backgrounded and killed by the OS), **all cached data is lost**. The next page load must re-fetch:
- EMR for the current visit (~2-5 KB, 200ms latency)
- ICD-10 reference table (~50 KB, 500ms latency)
- Services catalogue (~20 KB, 300ms latency)
- Doctor phrases (~10 KB, 200ms latency)
- AI analysis results (~5 KB, 2-5s latency — expensive)

For a doctor seeing 30 patients/day with 5 F5 reloads (accidental or browser-initiated), that is ~150 redundant re-fetches per day per doctor.

### The Problem

1. **UX latency on reload** — every F5 costs 1-2 seconds of "loading..." spinners while reference data re-fetches. Doctors perceive the app as slow.
2. **Backend load** — reference data (ICD-10, services) changes rarely (monthly), but is re-fetched on every reload. For 20 doctors × 5 reloads/day, that is 100 redundant requests/day for data that hasn't changed.
3. **AI cost** — AI analysis results are expensive (LLM call). If a doctor reloads after viewing an AI suggestion, the analysis is re-run. With 30 patients/day × 2 reloads each, that is 60 redundant LLM calls/day per doctor.
4. **Offline gap** — if the network drops momentarily, the in-memory cache is the only cache. Once the tab is reloaded, there is nothing to fall back on.

### What ADR-0001 Established

ADR-0001 (2026-02-06) centralised caching into `cacheService` with:
- Unified `get/set/invalidateByVisit` interface
- Unified TTL and tags (visitId/patientId)
- Forbade local `localStorage` in components for cache

This ADR builds on that foundation by adding a **persistence layer** below the in-memory cache, without changing the `cacheService` API.

## Decision

**Add an IndexedDB-backed persistence layer to `cacheService`, transparent to callers.**

### Principles

1. **In-memory is L1, IndexedDB is L2** — `get()` checks L1 first (fast), then L2 (slower but persistent), then the network. `set()` writes to both L1 and L2 asynchronously.
2. **Caller API unchanged** — `cacheService.get(key)`, `set(key, value, { ttl, tags })`, `invalidateByVisit(visitId)`, etc. all work the same. Callers do not know about IndexedDB.
3. **Selective persistence** — not everything should be persisted. A `persistent: true` flag in `set()` options opts in. Default is `false` (in-memory only) to avoid breaking changes. Reference data and AI analysis set `persistent: true`; EMR data sets `persistent: false` (PHI concern — see below).
4. **PHI protection** — EMR data is NOT persisted to IndexedDB by default. The `persistent` flag for EMR is `false`. If a future audit approves IndexedDB for PHI, we can flip the flag — but the default is conservative.
5. **TTL respected across sessions** — when writing to L2, store `expiresAt` timestamp. On L2 read, check expiry; if expired, delete from L2 and return null.
6. **Tag-based invalidation works on L2 too** — `invalidateByVisit(visitId)` deletes L1 entries tagged `visit:${visitId}` AND L2 entries with the same tag.
7. **No blocking** — L2 writes are async (fire-and-forget). L2 reads are async but `cacheService.get()` remains synchronous by returning `null` if L1 misses and triggering an async L2 backfill via a callback.

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Caller (panel / hook / service)                        │
│     cacheService.get(key) → value | null                │
│     cacheService.set(key, value, { ttl, tags, persistent }) │
└────────────────────────┬────────────────────────────────┘
                         │ (unchanged API)
┌────────────────────────▼────────────────────────────────┐
│  CacheService (existing, in-memory L1)                  │
│    Map<key, { value, expiresAt, tags, persistent }>     │
│                                                         │
│  get(key):                                              │
│    1. L1 hit → return value                             │
│    2. L1 miss → trigger async L2 backfill, return null  │
│                                                         │
│  set(key, value, opts):                                 │
│    1. L1 set (sync)                                     │
│    2. if opts.persistent → L2 set (async, fire-forget)  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  IndexedDBAdapter (new, L2)                             │
│    Database: clinic-cache                               │
│    Store: cache-entries                                 │
│    Index: by-tag, by-expires-at                         │
│                                                         │
│  get(key): Promise<value | null>                        │
│  set(key, value, expiresAt, tags): Promise<void>        │
│  delete(key): Promise<void>                             │
│  deleteByTag(tag): Promise<void>                        │
│  deleteExpired(): Promise<void>                         │
└─────────────────────────────────────────────────────────┘
```

### Migration Plan (4 phases, each a separate PR)

#### Phase 1: Create `IndexedDBAdapter` + unit tests (No production change)
- New file `frontend/src/core/cache/IndexedDBAdapter.js`.
- New file `frontend/src/core/cache/__tests__/IndexedDBAdapter.test.js`.
- Uses the raw IndexedDB API (no dependency on `idb-keyval` or `localforage` — keeps bundle small).
- API: `get(key)`, `set(key, value, expiresAt, tags)`, `delete(key)`, `deleteByTag(tag)`, `deleteExpired()`, `clear()`.
- Database: `clinic-cache`, version 1. Store: `cache-entries` with keyPath `key`, indexes on `tags` (multi-entry) and `expiresAt`.
- **No existing code changes** — `cacheService` continues to work as-is.
- **Estimated diff**: ~250 lines new code (adapter + tests).
- **Testing**: Unit tests with a mock IndexedDB (FakeIndexedDB or manual mock). Cover: set/get, TTL expiry, tag-based delete, bulk expired cleanup, quota-exceeded handling.

#### Phase 2: Add `persistent` flag to `cacheService.set()` + async L2 backfill (Low risk)
- Extend `set(key, value, options)` to accept `options.persistent: boolean` (default `false`).
- When `persistent: true`, fire-and-forget `indexedDBAdapter.set(key, value, expiresAt, tags)`.
- Extend `get(key)`:
  1. L1 hit → return value (unchanged)
  2. L1 miss → schedule async `indexedDBAdapter.get(key)`. If found and not expired, write to L1 and call an optional `onL2Hit(value)` callback. Return `null` synchronously (callers already handle null by fetching from network).
- Add `getAsync(key)` method that returns `Promise<value | null>` — awaits L2 if L1 misses. Callers that can tolerate async (e.g. reference data loaders) use this.
- **No caller changes yet** — the `persistent` flag defaults to `false`, so existing behaviour is preserved.
- **Estimated diff**: ~100 lines in `cacheService.js`, ~50 lines in tests.
- **Testing**: Unit test — `set` with `persistent: true` → L2 has entry → `get` after L1 clear returns null synchronously but triggers L2 backfill → next `get` returns value from L1.

#### Phase 3: Opt-in reference data + AI analysis to `persistent: true` (Medium risk)
- Audit all `cacheService.set` call sites:
  - `CACHE_KEYS.ICD10` (ICD-10 reference) → `persistent: true`
  - `CACHE_KEYS.SERVICES` (services catalogue) → `persistent: true`
  - `CACHE_KEYS.DOCTOR_PHRASES` → `persistent: true`
  - `CACHE_KEYS.AI_ANALYSIS` → `persistent: true` (with shorter TTL — 1 hour instead of 5 min — because AI results are expensive but may change)
  - `CACHE_KEYS.EMR` → `persistent: false` (PHI concern — see below)
- Update callers to use `getAsync(key)` for reference data where possible (avoids the "null on first call, then backfill" pattern).
- **Estimated diff**: ~30 lines across 5-10 call sites.
- **Testing**: Manual — reload page, verify ICD-10/services load instantly from L2 (no network request in DevTools). Verify EMR still fetches from network (not persisted).

#### Phase 4: Add observability + cleanup (Low risk)
- `cacheService.getStats()` now includes L2 stats: `l2Hits`, `l2Misses`, `l2Sets`, `l2Deletes`, `l2SizeBytes`.
- On `cacheService.startAutoCleanup()` (every 60s), also call `indexedDBAdapter.deleteExpired()` to clean up L2.
- Add a DevTools-only debug panel (`?debug=cache`) showing L1 + L2 stats, with a "Clear L2" button.
- **Estimated diff**: ~80 lines.
- **Testing**: Manual — open debug panel, verify L2 stats increment, clear L2 button works.

### PHI Considerations

**EMR data is NOT persisted to IndexedDB** in this ADR. Reasons:

1. **Regulatory** — medical records (EMR) are PHI. Storing them in IndexedDB means they persist on the device after logout. If the device is shared (clinic workstation), the next user could theoretically access them via DevTools.
2. **Session isolation** — when a doctor logs out, `tokenManager.clear()` should clear all PHI. With in-memory cache, this is automatic (page reload clears memory). With IndexedDB, we would need an explicit `indexedDBAdapter.clear()` on logout — easy to forget, easy to break.
3. **Audit trail** — if EMR is in IndexedDB, we need to document when it was written, when it was cleared, and whether the clear succeeded. This is a compliance burden we can defer.

**What IS persisted** (low PHI risk):
- ICD-10 codes (public reference data)
- Services catalogue (public — prices are set, not patient-specific)
- Doctor phrases (doctor-specific, not patient-specific — and only persisted if the doctor is logged in)
- AI analysis results (patient-specific — but the input is complaints/symptoms, not patient identifiers; the output is a suggested diagnosis. We persist with a short TTL and no patient ID in the key.)

If a future audit approves IndexedDB for PHI, we can flip `persistent: true` for EMR in one line — the architecture supports it.

### Acceptance Criteria

- [ ] `frontend/src/core/cache/IndexedDBAdapter.js` exists with the proposed API
- [ ] `IndexedDBAdapter.test.js` covers: set/get, TTL expiry, tag-based delete, bulk expired cleanup, quota-exceeded handling
- [ ] `cacheService.set` accepts `persistent: true` and writes to L2
- [ ] `cacheService.getAsync` returns `Promise<value | null>` and checks L2
- [ ] ICD-10, services, doctor phrases, AI analysis use `persistent: true`
- [ ] EMR uses `persistent: false` (default)
- [ ] `cacheService.getStats()` includes L2 stats
- [ ] `cacheService.clear()` on logout clears both L1 and L2
- [ ] Manual test: reload page, ICD-10 loads instantly from L2 (no network request)
- [ ] Manual test: logout → L2 cleared (verify in DevTools → Application → IndexedDB)

## Consequences

**Плюсы:**
- Reference data survives page reload — 1-2s UX latency → <100ms
- Backend load reduced — ~100 fewer reference-data requests/day for a 20-doctor clinic
- AI cost reduced — reloaded AI analysis reads from L2 instead of re-calling the LLM
- Foundation for offline-first features (e.g. doctor can view last-opened EMR during a network blip — if we later enable `persistent: true` for EMR)
- Caller API unchanged — `cacheService.get/set` work the same

**Минусы:**
- 4-phase migration requires coordination — each phase is a separate PR
- IndexedDB has quirks (quota limits, version migration, Safari private mode) — adapter must handle these gracefully
- L2 reads are async — callers that need sync reads (most UI components) still see `null` on first call after reload, then a re-render when L2 backfills. This is acceptable for reference data (the loading spinner shows briefly) but would be unacceptable for EMR (which is why EMR stays in-memory only).
- Storage size — ICD-10 (~50 KB) + services (~20 KB) + phrases (~10 KB) + AI cache (~100 KB for 20 entries) = ~180 KB. Well within the 5MB+ IndexedDB quota, but should be monitored.
- PHI boundary must be respected — EMR default is `persistent: false`. If a developer accidentally sets `persistent: true` on EMR, PHI persists on the device. CI lint rule should flag this.

## Alternatives Considered

### A. Use `localStorage` instead of IndexedDB
- **Rejected**: `localStorage` is synchronous (blocks the main thread), has a 5MB hard limit (shared across all keys), cannot store structured objects (must JSON.stringify), and throws on quota exceeded (no graceful degradation). IndexedDB is async, has 50MB+ quota per origin, stores structured-clone-able objects directly, and has a quota-exceeded event we can handle.

### B. Use `idb-keyval` or `localforage` library
- **Rejected**: `idb-keyval` is ~1KB but only supports key-value (no indexes, no tag-based delete). `localforage` is ~30KB and supports indexes but pulls in a Promise polyfill and has its own config API that doesn't match our `cacheService` interface. The raw IndexedDB API is ~150 lines and gives us full control over indexes (tags, expiresAt) and cleanup.

### C. Use Service Worker Cache API
- **Rejected**: Cache API is designed for HTTP responses (Request/Response pairs), not arbitrary JS objects. We would have to wrap every cache entry in `new Response(JSON.stringify(value))` — wasteful. Also, Cache API requires a Service Worker registration, which adds complexity.

### D. Wait for offline-first initiative before adding persistence
- **Rejected**: The UX and cost benefits of persisting reference data are independent of offline-first. We can ship this ADR now and build offline-first on top of it later.

## Follow-up

- After Phase 4 is merged, add a CI lint rule that forbids `cacheService.set` with `persistent: true` for keys starting with `emr:` or `patient:`.
- Add `indexedDBAdapter.getUsage()` to report storage size — surface in the DevTools debug panel.
- Consider Phase 5 (future): enable `persistent: true` for EMR after a PHI audit, with explicit `clearOnLogout` enforcement.
- Consider Phase 6 (future): add a Service Worker that serves L2-cached reference data when the network is offline (true offline-first).

## References

- `frontend/src/core/cache/cacheService.js` — current in-memory cache (L1)
- `frontend/src/core/cache/cacheConfig.js` — TTL + tag configuration
- `docs/architecture/ADR-0001-centralized-caching.md` — established the centralized cache
- `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P1-2 — original problem statement
- `frontend/src/utils/tokenManager.js` — `clear()` on logout should trigger L2 clear
- MDN IndexedDB API: https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
