# W2D board_state route strategy comparison

## Strategies compared

1. In-place replacement of `/board/state`
2. New adapter-backed endpoint with staged frontend migration

## Comparison

### Risk to existing consumers

- in-place replacement: high
- new endpoint: low

Why:

- current `/board/state` is a real mounted legacy route
- unknown or admin-side consumers may still rely on the counter contract
- a new endpoint isolates change instead of mutating route meaning in place

### Compatibility complexity

- in-place replacement: high
- new endpoint: medium

Why:

- in-place replacement would need a heavy compatibility layer for request shape,
  response shape, or both
- a new endpoint lets the legacy contract stay as-is during migration

### Testability

- in-place replacement: medium
- new endpoint: high

Why:

- with a new endpoint we can test the adapter-backed contract independently
- we can compare old and new side by side before any UI switch

### Rollback simplicity

- in-place replacement: weak
- new endpoint: strong

Why:

- a new endpoint can be abandoned without restoring the legacy route
- in-place replacement makes rollback more invasive and more error-prone

### Clarity of ownership

- in-place replacement: weak
- new endpoint: strong

Why:

- legacy `/board/state` belongs to the OnlineDay island
- adapter-backed display state belongs to board/display composition logic
- different route surfaces make that ownership clearer

### Speed of delivery

- in-place replacement: only looks faster
- new endpoint: safer actual delivery path

Why:

- in-place replacement would spend time on compatibility preservation
- new endpoint allows smaller, staged slices

## Conclusion

For this codebase, the safer strategy is:

- new adapter-backed endpoint with staged frontend migration

That approach wins on:

- consumer safety
- rollback
- ownership clarity
- bounded incremental delivery

In-place replacement of `/board/state` is not the right default because the
legacy route already has a different meaning than the live UI expectation.
