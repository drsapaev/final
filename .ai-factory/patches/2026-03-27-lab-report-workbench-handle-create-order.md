# LabReportWorkbench handleCreateInstance initialization order

Date: 2026-03-27

## Problem
- `LabReportWorkbench` defined the `handleCreateInstance` callback below an effect that auto-created the only allowed template.
- When the lab queue opened a visit with a single resolved template, the effect attempted to call `handleCreateInstance` before initialization, crashing the workbench with `Cannot access 'handleCreateInstance' before initialization`.

## Fix
- Moved the `handleCreateInstance` `useCallback` above the auto-create `useEffect`.
- Kept the existing behavior intact: the workbench still auto-creates the only allowed template, but now the callback is in scope when the effect runs.

## Verification
- Targeted eslint on `frontend/src/components/laboratory/LabReportWorkbench.jsx` passed.
- Live lab smoke on `/lab-panel` opened visit `748`, entered report `#23`, and `Сохранить черновик` transitioned the instance from `Черновик` to `Заполняется` without a refresh.
- Browser evidence captured at `output/playwright/lab-02-after-save-cycle2.png`.
