### 💡 What
Added the `aria-invalid` attribute to the underlying native form controls (`<input>`, `<textarea>`, and `<button>`) in the macOS UI component library (`Input.tsx`, `Textarea.tsx`, and `Select.tsx`). The attribute is dynamically set based on the presence of the `error` prop (`aria-invalid={!!error}`).

### 🎯 Why
While these form controls visually indicate an error state (e.g., via red borders or text), screen readers and assistive technologies were not programmatically notified of this invalid state. Adding `aria-invalid` ensures that visually impaired users receive explicit feedback when a form field contains an error or fails validation, significantly improving the form-filling experience.

### 📸 Before/After
*Before:* `aria-invalid` was omitted entirely.
*After:* `aria-invalid="true"` is added when the `error` prop is truthy, and `aria-invalid="false"` when falsy.

### ♿ Accessibility
*   **A11y Improved:** Form controls now correctly broadcast their validation state to assistive technologies, adhering to WCAG guidelines for form accessibility and error identification. Screen readers will now announce "invalid data" or similar when focused on an errored field.

## Summary

- Add `aria-invalid` to `Input.tsx`
- Add `aria-invalid` to `Textarea.tsx`
- Add `aria-invalid` to `Select.tsx`

## Cyclic Execution Evidence

not applicable because this is a styling and accessibility improvement only.

## Contract Impact

not applicable because no API contracts were changed.

## RBAC / Permissions

not applicable because no permissions were modified.

## Notification / Realtime

not applicable because no real-time functionality was altered.

## Frontend Resilience

not applicable because no user-facing panel or frontend data flow changed.

## Scope Gate

not applicable because no new routes were added or denied.

## Validation

not applicable because this is tested via vitest.
