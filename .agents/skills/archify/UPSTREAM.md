# Archify upstream provenance

- Upstream: https://github.com/tt-a1i/archify
- Release: [v3.0.1](https://github.com/tt-a1i/archify/releases/tag/v3.0.1)
- Pinned commit: 2ab3cae7ac2c2a55d7386ca789d03c4fcd31816c
- Imported package directory: archify/
- License: MIT; see LICENSE and THIRD_PARTY_NOTICES.md.

## SHA-256 checksums of upstream runtime files

Hashes below are for the exact raw files at the pinned commit. They document vendor provenance; Archify still validates generated diagrams separately.

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| assets/template.html | 727,976 | b0b550d644b77cad401bbc4b21375919ef01db45d235122a0ee42b732cb34233 |
| renderers/shared/generated-validators.mjs | 530,554 | 33697207b90a0eb0d0566a1c46eaf3cb58f85cef0f43caeec991017ade34c2b9 |

The vendored assets/template.html has only whitespace-only padding removed from blank lines to satisfy repository whitespace checks. generated-validators.mjs is unchanged from the pinned upstream file.

## Repository packaging

The 300 KB check-added-large-files limit remains in force for all files except the two exact runtime paths listed in .pre-commit-config.yaml. The five pre-rendered HTML examples are omitted because the installed runtime and skill instructions do not reference them; the JSON source examples remain available. Git LFS is not required.
