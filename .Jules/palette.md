## 2026-04-10 - Added aria-busy to Loading Buttons
**Learning:** Adding `aria-busy` to buttons experiencing a loading state is a crucial pattern for screen reader accessibility, explicitly signaling that an operation is pending.
**Action:** Ensure all async submission or loading buttons use `aria-busy` state, rather than simply depending on `disabled` state or an unannounced visual spinner.
