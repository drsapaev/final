# Clinic Release Artifact Policy

## Purpose
- Define the official delivery format for clinic updates.
- Keep the update path compatible with both internet-connected and local-only clinics.
- Reuse the existing rehearsal and rollback helpers without introducing a second deployment model.

## Approved Release Artifact

The official update unit for a clinic deployment is an **approved release artifact**.

It contains:
- `release.bundle`
  - a git bundle for the approved release ref
- `release-manifest.json`
  - release name
  - bundled ref
  - commit SHA
  - creation timestamp
  - artifact type metadata

The artifact is the same for both delivery modes:
- online delivery from GitHub Releases or another approved release store
- offline delivery by copying the artifact file directly to the clinic host

## Official Source Of Truth

The release approval source of truth is:
- the approved release ref selected by release engineering
- the `release-manifest.json` embedded in the artifact built from that ref

Clinic operators must deploy only artifacts that:
- came from the approved release source
- can be imported cleanly into the target clinic host repo
- produce a concrete `IMPORTED_RELEASE_REF`

## Build Workflow

Build the approved release artifact from a clean repo checkout:

```bash
python3 ops/vps/scripts/build_release_artifact.py --ref <approved-release-ref>
```

Expected output:
- `ARTIFACT_FILE=...`
- `ARTIFACT_RELEASE_NAME=...`
- `ARTIFACT_RELEASE_REF=...`
- `ARTIFACT_COMMIT_SHA=...`

Default output directory:
- `output/release-artifacts/`

## Online Delivery

For internet-connected clinics:
- publish the artifact zip as the approved release asset
- download it on the clinic host
- import it into the local repo
- deploy it through the normal update rehearsal path

## Offline Delivery

For local-only clinics:
- copy the same artifact zip to the clinic host by USB, LAN share, or another offline transfer method
- import it into the local repo
- deploy it through the same update rehearsal path

No clinic-specific rebuild is allowed for offline delivery.

## Import And Deploy Workflow

Import the artifact:

```bash
python3 ops/vps/scripts/import_release_artifact.py --artifact-file /path/to/clinic-release.zip
```

Expected output:
- `IMPORTED_RELEASE_REF=refs/clinic-releases/<release-name>`

Then deploy and rehearse the imported release:

```bash
UPDATE_RELEASE_REF=refs/clinic-releases/<release-name> \
ROLLBACK_REF=<known-good-baseline> \
python3 ops/vps/scripts/run_update_rehearsal.py
```

This keeps the operational path unchanged:
- backup
- deploy
- migrate
- health
- smoke
- rollback on failure

## Host Install And Workstation Access

The approved release artifact is used only for the **host machine**:
- backend
- PostgreSQL
- storage
- lifecycle helpers
- release checkout

Workstations do not consume release artifacts directly.
Their default access model is:
- browser
- LAN URL
- standard user login inside the already deployed clinic host

Any thin launcher remains optional convenience only.

## Acceptance Criteria
- One artifact format serves both online and offline clinics.
- The artifact can be imported into a local repo without internet access.
- The imported ref can be used by the existing update rehearsal and rollback tooling.
- The clinic host remains the only machine that deploys or updates backend/database state.
