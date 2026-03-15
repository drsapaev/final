## Recommended next step

Continue with another review-first duplicate/unmounted residue slice.

## Why

This cleanup remained low-risk, but it also showed a new pattern: some residue candidates may now be fully unmounted on both the service side and the endpoint side. Those should still be split into separate cleanup slices instead of deleted in bulk.

## Suggested direction

Choose the next candidate only after checking:

1. live imports
2. route mounting
3. whether the artifact is a service-side duplicate or a dead endpoint artifact
