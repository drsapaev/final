# Source Synthesis

Use this reference when deciding which behavior from the five source skill styles should guide the task.

## Selection Rule

Start from the clinic context, then borrow the smallest useful behavior from the source style. Do not let a generic design skill override role safety, route semantics, accessibility, or the existing design system.

## Borrowed Strengths

### Frontend Design

Use for:

- forming a clear visual direction
- avoiding generic AI-looking layouts
- improving hierarchy, rhythm, and visual confidence
- making a surface feel intentionally designed

Clinic adaptation:

- distinctive means calm, fast, clinical, and trustworthy
- avoid hero layouts, ornamental typography, aggressive motion, and decorative complexity
- do not make operational screens look like landing pages

### Impeccable

Use for:

- context gates before edits
- writing a shape brief
- making deliberate craft decisions
- keeping a clear evaluation loop

Clinic adaptation:

- the shape brief must include role, workflow, safety risk, current UI layer, out-of-scope contracts, and validation
- approvals are replaced with a small safe patch unless the user explicitly asks for a full redesign
- do not create speculative new design artifacts unless they directly guide implementation

### Web Design Reviewer

Use for:

- browser-first review
- viewport screenshots
- console and network inspection
- verifying fixes against the same route and viewport
- issue reports with severity and source references

Clinic adaptation:

- prioritize staff task completion and critical state clarity over visual novelty
- include route, role, and workflow in every finding
- screenshot evidence is preferred for layout, overlap, clipping, focus, and responsive issues

### Design Audit

Use for:

- audit-only mode
- separating diagnosis from implementation
- P0-P3 phased reports
- reducing clutter before adding polish
- avoiding functional changes during visual work

Clinic adaptation:

- audit findings must identify whether a risk affects clinical workflow, payment, queue, EMR, lab, or reporting
- implementation must be a separate slice unless the user requests immediate fixes
- do not change business logic while doing a visual audit

### UI UX Pro Max

Use for:

- broad rule matrix coverage
- accessibility and touch target checks
- forms, tables, charts, empty states, loading states, responsive behavior, and performance
- systematic standards across a large product surface

Clinic adaptation:

- apply the broad matrix selectively to the touched workflow
- avoid turning a narrow issue into a whole-system rewrite
- use measurable checks where possible: contrast, keyboard path, viewport overflow, target size, build output, and smoke tests

## Conflict Resolution

When source styles disagree:

1. Clinic safety wins.
2. Existing project rules win.
3. Existing canonical components and tokens win.
4. Accessibility wins over aesthetics.
5. Small reversible patch wins over broad redesign.
6. Browser evidence wins over static preference for visual issues.

## Output Hint

When explaining why a recommendation exists, name the borrowed behavior:

- `frontend-design`: visual direction
- `impeccable`: shape brief
- `web-design-reviewer`: browser evidence
- `design-audit`: phased audit
- `ui-ux-pro-max`: broad rule matrix
