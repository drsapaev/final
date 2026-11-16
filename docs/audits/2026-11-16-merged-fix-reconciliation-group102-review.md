# Code Review group102 — merged fixes #3900–#4098 versus owner tracker

2026-11-16. Pinned main: https://github.com/drsapaev/final/commit/a8531540cfcd1039710a1362c979573820ba56b1. Audit Draft PR #4059, owner issue #4063.
Only review/report/checklist activity. No source edits, new fix PR, runtime tests, gate, merge or deployment.

## Reconciliation snapshot

- Owner before: 416 unique checklist IDs; 82 marked fixed, 334 open.
- Search: 143 merged PRs numbered >=3900, created between Nov 5 and Nov 16 inclusive, latest merged #4098; 60 PR titles contain parseable audit IDs.
- 57 distinct existing UNCHECKED IDs are mentioned in merged PR titles, not automatically fixed.
- 120 unique audit-like IDs are mentioned in merged PR titles but are entirely MISSING as checkboxes from owner #4063. They must be crosschecked against original #3886/#3892/#3961 findings and not bulk-added.
- This group verifies 29 existing unchecked IDs using actual main source, checked-in regression test definitions, merged PR patch/metadata and successful head-specific GitHub CI. Reviewer did not rerun tests.
- After those 29 checks: 416 total, 111 checked, 305 open, assuming no concurrent ledger update.

## Source+test+CI verified (29; one ID counted once)

| Merged PR | Verified ID(s) | Evidence |
|---|---|---|
| [#3924](https://github.com/drsapaev/final/pull/3924) | `DERMAFILE-BE-001` | Exact main=merged source and test blobs; 7/7 PR CI; cross-visit upload denied. |
| [#3927](https://github.com/drsapaev/final/pull/3927) | `DERMAPRICE-BE-001`, `DERMAPRICE-BE-002`, `DERMAPRICE-BE-003`, `DERMAPRICE-BE-004` | Main derm/dental routes and integration regressions present; 9/9 PR CI; orphan-service, actual visit price, reason, Admin list. |
| [#3960](https://github.com/drsapaev/final/pull/3960) | `DOCSCHED-BE-001`, `DOCSCHED-BE-003`, `DOCSCHED-BE-004`, `DOCSCHED-BE-005` | Main schedule-next route and tests preserve replay, clinic day, doctor FK and HH:MM validation; 8/8 PR CI. |
| [#4002](https://github.com/drsapaev/final/pull/4002) | `DISPLAYCALL-BE-001`, `DISPLAYCALL-BE-002`, `DISPLAYCALL-BE-003`, `DISPLAYWS-BE-003` | Main conditional waiting claim, priority and department snapshot; byte-identical test suite; 6/6 PR CI. |
| [#4005](https://github.com/drsapaev/final/pull/4005) | `DISPLAYWS-BE-001`, `DISPLAYWS-BE-002`, `DISPLAYAUTH-BE-001`, `DISPLAYAUTH-BE-002`, `DISPLAYSESSION-BE-002` | Main display/department WebSocket handshake auth+session release and tests; 7/7 PR CI; not public kiosk policy. |
| [#4010](https://github.com/drsapaev/final/pull/4010) | `DISPLAYTARGET-BE-001`, `DISPLAYDELIVERY-BE-001` | Main board targeting and delivery verdicts + regression tests; 7/7 PR CI; DISPLAYPRIVACY-BE-002 already checked. |
| [#4012](https://github.com/drsapaev/final/pull/4012) | `DISPLAYSESSION-BE-001`, `DISPLAYRELAY-BE-002`, `DISPLAYRELAY-BE-003`, `DISPLAYSTATUS-BE-001` | Main Redis subscribe/retry and worker-local status tests; Unified CI success and later PR Quality rerun success. |
| [#4015](https://github.com/drsapaev/final/pull/4015) | `DISPLAYQUICK-BE-001` | Byte-identical merged/main service and clinic-day regression tests; 6/6 PR CI. |
| [#4016](https://github.com/drsapaev/final/pull/4016) | `DISPLAYBANNER-BE-001` | Main real DB banner GET/POST and byte-identical tests; Unified CI and later PR Quality rerun success. |
| [#4022](https://github.com/drsapaev/final/pull/4022) | `QPOSCALL-BE-001` | Main call endpoint/service/two regression suites byte-identical to second fix; 7/7 PR CI; #4013 alone was partial. |
| [#4065](https://github.com/drsapaev/final/pull/4065) | `AUTH-BE-001`, `AUTH-BE-002` | Main UTC-aware session and non-enumerating reset code+tests; 11/11 PR CI. AUTH-BE-005 refuted/reverted, not credited. |

## False-positive exclusions

- NOTIFYLIVEAUTH-BE-001 stays OPEN despite merged #4079. Owner already records PARTIAL_FIX_MERGED_RESIDUAL_OPEN: reused handshake SQLAlchemy Session identity-map may not notice a changed User.is_active/role from another session. Token blacklist test and green CI do not cover it.
- AUTH-BE-005 stays OPEN/pending explicit REFUTED verdict; PR #4065 says the CSRF Secure flag finding was refuted and the attempted code change reverted. It is not a verified source FIX.
- DISPLAYBOOT-FE-001 stays OPEN: merged #4042 was docs/design only.
- REG-FE-006 stays OPEN: #4099 is an unmerged source PR at the pin; #4097 is docs-only handoff.
- QPOSCALL-BE-001 counted once after both #4013 initial fix and #4022 regression repair; #4013 alone is insufficient.
- Prior PR Review Quality metadata failures on #4012 and #4016 were superseded by successful reruns on same head; Unified CI successes were independently retrieved.

## Other already-registered open IDs referenced by merged PRs (NOT certified this pass; 28)

`AUTH-BE-005`, `DENTPRICE-BE-001`, `DERMAAI-FE-001`, `DERMAAI-FE-002`, `DERMAAI-FE-004`, `DERMAAI-FE-005`, `DERMACACHE-FE-001`, `DERMACOMPLETE-FE-002`, `DERMAGALLERY-FE-001`, `DERMAGALLERY-FE-002`, `DERMAGALLERY-FE-003`, `DERMAGALLERY-FE-004`, `DERMAGALLERY-FE-005`, `DERMAGALLERY-FE-006`, `DERMAGALLERY-FE-007`, `DERMAHOTKEY-FE-001`, `DERMAQUEUE-FE-001`, `DERMARX-FE-001`, `DERMARX-FE-002`, `DERMARX-FE-003`, `DERMARX-FE-004`, `DERMAURL-FE-001`, `DERMAURL-FE-002`, `DERMSCHED-FE-001`, `DERMSCHED-FE-002`, `DISPLAYBOOT-FE-001`, `DOCVISIT-BE-003`, `NOTIFYLIVEAUTH-BE-001`

## PR-title ID candidates absent from the owner registry (NOT automatically added; 120)

`AUTH-FE-001`, `CARDAI-FE-001`, `CARDAI-FE-002`, `CARDAPPT-FE-001`, `CARDHIST-FE-001`, `CARDIO-FE-001`, `CARDIO-FE-002`, `CARDIO-FE-003`, `CARDPAT-FE-001`, `CARDPAT-FE-002`, `CARDPAT-FE-003`, `CARDQ-FE-001`, `CARDQ-FE-002`, `CARDSEARCH-FE-001`, `CARDSVC-FE-001`, `CARDSVC-FE-002`, `CARDVISIT-FE-001`, `DENTCHART-FE-001`, `DENTCHART-FE-002`, `DENTCHART-FE-003`, `DENTDATA-FE-001`, `DENTPOCKET-FE-001`, `DOCFLOW-FE-001`, `DOCFLOW-FE-002`, `DOCFLOW-FE-003`, `DOCFLOW-FE-004`, `DOCQ-FE-001`, `DOCQ-FE-002`, `DOCQ-FE-003`, `DOCQ-FE-004`, `ECGPARSER-FE-001`, `ECGPARSER-FE-002`, `ECGPARSER-FE-003`, `ECGVIEW-FE-001`, `ECGVIEW-FE-002`, `ECGVIEW-FE-003`, `ECHO-FE-001`, `EMRAI-FE-001`, `EMRAI-FE-002`, `EMRAI-FE-003`, `EMRAMEND-FE-001`, `EMRAMEND-FE-002`, `EMRAUTOSAVE-FE-001`, `EMRCACHE-FE-001`, `EMRCACHE-FE-002`, `EMRCARD-FE-001`, `EMRCOLLAPSE-FE-001`, `EMRCOMPLAINT-FE-001`, `EMRCONFLICT-FE-001`, `EMRCONFLICT-FE-002`, `EMRCTX-FE-001`, `EMRDIAG-FE-001`, `EMRDIAG-FE-002`, `EMREXAM-FE-001`, `EMRHIST-FE-001`, `EMRHIST-FE-002`, `EMRKEY-FE-001`, `EMRLAB-FE-001`, `EMRLAB-FE-002`, `EMRLAB-FE-003`, `EMRLAB-FE-004`, `EMRLEARN-FE-001`, `EMRLOCK-FE-001`, `EMRORDER-FE-001`, `EMRPHRASE-FE-001`, `EMRPRES-FE-001`, `EMRPRES-FE-002`, `EMRPRES-FE-003`, `EMRPRES-FE-004`, `EMRPROGRESS-FE-001`, `EMRREAD-FE-001`, `EMRRELOAD-FE-001`, `EMRRESTORE-FE-001`, `EMRRESTORE-FE-002`, `EMRSAVE-FE-001`, `EMRSCORE-FE-001`, `EMRSCORE-FE-002`, `EMRSIGN-FE-001`, `EMRSMART-FE-001`, `EMRSTATUS-FE-001`, `EMRTEMPL-FE-001`, `EMRTMPL-FE-001`, `EMRTMPL-FE-002`, `EMRTMPL-FE-003`, `EMRTREAT-FE-001`, `EMRVITAL-FE-001`, `LABAI-FE-001`, `LABAI-FE-002`, `LABAI-FE-003`, `LABEDIT-FE-001`, `LABEDIT-FE-002`, `LABEDIT-FE-003`, `LABEDIT-FE-004`, `LABGUARD-FE-001`, `LABGUARD-FE-002`, `LABGUARD-FE-003`, `LABH-FE-001`, `LABN-FE-001`, `LABN-FE-002`, `LABPRINT-FE-001`, `LABPRINT-FE-002`, `LABPRINT-FE-003`, `LABQ-FE-001`, `LABQ-FE-002`, `LABQ-FE-003`, `LABQ-FE-004`, `LABR-FE-001`, `LABR-FE-002`, `LABR-FE-003`, `LABUX-FE-001`, `LABUX-FE-002`, `QAPI-FE-001`, `QMAN-FE-001`, `QMAN-FE-002`, `TEMPL-FE-001`, `TEMPL-FE-002`, `TEMPL-FE-003`, `TEMPL-FE-004`, `WSQ-FE-001`, `WSQ-FE-002`

## Deferred evidence mapping for fixing-agent / future review

| Merged PR | Listed in owner but still open | Absent from owner |
|---|---|---|
| [#3900](https://github.com/drsapaev/final/pull/3900) | — | DOCQ-FE-001, DOCQ-FE-003, QAPI-FE-001 |
| [#3901](https://github.com/drsapaev/final/pull/3901) | — | CARDQ-FE-001, CARDQ-FE-002, WSQ-FE-001, WSQ-FE-002, QAPI-FE-001 |
| [#3902](https://github.com/drsapaev/final/pull/3902) | — | DOCFLOW-FE-001, DOCFLOW-FE-002, DOCFLOW-FE-003 |
| [#3904](https://github.com/drsapaev/final/pull/3904) | — | QMAN-FE-001, QMAN-FE-002 |
| [#3905](https://github.com/drsapaev/final/pull/3905) | — | DOCQ-FE-002 |
| [#3906](https://github.com/drsapaev/final/pull/3906) | DERMARX-FE-001, DERMARX-FE-002, DERMARX-FE-003, DERMARX-FE-004, DERMACOMPLETE-FE-002, DERMSCHED-FE-001, DERMSCHED-FE-002, DERMAURL-FE-001, DERMAURL-FE-002, DERMACACHE-FE-001, DERMAHOTKEY-FE-001, DERMAQUEUE-FE-001 | — |
| [#3907](https://github.com/drsapaev/final/pull/3907) | — | LABQ-FE-001, LABQ-FE-002, LABQ-FE-003 |
| [#3909](https://github.com/drsapaev/final/pull/3909) | — | LABR-FE-001, LABR-FE-002, LABAI-FE-001 |
| [#3913](https://github.com/drsapaev/final/pull/3913) | — | LABN-FE-001, LABN-FE-002, LABAI-FE-002, LABH-FE-001 |
| [#3914](https://github.com/drsapaev/final/pull/3914) | — | TEMPL-FE-001, TEMPL-FE-002, TEMPL-FE-003, TEMPL-FE-004 |
| [#3915](https://github.com/drsapaev/final/pull/3915) | — | DOCQ-FE-004, DOCFLOW-FE-004, LABQ-FE-004, LABR-FE-003, LABAI-FE-003 |
| [#3916](https://github.com/drsapaev/final/pull/3916) | — | LABEDIT-FE-001, LABEDIT-FE-002 |
| [#3917](https://github.com/drsapaev/final/pull/3917) | — | LABEDIT-FE-003, LABEDIT-FE-004 |
| [#3918](https://github.com/drsapaev/final/pull/3918) | — | LABGUARD-FE-001, LABGUARD-FE-002, LABGUARD-FE-003, LABUX-FE-001, LABUX-FE-002, AUTH-FE-001 |
| [#3921](https://github.com/drsapaev/final/pull/3921) | — | LABPRINT-FE-001, LABPRINT-FE-002, LABPRINT-FE-003 |
| [#3922](https://github.com/drsapaev/final/pull/3922) | — | EMRLAB-FE-001, EMRLAB-FE-002, EMRLAB-FE-003, EMRLAB-FE-004 |
| [#3923](https://github.com/drsapaev/final/pull/3923) | — | EMRAMEND-FE-002, EMRRESTORE-FE-001, EMRRESTORE-FE-002, EMRLOCK-FE-001 |
| [#3929](https://github.com/drsapaev/final/pull/3929) | — | EMRSAVE-FE-001, EMRSIGN-FE-001, EMRRELOAD-FE-001, EMRCONFLICT-FE-001, EMRCONFLICT-FE-002, EMRAMEND-FE-001, EMRAMEND-FE-002 |
| [#3930](https://github.com/drsapaev/final/pull/3930) | — | EMRCTX-FE-001, EMRCACHE-FE-001, EMRCACHE-FE-002, EMRDIAG-FE-001, EMRDIAG-FE-002 |
| [#3938](https://github.com/drsapaev/final/pull/3938) | — | EMREXAM-FE-001, EMRPRES-FE-001, EMRPRES-FE-002, EMRPRES-FE-003, EMRPRES-FE-004, EMRORDER-FE-001, EMRHIST-FE-001, EMRHIST-FE-002 |
| [#3941](https://github.com/drsapaev/final/pull/3941) | — | CARDIO-FE-001, CARDIO-FE-002, CARDIO-FE-003, ECGVIEW-FE-001, ECGVIEW-FE-002, ECGVIEW-FE-003, ECHO-FE-001, CARDSEARCH-FE-001 |
| [#3942](https://github.com/drsapaev/final/pull/3942) | DERMAGALLERY-FE-001, DERMAGALLERY-FE-002, DERMAGALLERY-FE-003, DERMAGALLERY-FE-004, DERMAGALLERY-FE-005, DERMAGALLERY-FE-006, DERMAGALLERY-FE-007, DERMAAI-FE-001, DERMAAI-FE-002, DERMAAI-FE-004, DERMAAI-FE-005 | — |
| [#3943](https://github.com/drsapaev/final/pull/3943) | — | EMRSCORE-FE-001, EMRSCORE-FE-002, EMRCARD-FE-001, EMRREAD-FE-001, EMRCOLLAPSE-FE-001, EMRVITAL-FE-001 |
| [#3953](https://github.com/drsapaev/final/pull/3953) | — | EMRTMPL-FE-001, EMRTMPL-FE-002, EMRTMPL-FE-003, EMRTEMPL-FE-001 |
| [#3957](https://github.com/drsapaev/final/pull/3957) | DOCVISIT-BE-003, DENTPRICE-BE-001 | — |
| [#3963](https://github.com/drsapaev/final/pull/3963) | — | CARDPAT-FE-001, CARDPAT-FE-002, CARDPAT-FE-003, CARDVISIT-FE-001, CARDAPPT-FE-001 |
| [#3965](https://github.com/drsapaev/final/pull/3965) | — | ECGPARSER-FE-001, ECGPARSER-FE-002, ECGPARSER-FE-003 |
| [#3966](https://github.com/drsapaev/final/pull/3966) | — | DENTPOCKET-FE-001, DENTDATA-FE-001, DENTCHART-FE-001, DENTCHART-FE-002, DENTCHART-FE-003 |
| [#3967](https://github.com/drsapaev/final/pull/3967) | — | EMRAI-FE-001, EMRAI-FE-002, EMRAI-FE-003, EMRPROGRESS-FE-001, EMRSMART-FE-001, EMRCOMPLAINT-FE-001, EMRPHRASE-FE-001 |
| [#3970](https://github.com/drsapaev/final/pull/3970) | — | CARDAI-FE-001, CARDAI-FE-002, CARDSVC-FE-001, CARDSVC-FE-002, CARDHIST-FE-001 |
| [#3971](https://github.com/drsapaev/final/pull/3971) | — | EMRAUTOSAVE-FE-001, EMRTREAT-FE-001, EMRLEARN-FE-001 |
| [#3994](https://github.com/drsapaev/final/pull/3994) | — | EMRKEY-FE-001, EMRSTATUS-FE-001 |
| [#4042](https://github.com/drsapaev/final/pull/4042) | DISPLAYBOOT-FE-001 | — |
| [#4065](https://github.com/drsapaev/final/pull/4065) | AUTH-BE-005 | — |
| [#4079](https://github.com/drsapaev/final/pull/4079) | NOTIFYLIVEAUTH-BE-001 | — |

ID extraction here uses PR TITLES only, including shorthand ranges. This is an inventory, not a finding proof or a full review of every diff. Some absent IDs belong to the separate earlier frontend audit; original authority must be inspected before global registry insertion.

## Verification limitations

Source excerpts and tests were read directly from GitHub at pinned main or compared against merged blobs; exact-head CI run results fetched for listed PRs. This pass did not run tests locally or verify live multi-worker/real browser behavior. When a file changed after a merge, current code and test contracts were inspected rather than assuming an unchanged blob. Any later independently demonstrated regression warrants re-opening, not silent preservation.