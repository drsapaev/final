# Anti-Patterns

Use this reference to block common mistakes in clinic UI/UX work.

## Clinic-Specific Anti-Patterns

- Making an operational screen look like a landing page.
- Hiding critical patient, payment, queue, lab, or EMR state below decorative content.
- Using AI-assistant visuals that compete with confirmed clinical facts.
- Presenting pending, failed, and successful states with similar visual weight.
- Making destructive or irreversible actions look like routine actions.
- Using clever wording where staff need direct task labels.
- Adding motion that delays repeated staff workflows.

## Design-System Anti-Patterns

- Creating a new token system for one patch.
- Adding a new UI component family without checking existing primitives.
- Mixing canonical components and MUI in a new surface without a migration reason.
- Copying styles from one page into another instead of extracting a proven pattern.
- Treating historical design docs as stronger than current source and tests.
- Replacing many files to remove a small visual inconsistency.

## Layout Anti-Patterns

- Cards inside cards for page sections.
- Toolbars that only work at one viewport.
- Text that depends on fixed English-length labels.
- Wide desktop layouts that stretch forms across the full screen.
- Mobile screens where the submit/recovery action is hidden under sticky elements.
- Scroll containers inside scroll containers without clear boundaries.

## Accessibility Anti-Patterns

- Icon-only buttons without accessible names.
- Color-only status.
- Missing focus ring or focus clipped by overflow.
- Placeholder as the only label.
- Top-only form errors on long forms.
- Modal close behavior without focus restore.
- Disabled buttons without context when the user can recover.

## Data And Workflow Anti-Patterns

- Changing route ownership while polishing UI.
- Changing API payloads during visual cleanup.
- Changing queue/payment/EMR/lab state logic while improving layout.
- Adding frontend role rules instead of using existing route/auth patterns.
- Removing a "redundant" confirmation that exists for audit or safety.
- Moving clinical identifiers out of immediate view.

## Visual Polish Anti-Patterns

- One-note palette across the whole product.
- Decorative gradients as the main visual structure.
- Large hero-scale headings inside dense panels.
- Excessive shadows and elevation.
- Unusual fonts.
- Dense icon decoration without workflow meaning.
- Animation that distracts from tables, forms, or status changes.

## Review Questions

Before accepting a UI patch, ask:

- Did we preserve staff task speed?
- Did we preserve route, role, and state contracts?
- Did we improve clarity without adding a new system?
- Can this be validated on the affected route?
- Would a registrar/doctor/cashier/lab user understand the next action immediately?
