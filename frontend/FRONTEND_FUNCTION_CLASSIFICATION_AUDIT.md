# Frontend Function Classification Audit

Static audit date: 2026-05-15  
Repository: `C:\final`  
Branch: `audit-frontend-function-classification`  
Scope: frontend classification/documentation only. No runtime application code was changed.

## 1. Executive Summary

The frontend is mature enough to have a real routing SSOT, route contract tests, role-home selection, macOS UI primitives, AppState primitives, and targeted e2e coverage for routes, auth, queue, payment, and visual/a11y smoke. It is not yet mature enough to treat broad frontend cleanup as low risk. The app still has very large role panels, several UI layers in active use, duplicated status/queue/payment interpretation in page code, and many backend-contract-sensitive screens where frontend display code can accidentally become policy.

Biggest risks:

- Route, auth, and role behavior are centralized, but any change to `routeRegistry.js`, `routeSelectors.js`, `routeGuards.jsx`, `App.jsx`, or role-home logic is high to critical risk.
- Queue, payment, EMR, lab, file upload, patient data, diagnosis, prescription, and AI-assisted copy are backend-contract and clinical/payment sensitive.
- Monolith files make safe review hard: `DentistPanelUnified.jsx` (3804 lines), `RegistrarPanel.jsx` (3585), `AppointmentWizardV2.jsx` (3427), `AdminPanel.jsx` (2837), `DermatologistPanelUnified.jsx` (2549), and `CardiologistPanelUnified.jsx` (2253).
- UI layer fragmentation remains: canonical `components/ui/macos` exists, but `Modern*`, MUI, Tailwind-like class strings, page-local inline styles, `frontend/src/design-system`, and older native UI primitives are still present.
- App-state UI is partially migrated. `AppLoading`, `AppEmpty`, and `AppError` exist, but search still found many local loading/error/empty patterns.

Safest next steps:

- Keep docs-only and audit-only work in `frontend_docs_only`.
- Migrate one AppState slice at a time, starting with small non-clinical pages already identified in `frontend/APP_STATE_MIGRATION_BACKLOG.md`.
- Treat role panels, queue, payment, EMR, lab, auth, file upload, and patient medical data as dedicated PRs with explicit validation.
- Do not mass-refactor role panels. No mass refactor is safe here without a separate execution plan and contract tests.

Verified statically:

- Read required docs and source anchors.
- Ran required search inventories or PowerShell equivalents where Unix `find` was unavailable.
- Inventoried 72 canonical routes, 45 page files at requested depth, 455 component files at requested depth, 0 `frontend/src/panels`, 63 frontend unit/spec files, 16 e2e files, and 690 JS/TS/JSX/TSX source files.

Live browser smoke:

- Not run. This report is static-code audit only.

## 2. Product Function Map

| Zone | Purpose | Key files | Owner/SSOT visible | Risk | Backend-contract sensitivity | Recommended validation | Safe PR strategy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Public / Marketing UI | Landing and public presentation. | `frontend/src/pages/Landing.jsx`, `frontend/src/pages/landingContent.js`, `frontend/src/components/landing/*`, `frontend/src/PublicApp.jsx` | Route registry owner `marketing.landing`; public app bridge exists but `main.jsx` mounts `App.jsx`. | Low/Medium | Low, unless links route into auth/queue/payment callbacks. | `git diff --check`, frontend lint/build for runtime copy/layout work, landing e2e when layout changes. | Copy/layout PRs only; do not touch app-shell or route guards. |
| 2. Auth / Onboarding | Login, setup, password change, 2FA, profile/security entry. | `LoginFormStyled.jsx`, `Login.jsx`, `Setup.jsx`, `ChangePasswordRequired.jsx`, `TwoFactorManager.jsx`, `ForgotPassword.jsx`, `PhoneVerification.jsx`, `stores/auth.js`, `api/client.js`, `api/interceptors.js` | IAM/auth is backend-owned; route registry maps `/login` to `LoginFormStyled`; `Login.jsx` is now a wrapper. | Critical | Very high: token, refresh, 2FA, route redirects, password-change behavior. | auth/unit tests, route contract tests, route smoke, manual auth smoke if changed. | One auth surface per PR; no token/RBAC semantic changes in visual PRs. |
| 3. App Shell / Navigation | Header, sidebar, route chrome, app framing. | `App.jsx`, `HeaderNew.jsx`, `components/ui/macos/Sidebar.jsx`, `routeSelectors.js`, `routeRegistry.js` | Route chrome from `getRouteChromeState`; sidebar presets from `SIDEBAR_PRESETS`. | High | High for role visibility and redirects. | route contract tests, route ownership tests, e2e route smoke, visual smoke. | One shell concern per PR; no route or role changes bundled with visual polish. |
| 4. Routing / Route SSOT | Canonical routes, aliases, roles, shells, nav metadata. | `frontend/src/routing/routeRegistry.js`, `routeSelectors.js`, `routeGuards.jsx`, route tests. | `ROUTE_REGISTRY` is SSOT; `constants/routes.js` delegates to selectors. | Critical | High: auth, role access, setup redirect, internal-demo flag. | `routeContract.test.js`, `routeOwnershipEnforcement.test.js`, `rbacRouteParity.test.js`, route smoke. | Dedicated route PR only; table-driven review; no opportunistic cleanup. |
| 5. Role Workspaces | Staff operational homes. | `AdminPanel.jsx`, `RegistrarPanel.jsx`, `DoctorPanel.jsx`, `CashierPanel.jsx`, `LabPanel.jsx`, `PatientPanel.jsx`, specialty panels. | Route owner fields: `admin.*`, `clinical.*`; panel internals also own query-tab workflows. | High/Critical | High: role-specific endpoints, queues, payments, patient data. | role-specific smoke, route/role checks, frontend tests/build. | One panel slice per PR; avoid changing query-tab semantics. |
| 6. Clinical-heavy flows | Visit, EMR, diagnosis, prescription, specialty workflows. | `VisitDetails.jsx`, `components/emr-v2/*`, `DoctorPanel.jsx`, specialty panels, dental/derma/cardio components. | Backend owns clinical state; EMR hooks/services mediate client behavior. | Critical | Very high: clinical record, autosave, AI suggestions, prescriptions. | EMR/unit tests, clinical smoke, route/role checks, backend parity awareness. | Dedicated clinical PR with acceptance criteria; visual-only slices must preserve payloads. |
| 7. Payment-sensitive flows | Payment widgets, cashier, payment callbacks, provider settings. | `CashierPanel.jsx`, `PaymentSuccess.jsx`, `PaymentCancel.jsx`, `components/payment/*`, `PaymentDialog.jsx`, `PaymentProviderSettings.jsx`, `usePayments.js`, `services/payment.js` | Backend owns payment status; frontend displays/requests receipts and marks paid through APIs. | Critical | Very high: payment status, receipt, invoice, mark-paid endpoints. | payment e2e, targeted manual callback smoke, frontend tests/build. | Separate visual payment-result PRs from payment-state/API PRs. |
| 8. Queue-sensitive flows | Public QR join, queue boards, queue admin, registrar queue. | `QueueJoin.jsx`, `DisplayBoardUnified.jsx`, `ModernQueueManager.jsx`, `QueueTable.jsx`, `useQueueManager.js`, `api/queue.js`, `services/queue.js`, registrar queue code. | Backend queue service owns allocation/status; frontend must preserve `queue_time` and queue profile mapping. | Critical | Very high: fairness, `queue_time`, queue profile/doctor mapping. | queue unit tests, queue-system e2e, route smoke, manual queue smoke for UI changes. | One queue surface per PR; no frontend-side allocation logic changes. |
| 9. Patient-facing flows | Patient panel, pickup view, public queue patient entry. | `PatientPanel.jsx`, `PatientPickupView.jsx`, `QueueJoin.jsx`, `MobilePatientDashboard.jsx`, patient components. | Backend owns patient medical data and access rules. | Critical | Very high: PHI/medical data, pickup permissions, lab result display. | patient tests, route/role checks, manual smoke with seeded safe data. | Visual/state-only slices; no access or data-shape changes. |
| 10. Admin / Owner operations | Admin dashboard, users, doctors, services, clinic, settings, security, integrations. | `AdminPanel.jsx`, `components/admin/*`, `AnalyticsPage.jsx`, `Settings.jsx`, `Audit.jsx` | `admin.*` route owners; backend owns user/role/catalog/audit/security contracts. | High/Critical | High: users, doctors, billing, queue settings, activation, audit. | admin tests, route contract tests, frontend build, targeted smoke. | Prefer small admin component PRs; avoid full `AdminPanel.jsx` rewrites. |
| 11. Lab operations | Lab queue, templates, report blank/results workbench. | `LabPanel.jsx`, `components/laboratory/*`, `api/labReporting.js`, `services/print.js` | Lab reporting API/backend owns report templates/instances/results. | Critical | Very high: lab state, report status, patient lab results, print payloads. | lab component tests, lab workflow smoke, frontend build. | Dedicated lab PRs only; keep queue/report status merges unchanged unless tested. |
| 12. EMR / Doctor workflows | Doctor queue, EMR, visit lifecycle, autosave, history/conflicts. | `components/emr-v2/*`, `hooks/useEMR*.js`, `useVisitLifecycle.js`, `DoctorPanel.jsx`, specialty panels. | Backend owns clinical visit state; frontend owns editing UX and autosave coordination. | Critical | Very high: diagnosis/prescription/history/AI medical text. | EMR tests, prescription accessibility test, visit lifecycle tests, manual clinical smoke. | One section or helper per PR; never mix EMR behavior and UI migration casually. |
| 13. AI-assisted features | AI chat, assistant, suggestions, analytics, clinical text. | `components/ai/*`, `hooks/useAI*.js`, `api/mcpClient.js`, EMR AI sections, `admin-ai-settings`. | Backend/provider contract owns outputs; route tests assert AI sidebar disclaimer. | Critical for clinical AI; High for admin settings. | High: AI disclaimers, medical copy, provider config, token use. | AI tests, route disclaimer tests, manual copy review. | Preserve "draft, not diagnosis" framing; no medical assertion changes in UI-only PRs. |
| 14. UI infrastructure / design system | Shared primitives, tokens, styles, legacy design systems. | `components/ui/macos/*`, `theme/macos-tokens.css`, `styles/macos.css`, `frontend/src/design-system`, `styles/*`, `theme/*` | `frontend/DESIGN_SYSTEM.md` UI Layer Contract makes macOS layer canonical. | Medium/High | Usually low, but shared primitive changes can affect all app pages. | AppState/macOS tests, frontend lint/test/build, visual smoke for primitives. | Add/change one primitive at a time; no parallel UI framework. |
| 15. App-state UI: loading/error/empty | Loading, empty, and error primitives and migrations. | `components/ui/macos/AppState.jsx`, `APP_STATE_MIGRATION_BACKLOG.md`, pages/components with local states. | AppState primitives are canonical for new app-state UI. | Medium; High in role/clinical/payment/queue contexts. | Low for simple pages; high where state implies domain status. | AppState tests plus target page tests/smoke. | Start low-risk pages; do not migrate high-risk panels until reviewed. |
| 16. Internal / utility / demo pages | Demos, showcase, test pages, compatibility surfaces. | `MacOSDemoPage.jsx`, `ButtonShowcase.jsx`, `IntegrationDemo.jsx`, `PaymentTest.jsx`, `MediLabDemo.jsx`, `CSSTestPage.jsx` | Route group `internal-demo`; gated by `VITE_ENABLE_INTERNAL_DEMO`. | Low generally; payment/lab demos can be Medium/High. | Low unless demo uses real payment/lab endpoints. | route contract test for internal-demo disabled state; no live smoke unless changed. | Keep admin-gated and out of nav; avoid demo code leaking into production flows. |
| 17. Tests / QA / E2E | Unit, route, parity, e2e, smoke coverage. | `frontend/src/**/__tests__`, `frontend/src/test/*`, `frontend/e2e/*` | Test ownership follows feature area; route contract tests are route SSOT guard. | Low for test-only; High if tests encode wrong contracts. | Medium/High for parity and e2e contract tests. | targeted test command; no runtime changes. | Test-only PRs are safe when assertions match current source truth. |
| 18. Agent/docs/skills surfaces | Repo guidance and frontend audit docs. | `AGENTS.md`, `.agents/skills/clinic-frontend-design/*`, `frontend/*.md`, `.cursorrules` | Repo instructions and clinic skill are operational guidance. | Low | None unless docs instruct unsafe behavior. | `git diff --check`, marker `rg`. | Docs-only PRs; do not update runtime code. |

## 3. Route Registry and Navigation Audit

Canonical route subsystem:

- `routeRegistry.js` defines 72 routes, route groups, shells, auth types, lifecycle metadata, owner metadata, legacy aliases, home routes, and `SIDEBAR_PRESETS`.
- `routeSelectors.js` normalizes roles, maps profile roles/usernames to home routes, checks route access, builds admin/clinical nav, resolves aliases, and derives route chrome.
- `routeGuards.jsx` enforces setup redirects, public/authenticated/role-scoped access, internal-demo disablement, legacy redirects, and system error pages.
- `App.jsx` renders `ROUTE_REGISTRY.map(...)` and `legacyRedirectFrom` aliases through `LegacyRouteRedirect`.
- `PublicApp.jsx` exists but `main.jsx` mounts `App.jsx`; `PublicApp.jsx` has direct `/`, `/login`, `/old-login`, `/health`, and wildcard bridge routes. `/old-login` now renders `Login.jsx`, which wraps `LoginFormStyled`.

Route classifications:

- Public: 14 routes, including landing, login, setup/health utilities, queue join, queue/display boards, payment callbacks, and error pages.
- Authenticated: 3 routes: password change, profile, and clinical security.
- Role-scoped: 55 routes.
- Admin group: 35 routes. Most are Admin-only; `admin-file-management` also allows Doctor.
- Clinical group: 16 routes.
- Internal/demo/dev: 6 routes, all `internal-demo`, admin-gated, and route tests assert disabled unless explicitly enabled.
- Payment-sensitive: `/payment/success`, `/payment/cancel`, `/cashier`, `/admin/finance`, `/admin/payment-providers`, `/admin/benefit-settings`, and internal payment test.
- Queue-sensitive: public queue join, display/queue board, queue admin settings/cabinets/display, registrar queue, and queue-related role panels.
- Clinical-heavy: doctor/specialty panels, visit details, EMR components, patient pickup.
- Route exists but sidebar missing/contextual: `/admin/benefit-settings`, `/admin/wizard-settings`, `/admin/payment-providers`, `/admin/clinic-settings`, `/admin/queue-settings`, `/admin/telegram-settings`, `/admin/display-settings`, `/admin/user-select`, `/patient`, `/clinical/profile`, `/clinical/security`, `/clinical/security/two-factor`, `/clinical/visits/:id`, `/clinical/pickup/:patientId`.
- Sidebar points to route: admin/default sidebar routes are derived from registry nav metadata; 37 visible nav routes.
- Sidebar points to missing route: no route-based missing target found from registry-derived admin/default nav. Query-based role panel sidebars use tab IDs, not route paths; those need panel-specific review.
- Orphan/possibly unused or compatibility surfaces: `PublicApp.jsx` is not mounted by `main.jsx`; route registry aliases are canonical in `App.jsx`. Keep it as a compatibility/secondary entry surface until ownership is clarified.
- `/support` navigation from the previous audit was not found in current `PaymentCancel.jsx` search.

| Route | Component | Role/Access | Product zone | Risk | Notes |
| --- | --- | --- | --- | --- | --- |
| `/` | `Landing` | public | Public / Marketing UI | Low | id `landing`; owner `marketing.landing`; no app shell. |
| `/login` | `LoginFormStyled` | public | Auth / Onboarding | Critical | id `login`; alias `/old-login`; auth contract. |
| `/change-password-required` | `ChangePasswordRequired` | authenticated | Auth / Onboarding | Critical | Password lifecycle utility. |
| `/health` | `Health` | public | Internal / utility | Medium | Health/audit-adjacent utility. |
| `/queue/join` | `QueueJoin` | public | Queue-sensitive flows | Critical | Public QR/clinic-wide queue join; alias `/pwa/queue`. |
| `/queue/join/:token` | `QueueJoin` | public | Queue-sensitive flows | Critical | Tokenized queue join. |
| `/payment/success` | `PaymentSuccess` | public | Payment-sensitive flows | Critical | Callback; reads `payment_id`, payment status, receipt. |
| `/payment/cancel` | `PaymentCancel` | public | Payment-sensitive flows | Critical | Callback; displays `payment_id`. |
| `/queue-board` | `DisplayBoardUnified` | public | Queue-sensitive flows | Critical | Public display board. |
| `/display-board` | `DisplayBoardUnified` | public | Queue-sensitive flows | Critical | Public display board alias-like canonical route. |
| `/display-board/:role` | `DisplayBoardUnified` | public | Queue-sensitive flows | Critical | Role-param display board. |
| `/setup` | `Setup` | public | Auth / Onboarding | High | Setup precedence redirects protected routes before initialization. |
| `/admin` | `AdminPanel` | Admin | Admin / Owner operations | High | Admin home; visible nav. |
| `/admin/analytics` | `AnalyticsPage` | Admin | Admin / Owner operations | High | Alias `/analytics`; analytics/payment metrics. |
| `/admin/webhooks` | `AdminPanel` | Admin | Admin / Owner operations | High | Admin integration route. |
| `/admin/reports` | `AdminPanel` | Admin | Admin / Owner operations | High | Reports surface. |
| `/admin/system` | `AdminPanel` | Admin | Admin / Owner operations | High | System operations. |
| `/admin/cloud-printing` | `AdminPanel` | Admin | Admin / Owner operations | High | Printing integration. |
| `/admin/medical-equipment` | `AdminPanel` | Admin | Admin / Owner operations | High | Equipment operations. |
| `/admin/graphql-explorer` | `AdminPanel` | Admin | Internal / utility | High | Admin-only API explorer. |
| `/admin/users` | `AdminPanel` | Admin | Admin / Owner operations | Critical | User management/RBAC-adjacent. |
| `/admin/doctors` | `AdminPanel` | Admin | Admin / Owner operations | High | Doctor catalog/user linkage. |
| `/admin/services` | `AdminPanel` | Admin | Admin / Owner operations | High | Service catalog; queue/payment adjacency. |
| `/admin/queue-cabinet-management` | `AdminPanel` | Admin | Queue-sensitive flows | Critical | Queue cabinet/status configuration. |
| `/admin/patients` | `AdminPanel` | Admin | Patient-facing flows | Critical | Patient data. |
| `/admin/appointments` | `AdminPanel` | Admin | Admin / Owner operations | High | Appointment operations. |
| `/admin/all-free` | `AdminPanel` | Admin | Payment-sensitive flows | High | All-free approval/payment-adjacent. |
| `/admin/benefit-settings` | `AdminPanel` | Admin | Payment-sensitive flows | Critical | Hidden route; billing benefits. |
| `/admin/wizard-settings` | `AdminPanel` | Admin | Admin / Owner operations | High | Hidden route; registrar wizard settings. |
| `/admin/payment-providers` | `AdminPanel` | Admin | Payment-sensitive flows | Critical | Hidden route; provider config. |
| `/admin/clinic-management` | `AdminPanel` | Admin | Admin / Owner operations | High | Clinic ops. |
| `/admin/clinic-settings` | `AdminPanel` | Admin | Admin / Owner operations | High | Hidden route; clinic settings. |
| `/admin/queue-settings` | `AdminPanel` | Admin | Queue-sensitive flows | Critical | Hidden route; queue config. |
| `/admin/ai-settings` | `AdminPanel` | Admin | AI-assisted features | High | Visible nav; route tests assert AI disclaimer. |
| `/admin/telegram-settings` | `AdminPanel` | Admin | Admin / Owner operations | High | Hidden route; integration config. |
| `/admin/display-settings` | `AdminPanel` | Admin | Queue-sensitive flows | Critical | Hidden route; queue display settings. |
| `/admin/integrations/telegram` | `TelegramManager` | Admin | Admin / Owner operations | High | Alias `/telegram-integration`. |
| `/admin/notifications` | `EmailSMSManager` | Admin | Admin / Owner operations | High | Alias `/notifications`; notification contracts. |
| `/admin/phone-verification` | `AdminPanel` | Admin | Auth / Onboarding | High | Phone verification workflow. |
| `/admin/activation` | `AdminPanel` | Admin | Admin / Owner operations | High | Alias `/activation`; licensing/activation. |
| `/admin/finance` | `AdminPanel` | Admin | Payment-sensitive flows | Critical | Finance/payment data. |
| `/admin/settings` | `Settings` | Admin | Admin / Owner operations | High | Alias `/settings`. |
| `/admin/security` | `AdminPanel` | Admin | Auth / Onboarding | Critical | Security/RBAC-adjacent settings. |
| `/admin/audit` | `Audit` | Admin | Admin / Owner operations | High | Alias `/audit`; audit contract. |
| `/admin/advanced-users` | `UserManagement` | Admin | Admin / Owner operations | Critical | Alias `/advanced-users`; user lifecycle. |
| `/admin/file-management` | `FileManager` | Admin, Doctor | Patient-facing flows | Critical | Alias `/file-management`; file upload/private data. |
| `/admin/user-select` | `UserSelect` | Admin | Admin / Owner operations | High | Hidden route; user switching. |
| `/registrar` | `RegistrarPanel` | Admin, Registrar | Role Workspaces | Critical | Alias `/registrar-panel`; queue/payment/patient flow. |
| `/doctor` | `DoctorPanel` | Admin, Doctor | Role Workspaces | Critical | Alias `/doctor-panel`; clinical/AI/queue. |
| `/cashier` | `CashierPanel` | Admin, Cashier | Payment-sensitive flows | Critical | Alias `/cashier-panel`. |
| `/lab` | `LabPanel` | Admin, Lab | Lab operations | Critical | Alias `/lab-panel`; lab queue/report state. |
| `/patient` | `PatientPanel` | Admin, Registrar, Doctor | Patient-facing flows | Critical | Hidden nav; patient medical data. |
| `/doctor/cardiology` | `CardiologistPanelUnified` | Admin, Doctor, cardio | Clinical-heavy flows | Critical | Alias `/cardiologist`; EMR/queue/AI. |
| `/doctor/dermatology` | `DermatologistPanelUnified` | Admin, Doctor, derma | Clinical-heavy flows | Critical | Alias `/dermatologist`; EMR/photos/AI. |
| `/doctor/dentistry` | `DentistPanelUnified` | Admin, Doctor, dentist | Clinical-heavy flows | Critical | Alias `/dentist`; dental chart/diagnoses/plans. |
| `/clinical/scheduler` | `Scheduler` | Admin, Doctor, Registrar | Role Workspaces | High | Alias `/scheduler`; scheduling contract. |
| `/clinical/appointments` | `Appointments` | Admin, Registrar | Role Workspaces | High | Alias `/appointments`. |
| `/clinical/search` | `Search` | Admin, Doctor, Registrar, cardio, derma, dentist | Role Workspaces | High | Alias `/search`; patient search. |
| `/clinical/profile` | `UserProfile` | authenticated | Auth / Onboarding | High | Hidden route; alias `/profile`; profile API. |
| `/clinical/security` | `SecurityPage` | authenticated | Auth / Onboarding | Critical | Hidden route; alias `/security`. |
| `/clinical/security/two-factor` | `TwoFactorManager` | Admin, Doctor | Auth / Onboarding | Critical | Hidden route; alias `/security-settings`. |
| `/clinical/visits/:id` | `VisitDetails` | Admin, Doctor, Registrar, cardio, derma, dentist | EMR / Doctor workflows | Critical | Hidden route; alias `/visits/:id`. |
| `/clinical/pickup/:patientId` | `PatientPickupView` | Admin, Registrar, Cashier, Lab, Doctor, cardio, derma, dentist | Patient-facing flows | Critical | Hidden route; alias `/pickup/:patientId`. |
| `/internal-demo/medilab` | `MediLabDemo` | Admin | Internal / utility / demo pages | Low/Medium | Admin-gated internal demo; many legacy aliases. |
| `/internal-demo/macos` | `MacOSDemoPage` | Admin | Internal / utility / demo pages | Low | Admin-gated demo. |
| `/internal-demo/integration` | `IntegrationDemo` | Admin | Internal / utility / demo pages | Low | Admin-gated demo. |
| `/internal-demo/payment-test` | `PaymentTest` | Admin | Internal / utility / demo pages | Medium | Payment-adjacent internal test; alias `/payment/test`. |
| `/internal-demo/css-test` | `CSSTestPage` | Admin | Internal / utility / demo pages | Low | CSS test route. |
| `/internal-demo/buttons` | `ButtonShowcase` | Admin | Internal / utility / demo pages | Low | Button showcase; alias `/buttons`. |
| `/unauthorized` | `UnauthorizedPage` | public | Auth / Onboarding | Medium | System auth error page. |
| `/forbidden` | `ForbiddenPage` | public | Auth / Onboarding | Medium | System auth error page. |
| `/not-found` | `NotFoundPage` | public | Internal / utility | Low | System not-found page. |

## 4. Role Workflow Audit

| Role | Entry route(s) | Main components/pages | Key workflows | API/backend dependency visible | UI risks | SSOT risk | Recommended tests/smoke | Next safe PR candidates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Admin / Owner | `/admin`, many `/admin/*` routes | `AdminPanel.jsx`, `components/admin/*`, `AnalyticsPage`, `Settings`, `Audit`, `UserManagement` | Users, doctors, services, queue settings, billing, activation, audit, integrations, AI settings. | `useAdminData`, `useUsers`, `useDoctors`, `usePatients`, `useAppointments`, `useFinance`, `api/client`, many admin endpoints. | Monolithic panel, many inline styles, mixed UI layers, destructive admin actions. | High: backend owns roles, permissions, service catalog, payment/queue settings. | route contract tests, admin navigation e2e, targeted admin component tests, build. | AppState migration in `Activation.jsx`; admin utility empty/error states; docs-only CI mapping. |
| Registrar | `/registrar` | `RegistrarPanel.jsx`, `AppointmentWizardV2.jsx`, `PaymentManager`, `ModernQueueManager`, dialogs, `EnhancedAppointmentsTable` | Appointments, patient aggregation, wizard checkout, payments, cancellation, queue display, CSV/export. | `api/client`, `api/visits`, `api/queue`, direct fetch to registrar endpoints, payment mark-paid endpoints. | Very large file; queue/payment/patient logic interleaved with UI; `queue_time` sorting is explicit. | Critical: backend owns payment status, queue entries, visit status, patient records. | registrar e2e, queue/payment smoke, route/role checks, targeted tests around aggregation. | Only small visual state slices after dedicated review; do not start with monolith refactor. |
| Doctor | `/doctor` | `DoctorPanel.jsx`, `DoctorQueuePanel`, `AIAssistant`, `AIChatWidget`, schedule/queue hooks | Doctor dashboard, queue, patients, appointments, AI assistant, reports. | `useDoctorQueue`, token manager, API runtime origin, notification center. | Clinical/AI interactions and older native UI usage. | Critical: backend owns visits, queue, medical record state. | doctor route smoke, queue panel tests, AI disclaimer tests. | Button/empty-state polish inside non-clinical dashboard card only. |
| Cashier | `/cashier` | `CashierPanel.jsx`, `PaymentWidget`, `CashPaymentModal`, `RefundRequestsTable`, `usePayments` | Payment list/search, cash payments, receipts, refund requests. | `usePayments`, `services/payment`, panel print service, backend payment APIs. | Payment-state UI can imply financial truth. | Critical: payment status and receipt state backend-owned. | payment e2e, cashier smoke, frontend build. | Payment result visual-only AppState/copy PR; no mark-paid behavior. |
| Lab | `/lab` | `LabPanel.jsx`, `LabQueueWorkbench`, `LabReportWorkbench`, `LabTemplateWorkbench`, `api/labReporting` | Lab queue, template selection, report creation/history, print. | `fetch /registrar/queues/today`, `labReportingApi`, print service, token manager. | Lab queue/report status merge is sensitive. | Critical: backend owns lab templates, instances, statuses, patient results. | lab component tests, lab workflow smoke, build. | Docs/test-only first; tiny loading state in lab-only component after review. |
| Patient | `/patient`, `/clinical/pickup/:patientId`, `/queue/join/:token` | `PatientPanel.jsx`, `PatientPickupView.jsx`, `QueueJoin.jsx`, `FamilyRelationsCard` | Patient appointment/results/profile display, pickup/lab result view, public queue registration. | `/patients`, `/lab`, `/registrar/visits`, queue APIs. | Medical data visibility, public form language/accessibility, local status badges. | Critical: backend owns patient data and access policy. | patient/profile tests, queue join accessibility tests, route/role smoke. | PatientPanel empty-state polish only; no pickup access/data changes. |
| Cardio / Derma / Dentist | `/doctor/cardiology`, `/doctor/dermatology`, `/doctor/dentistry` | `CardiologistPanelUnified`, `DermatologistPanelUnified`, `DentistPanelUnified`, specialty components, EMR container. | Specialty queues, visits, EMR, dental chart, photos, procedures, AI, prescriptions. | Queue service, print service, `api/client`, `api/runtime`, EMR hooks, specialty utilities. | Largest clinical files; AI and diagnosis/prescription surfaces. | Critical: clinical state and specialty workflow backend-owned. | specialty smoke, EMR tests, prescription a11y test, queue tests. | Dedicated review docs or tests before runtime changes. |
| Support / Dev tools | Internal demo routes, GraphQL explorer, button/CSS demos | `MediLabDemo`, `MacOSDemoPage`, `IntegrationDemo`, `PaymentTest`, `CSSTestPage`, `ButtonShowcase`, `GraphQLExplorer` | Internal demos, API exploration, UI showcases. | Depends by route; GraphQL/payment demos can hit backend-like surfaces. | Demo code can be mistaken for production pattern. | Medium: keep internal-demo flag and admin gate. | route contract tests for internal-demo disabled state. | Docs labels and demo isolation checks. |
| Missing/gap roles discovered | No standalone `Owner` route role; `receptionist` and `nurse` are aliases; specialist roles are lower-case route roles. | `ROLE_ALIASES`, `ROLE_HOME_PRIORITY`, `constants/routes.js` role options. | Owner appears as product responsibility, not as route role. | Backend role system likely owns canonical role names. | Mistyping role case can break access. | Critical for RBAC parity. | route contract tests, `rbacRouteParity.test.js`. | Docs-only clarification; no role rename. |

## 5. Risk Classification Matrix

Risk definitions used in this audit:

- Low: docs, skills, demo/showcase, small static utility, static copy, non-runtime markdown.
- Medium: shared UI primitives, small runtime pages, visual-only changes, loading/error/empty state migration, landing sections.
- High: login/auth screens, route registry/selectors/guards, sidebar/app shell, role panels, patient panel, queue UI, payment UI, admin operations.
- Critical: auth/RBAC behavior, queue domain logic, payment status/payment API behavior, EMR clinical state, lab workflow, diagnosis/prescription/AI medical copy, file upload, patient medical data.

| Frontend area | Risk | Why |
| --- | --- | --- |
| `frontend/FRONTEND_FUNCTION_CLASSIFICATION_AUDIT.md` | Low | Docs-only, no runtime semantics. |
| `.agents/skills/clinic-frontend-design/*` | Low | Agent guidance, but can affect future execution quality. |
| `frontend/DESIGN_SYSTEM.md` | Low | Docs-only UI guidance. |
| Landing/marketing components | Low/Medium | Mostly public copy/layout; medium if route links or auth CTAs change. |
| `LoginFormStyled.jsx`, `api/client.js`, `api/interceptors.js`, `stores/auth.js` | Critical | Token, refresh, login, 2FA, redirect, profile state. |
| `routeRegistry.js`, `routeSelectors.js`, `routeGuards.jsx`, `App.jsx` route rendering | Critical | Route/RBAC/setup/alias behavior. |
| Header/sidebar/app shell | High | Cross-role navigation and layout. |
| `AdminPanel.jsx` and admin components | High/Critical | Admin operations, user/role/payment/queue settings. |
| `RegistrarPanel.jsx` and `AppointmentWizardV2.jsx` | Critical | Patient, queue, payment, visit, appointment contracts interleaved. |
| Doctor and specialty panels | Critical | Clinical state, EMR, prescriptions, AI, queue. |
| `CashierPanel.jsx` and payment components | Critical | Payment status, receipts, mark-paid/refunds. |
| `QueueJoin.jsx`, `DisplayBoardUnified.jsx`, queue services/hooks | Critical | Public queue, fairness, queue profile mapping, `queue_time`. |
| `LabPanel.jsx` and laboratory workbenches | Critical | Lab report status/results/templates/print. |
| `PatientPanel.jsx`, `PatientPickupView.jsx`, patient hooks | Critical | Patient medical data and pickup access. |
| `components/ui/macos/*` | Medium/High | Canonical primitives; broad blast radius if changed. |
| `frontend/src/design-system/*` | Medium | Legacy/compatibility; new app work should not expand it. |
| MUI theme/components | Medium/High | Existing legacy dependency; new app usage discouraged. |
| AppState migrations | Medium, High/Critical in sensitive screens | Safe on small pages; risky when loading/error state implies domain status. |
| Frontend tests/e2e | Low/Medium | Test-only safe, but route/parity tests encode product contract. |

## 6. SSOT and Backend-Contract Sensitivity

Frontend must not become SSOT for these areas:

| Area | Backend-owned logic | Frontend display-only logic | Risky duplicated logic found by search/static review | Parity needs |
| --- | --- | --- | --- | --- |
| Auth/RBAC | Token issuance, refresh, profile roles, permissions, 2FA, password change. | Login form state, error display, route redirect UI. | Role normalization and route access mirror backend role names; `useRoles` has fallback role options. | Route contract, RBAC parity, auth smoke. |
| Queue status | Queue creation, allocation, status, duplicate rules, `queue_time`, doctor/profile mapping. | Display queue position, sort/render entries from backend fields. | Registrar and QueueJoin have local normalization/sorting and profile/tag fallback logic. | Queue tests, queue e2e, manual queue smoke. |
| Payment status | Payment provider, status, receipt, mark-paid/refund behavior. | Show payment callback details and buttons. | Cashier/registrar/payment result pages interpret payment states locally. | Payment e2e, targeted callback smoke. |
| EMR/diagnosis/prescription | Visit record, clinical content, prescriptions, history, conflicts. | Form rendering, local draft UX, autosave indicator. | EMR hooks and specialty panels coordinate autosave/navigation/AI suggestions. | EMR tests, prescription a11y, clinical smoke. |
| Lab state | Report templates, result instances, status, PDF/print payload truth. | Workbench UI, local filters, print trigger. | `LabPanel` merges queue entries with lab instances and resolves template payloads. | Lab tests, lab smoke. |
| Patient data | Patient identity, access rights, visit/lab history. | Patient cards, empty states, pickup rendering. | `PatientPickupView` local role/view handling and status badges. | Patient tests, role access smoke. |
| Audit/health/activation | Backend health/audit/activation status. | Display diagnostics and statuses. | Health/audit pages are safer but still display backend-owned statuses. | Target page tests; no broad suite for docs-only. |
| AI assistant/disclaimer | AI provider behavior and medical safety policy. | Disclaimers, draft labels, prompt surfaces. | AI assistant appears in doctor/specialty/admin; route tests assert sidebar disclaimer. | AI tests and copy review. |

Classifications:

- Backend-owned logic: auth/RBAC, queue allocation/status, payment status/API behavior, EMR/lab/patient medical data, audit records, activation truth, AI output meaning.
- Frontend display-only logic: layout, visual state, labels, filters that do not change payloads, route chrome rendering from registry metadata.
- Risky duplicated logic: role fallback options, queue profile/tag fallback, payment status labels/colors, visit/lab status badges, patient aggregation/sorting, EMR/specialty status helpers.
- API contract dependencies: `api/client.js`, `api/interceptors.js`, `api/queue.js`, `api/labReporting.js`, `api/visits.js`, `services/payment.js`, `services/queue.js`, direct fetches in role panels.
- Route/role contract dependencies: `routeRegistry.js`, `routeSelectors.js`, `routeGuards.jsx`, `constants/routes.js`, route tests, RBAC parity tests.
- Frontend-backend parity needs: auth, route roles, queue profiles, payment statuses, lab statuses, EMR visit lifecycle, patient pickup access.

## 7. UI Layer Usage Audit

| UI layer | Where used | Status | Recommendation |
| --- | --- | --- | --- |
| `frontend/src/components/ui/macos` | App shell, many admin/role pages, AppState, payment result pages, form/table primitives. | Canonical for new clinic app work. | Prefer exported primitives from `index.js`; inspect before creating anything. |
| `frontend/src/theme/macos-tokens.css` | Imported in `main.jsx` and `App.jsx`; token base for macOS UI. | Canonical token layer for current app direction. | Preserve; use for app work. |
| `frontend/src/theme/macosTheme.jsx` | Providers in app/public app/tests. | Canonical provider for macOS theme. | Preserve; do not replace in docs-only/runtime-light PRs. |
| `frontend/src/styles/macos.css` | Imported globally; macOS style foundation. | Canonical global style layer for current app direction. | Safe to touch only in dedicated primitive/style PRs. |
| `frontend/src/design-system` | Legacy components, tests, stories, docs. | Allowed existing legacy; deprecated for new app work. | Do not expand for clinic operations unless explicitly scoped. |
| MUI (`@mui/*`, theme files) | Existing theme files and several components including `PaymentTest`, `Dashboard`, dental/cardiology/lab/patient components. | Existing legacy/compatibility. | Do not add new MUI app usage; migrate only one safe surface at a time. |
| Tailwind-like utilities/class strings | `Activation.jsx`, many pages/components, older utility class patterns. | Allowed existing legacy. | Do not expand; replace with macOS primitives in safe migrations. |
| Page-local inline styles | Very broad usage, especially monolith panels and auth. | Existing compatibility; high-risk in monoliths. | Avoid adding large new inline style systems; do not mass rewrite. |
| `Modern*` components | Dialogs, filters/forms/buttons/layout/nav, `RegistrarPanel`, `ModernQueueManager`, statistics, notifications. | Legacy/compatibility. | Leave unless target slice owns it; new app work should prefer macOS. |
| `components/ui/native` | `DoctorPanel`, example/native components. | Legacy/compatibility. | Do not expand; migrate only after panel-specific review. |
| `AppLoading`, `AppEmpty`, `AppError` | `Health`, `Audit`, `Activation`, `Appointments`, `Search`, `PatientPickupView`, `ServiceAuditHistory`, tests. | Canonical app-state primitives. | Use for new page/panel loading/error/empty states; preserve domain semantics. |
| `MacOSEmptyState`, `MacOSLoadingSkeleton`, `MacOSAlert` | Admin and role components, direct primitive usage. | Allowed but lower-level than AppState for page state. | Gradually migrate simple app-level state to AppState; keep skeletons for local layout placeholders. |

## 8. Loading / Empty / Error State Audit

Search found repeated state patterns in 329 files under pages/components:

- Inline loading text or full-page loading blocks.
- `loading`, `isLoading`, `busy`, `setLoading`, and local spinner markup.
- Direct `Skeleton`, `MacOSLoadingSkeleton`, or CSS spinner usage.
- `setError`, `setErr`, local error boxes, toast-only API errors, and red utility/error classes.
- Table empty rows using `colSpan`.
- Direct `MacOSEmptyState` use where `AppEmpty` may be more canonical for app-level state.
- Existing `AppLoading`, `AppEmpty`, and `AppError` in 10 files.

Top future migration candidates:

| File | Current pattern | Recommended primitive | Risk | Effort | Acceptance criteria |
| --- | --- | --- | --- | --- | --- |
| `frontend/src/pages/Activation.jsx` | Already uses AppState plus utility classes; good pilot follow-up. | Keep/normalize `AppLoading`, `AppError`, `AppEmpty`. | Low | S | No API/role/filter changes; state UI remains canonical. |
| `frontend/src/pages/Appointments.jsx` | Error/empty/table state patterns, already has AppState references. | `AppError`, `AppEmpty`; cautious `AppLoading`. | Medium | S | Filters/table semantics unchanged. |
| `frontend/src/pages/Search.jsx` | Local search error/no-results state, AppState references. | `AppError`, `AppEmpty`. | Low | S | Search API/navigation unchanged. |
| `frontend/src/pages/PatientPickupView.jsx` | Patient/lab loading and error states. | `AppLoading`, `AppError`; avoid domain status change. | Medium/High | S | Pickup token/access and patient/lab data unchanged. |
| `frontend/src/components/admin/AdminSection.jsx` | Shared loading/error wrapper. | `AppLoading`, `AppError` or wrapper. | Medium | M | Component API and consumers unchanged. |
| `frontend/src/components/admin/ServiceAuditHistory.jsx` | Direct skeleton/empty state. | `AppLoading`, `AppEmpty`. | Low | S | Service history fetch/render unchanged. |
| `frontend/src/components/admin/ActivationSystem.jsx` | Loading and message-driven errors. | `AppLoading`; only load failure to `AppError`. | Low/Medium | S | Activation actions unchanged. |
| `frontend/src/components/admin/AISettings.jsx` | Loading and provider message states. | `AppLoading`; retain action messages. | Medium | S | AI provider behavior/copy unchanged. |
| `frontend/src/components/admin/QueueLimitsManager.jsx` | Queue loading and empty/status state. | `AppLoading`, `AppEmpty`. | High | M | Queue limit calculations/API unchanged. |
| `frontend/src/components/payment/PaymentManager.jsx` | Payment loading/empty/error patterns. | `AppLoading`, `AppEmpty`, `AppError` in a payment-specific slice. | Critical | M | Payment API/status behavior unchanged. |

High-risk states that should not be migrated yet without dedicated review:

- `RegistrarPanel.jsx` payment/queue states.
- `QueueJoin.jsx` public queue state and language.
- `CashierPanel.jsx` payment status states.
- `LabPanel.jsx` report/queue state merge.
- EMR v2 autosave/conflict/AI states.
- Specialty panels and dental diagnosis/treatment plan states.

## 9. Component and Page Monolith Audit

| File | Lines | Product zone | Why risky | Split? | First safe slice | What not to change |
| --- | ---: | --- | --- | --- | --- | --- |
| `frontend/src/pages/DentistPanelUnified.jsx` | 3804 | Clinical-heavy / dentist | Dental chart, diagnosis, treatment plans, EMR, queue, AI, print. | Yes, but only with dedicated plan. | Extract/cover one non-clinical display subpanel or docs inventory first. | Diagnosis, dental chart semantics, pricing, queue, EMR payloads. |
| `frontend/src/pages/RegistrarPanel.jsx` | 3585 | Registrar / queue / payment | Appointment, queue, payment, cancellation, patient aggregation, `queue_time` sorting. | Yes, but high risk. | State/readability audit or one isolated modal state after tests. | Payment status, queue sorting, cancellation endpoint selection. |
| `frontend/src/components/wizard/AppointmentWizardV2.jsx` | 3427 | Registrar wizard | Patient/cart/queue/payment/service selection in one file. | Yes, later. | Test-only characterization or low-risk presentation substep. | Checkout payloads, queue entries, service normalization. |
| `frontend/src/pages/AdminPanel.jsx` | 2837 | Admin / owner | Many admin modules, navigation, data hooks, UI layers. | Yes, gradually. | One admin utility state or route-switch display slice. | Navigation sections, user/role/payment/queue behavior. |
| `frontend/src/pages/DermatologistPanelUnified.jsx` | 2549 | Clinical-heavy / derma | Photos, procedures, EMR, AI, print, queue. | Yes, later. | Non-domain visual cleanup in a small card. | Photos/clinical data, prescriptions, queue, AI medical copy. |
| `frontend/src/pages/CardiologistPanelUnified.jsx` | 2253 | Clinical-heavy / cardio | Queue, ECG/echo, EMR, AI, print. | Yes, later. | Dedicated review of queue/EMR boundaries first. | ECG/echo/EMR status and backend payloads. |
| `frontend/src/components/tables/EnhancedAppointmentsTable.jsx` | 2189 | Shared appointment table | Shared table/context menu impacts registrar/admin/clinical. | Maybe, with tests. | Add/adjust a test before UI changes. | Sorting, actions, context menu semantics. |
| `frontend/src/components/admin/DepartmentManagement.jsx` | 1615 | Admin operations | Admin CRUD and likely backend contracts. | Maybe. | Loading/error state only after endpoint review. | Department CRUD payloads. |
| `frontend/src/pages/QueueJoin.jsx` | 1610 | Public queue | Public entry, token/session, specialist merge, queue events, locale. | Yes, but critical. | Language/copy audit or test-only PR. | Session token, queue submission payload, `queueUpdated` events. |
| `frontend/src/components/ai/RiskAssessment.jsx` | 1554 | AI clinical | Medical AI risk assessment forms/copy. | Yes. | Disclaimer/copy review only. | Medical scoring claims or payloads. |
| `frontend/src/pages/CashierPanel.jsx` | 1482 | Payment | Payment/refund/receipt behavior. | Maybe. | Receipt visual polish with tests. | Payment status, mark-paid/refund endpoints. |
| `frontend/src/pages/DoctorPanel.jsx` | 1449 | Clinical role | Doctor queue, AI, native UI, role notifications. | Maybe. | Non-clinical dashboard empty state. | Queue/visit/AI behavior. |
| `frontend/src/components/ai/SmartScheduling.jsx` | 1439 | AI scheduling | AI and scheduling suggestions. | Maybe. | Docs/test first. | Scheduling decisions or AI claims. |
| `frontend/src/components/admin/ServiceCatalog.jsx` | 1348 | Admin catalog | Service catalog, queue tags, audit/history, batch edit. | Maybe. | `ServiceAuditHistory` AppState migration. | Service code/category/queue tag logic. |
| `frontend/src/pages/AnalyticsPage.jsx` | 1007 | Admin analytics | Revenue, appointment conversion, provider metrics. | Maybe. | Empty/error state slice. | Metric definitions and API mapping. |

## 10. CI/CD Category Mapping for Frontend

| Category | Path examples | Required checks | Optional checks | When parity/e2e/manual smoke is required |
| --- | --- | --- | --- | --- |
| `frontend_docs_only` | `frontend/*.md`, report docs | `git diff --check`, marker `rg` | docs link check | Never, unless docs claim runtime proof. |
| `frontend_tests_only` | `frontend/src/**/__tests__`, `frontend/e2e/*` | Targeted test command if runnable, `git diff --check` | build if helpers changed | Required when tests encode route/RBAC/payment/queue contracts. |
| `frontend_ui_primitives` | `components/ui/macos/*`, `styles/macos.css`, `theme/macos-*` | frontend lint/test/build, primitive tests | visual smoke/storybook | Required if shared primitive affects auth/role/payment/queue pages. |
| `frontend_runtime_page` | Small pages like `Health`, `Audit`, `Activation`, `Search` | frontend lint/test/build or targeted tests | browser smoke | Manual smoke if page uses backend data. |
| `frontend_role_panel` | `AdminPanel`, `RegistrarPanel`, `DoctorPanel`, `CashierPanel`, `LabPanel`, specialty panels | targeted tests, build, route/role checks | panel e2e/manual smoke | Always for role panel behavior or layout changes. |
| `frontend_contract_sensitive` | `api/*`, `services/*`, `hooks/use*`, route files | targeted unit/contract tests, build | parity tests | Required when endpoint, payload, status, or role access changes. |
| `frontend_clinical_sensitive` | `components/emr-v2/*`, doctor/specialty panels, diagnosis/prescription components | EMR/clinical tests, build | manual clinical smoke | Always for clinical data/copy/payload changes. |
| `frontend_payment_sensitive` | `CashierPanel`, `PaymentSuccess`, `PaymentCancel`, `components/payment/*`, payment hooks/services | payment tests/e2e, build | manual callback smoke | Always when payment status, receipt, mark-paid, or provider behavior changes. |
| `frontend_queue_sensitive` | `QueueJoin`, `DisplayBoardUnified`, queue hooks/services, registrar queue | queue tests/e2e, build | manual queue smoke | Always when queue status, sorting, allocation, profile mapping, or events change. |
| `frontend_e2e_sensitive` | `frontend/e2e/*`, route/auth/queue/payment e2e | targeted Playwright test when practical | full e2e | Required when changing e2e specs or flows they cover. |
| `frontend_deps` | `frontend/package.json`, lockfiles | install/build/test policy | security/audit | Always requires broader checks; not allowed in this PR. |
| `skills_changed` | `.agents/skills/*` | YAML/frontmatter/readability check | skill dry-run | Required if skill changes execution behavior. |

## 11. Validation Matrix

| Function class | Recommended validation |
| --- | --- |
| Docs-only | `git diff --check`; marker `rg`; verify docs link if edited. |
| Skills-only | frontmatter/openai.yaml validation; `git diff --check`; no runtime tests unless skill includes scripts. |
| UI primitive | macOS/AppState tests, frontend lint/test/build, visual smoke if shared. |
| Small utility page | Target page tests if present, frontend lint/build, optional browser smoke. |
| Route SSOT | route contract tests, route ownership tests, RBAC parity, frontend build, route smoke. |
| Auth/login | auth store/interceptor/login tests, route smoke, manual auth smoke, backend contract awareness. |
| Queue | queue API tests, queue e2e, role smoke, manual queue smoke; protect `queue_time`. |
| Payment | payment e2e/tests, callback manual smoke, build; protect payment status semantics. |
| EMR/clinical | EMR tests, visit lifecycle tests, prescription a11y, manual clinical smoke. |
| Lab | lab workbench tests, lab workflow smoke, build. |
| Role panel | Route/role checks, targeted panel smoke, build; one slice per PR. |
| API/hooks/services | Unit tests around client/hook/service, parity tests when endpoint contracts change. |
| E2E | Targeted Playwright spec; do not claim live browser proof without running it. |

## 12. Top Findings

Top 10 frontend risks:

1. `RegistrarPanel.jsx` mixes queue, payment, appointment, patient aggregation, and cancellation in one 3585-line file.
2. Specialty clinical panels are large and clinical-heavy, especially dentist/derma/cardio.
3. Queue logic appears in public queue, registrar, admin queue settings, display boards, hooks, and services; `queue_time` must remain backend-aligned.
4. Payment status appears across cashier, registrar, payment result callbacks, admin finance, payment providers, and payment widgets.
5. Auth/RBAC route decisions are centralized but high blast radius.
6. Patient pickup and file management expose medical/private data surfaces.
7. EMR v2 includes autosave, conflict, navigation guard, AI suggestions, diagnosis, prescription, and specialty sections.
8. Lab queue/report state merges queue entries with lab report instances in frontend.
9. UI layer fragmentation makes visual-only PRs likely to expand old patterns.
10. AppState migration is incomplete and risky in domain-heavy screens.

Top 10 safe cleanup opportunities:

1. Docs link from `DESIGN_SYSTEM.md` to this report.
2. AppState documentation and low-risk page migration checklist updates.
3. `Activation.jsx` state/UI consistency check.
4. `Search.jsx` no-results/error AppState polish.
5. `ServiceAuditHistory.jsx` AppState normalization.
6. `Health.jsx`/`Audit.jsx` AppState examples in docs.
7. Internal demo route documentation and isolation notes.
8. Test-only characterization for route/sidebar hidden routes.
9. UI-layer import inventory docs.
10. Monolith review docs before runtime edits.

Top 10 files needing dedicated review:

1. `frontend/src/pages/DentistPanelUnified.jsx`
2. `frontend/src/pages/RegistrarPanel.jsx`
3. `frontend/src/components/wizard/AppointmentWizardV2.jsx`
4. `frontend/src/pages/AdminPanel.jsx`
5. `frontend/src/pages/DermatologistPanelUnified.jsx`
6. `frontend/src/pages/CardiologistPanelUnified.jsx`
7. `frontend/src/components/tables/EnhancedAppointmentsTable.jsx`
8. `frontend/src/pages/QueueJoin.jsx`
9. `frontend/src/pages/CashierPanel.jsx`
10. `frontend/src/pages/LabPanel.jsx`

Top 10 candidate PRs ordered by safety/impact:

| Title | Scope | Allowed files | Forbidden files | Expected validation | Risk | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| Docs: link frontend classification audit | Add design-system link only. | `frontend/DESIGN_SYSTEM.md` | Runtime/test/package files | `git diff --check`, link `rg` | Low | Link resolves and no runtime changed. |
| Docs: AppState migration candidate checklist | Clarify safe state migration order. | `frontend/APP_STATE_MIGRATION_BACKLOG.md` | Runtime files | `git diff --check`, marker `rg` | Low | Checklist matches current report. |
| UI: `Activation.jsx` AppState polish | Keep existing AppState primitives consistent. | `frontend/src/pages/Activation.jsx` | route/API/backend/tests unless targeted | lint/test/build or targeted page test | Low | API calls/roles/filter unchanged. |
| UI: `Search.jsx` empty/error state polish | No-results/error only. | `frontend/src/pages/Search.jsx` | search API/navigation | targeted test/build | Low | Search behavior unchanged. |
| UI: `ServiceAuditHistory` state normalization | Loading/empty only. | `frontend/src/components/admin/ServiceAuditHistory.jsx` | service API/catalog logic | targeted test/build | Low | History fields/fetch unchanged. |
| Test: route hidden/sidebar characterization | Add assertions for hidden app-shell routes. | route tests only | route registry/runtime | route tests | Medium | Documents current nav/hidden route contract. |
| UI: Payment result visual-only review | PaymentSuccess/Cancel display polish only. | `PaymentSuccess.jsx`, `PaymentCancel.jsx` | payment APIs/services/routes | payment e2e/manual smoke | High/Critical | No status/receipt endpoint semantics changed. |
| UI: Admin utility empty state slice | One small admin utility component. | One `components/admin/*` file | `AdminPanel.jsx` broad rewrites | targeted test/build | Medium | Component API unchanged. |
| Test: queue join language/accessibility characterization | Add/extend tests around existing copy/accessibility. | QueueJoin test file | `QueueJoin.jsx`, queue API | targeted tests | Medium | Current behavior captured before edits. |
| Docs: monolith decomposition dossiers | One dossier per role panel. | docs only | runtime files | `git diff --check` | Low | Future safe slices documented. |

## 13. Future Roadmap

Phase 0:

- Complete P0/P1 trust and consistency fixes already underway.
- Keep login/auth, queue language, AI disclaimer, payment result, design-system, monolith, and AppState concerns as separate PRs.

Phase 1:

- App-state primitives and small utility page migrations.
- Prefer `Activation.jsx`, `Search.jsx`, `Health.jsx`, `Audit.jsx`, and tiny admin utilities.

Phase 2:

- Low-risk admin/table empty/error states.
- Avoid shared table primitives until tests characterize consumers.

Phase 3:

- Payment-adjacent visual states.
- Payment result pages and display copy only; no status/API behavior.

Phase 4:

- Role panel one-slice migrations.
- Each PR must define one role, one screen/tab/state, and one validation target.

Phase 5:

- Clinical-heavy flows after dedicated review.
- EMR, lab, specialty, diagnosis, prescription, AI medical copy, and patient medical data require review-first prompts.

Phase 6:

- Visual regression / Storybook / Playwright expansion if justified.
- Use after stable primitives and role smoke coverage exist.

## 14. Agent Rules for Future Frontend PRs

Before editing:

- Classify the target function area.
- Identify risk level.
- Identify backend-owned logic and SSOT sensitivity.
- Inspect `routeRegistry.js` if routing, navigation, role, shell, or redirect behavior is involved.
- Inspect `frontend/src/components/ui/macos/index.js` before creating UI.
- Choose one safe slice.
- Define validation before editing.
- Record stop conditions for queue, payment, EMR, lab, auth, patient data, and role panels.

Do not:

- Mass-refactor panels.
- Move backend logic into frontend.
- Change role/route/payment/queue/EMR semantics in UI-only PRs.
- Create a parallel UI framework.
- Add MUI or a new dependency without explicit justification.
- Claim live smoke without running it.
- Bundle visual cleanup with endpoint/payload/status changes.
- Expand legacy UI layers in new clinic operations work.

## 15. Appendix

### Search Commands Run

Required `rg` commands run:

```powershell
rg "path:|route|ROUTE_|SIDEBAR_PRESETS|RouteAccessBoundary|createBrowserRouter|Routes|Route" frontend/src/routing frontend/src/App.jsx frontend/src/PublicApp.jsx
rg "Admin|Owner|Registrar|Doctor|Cashier|Lab|Patient|Cardio|Derma|Dentist|role|roles|permission|permissions|RoleGate|RBAC" frontend/src
rg "auth|login|token|refresh|logout|permission|RBAC|queue|payment|cashier|invoice|EMR|emr|lab|patient|diagnosis|prescription|AI|assistant|upload|file" frontend/src
rg "@mui|mui|MUI|Tailwind|tailwind|className=|style=|MacOS|macos|design-system|Modern|AppLoading|AppEmpty|AppError|MacOSEmptyState|MacOSAlert|MacOSLoadingSkeleton" frontend/src
rg "Loading|loading|isLoading|Spinner|Skeleton|Empty|empty|No data|Нет данных|Ошибка|Error|error|failed|Не удалось|setError" frontend/src/pages frontend/src/components
rg "fetch\(|axios|apiClient|/api/|graphql|payment_id|queue|activation|audit|health|appointments|patients|visits|lab|emr" frontend/src
```

PowerShell equivalents used because Unix `find` was not available:

```powershell
Get-ChildItem -Path 'frontend\src\pages' -File -Recurse -Depth 1
Get-ChildItem -Path 'frontend\src\components' -File -Recurse -Depth 2
if (Test-Path 'frontend\src\panels') { Get-ChildItem -Path 'frontend\src\panels' -File -Recurse -Depth 2 } else { 'MISSING: frontend\src\panels' }
Get-ChildItem -Path 'frontend\src' -Recurse -File -Include '*.test.*','*.spec.*'
if (Test-Path 'frontend\e2e') { Get-ChildItem -Path 'frontend\e2e' -Recurse -File } else { 'MISSING: frontend\e2e' }
Get-ChildItem -Path 'frontend\src' -Recurse -File -Include *.jsx,*.tsx,*.js,*.ts | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines }
```

Additional summary commands run:

```powershell
node --input-type=module -e "import { ROUTE_REGISTRY, SIDEBAR_PRESETS } from './frontend/src/routing/routeRegistry.js'; ..."
rg -l "AppLoading|AppEmpty|AppError" frontend/src
rg -l "MacOSEmptyState|MacOSLoadingSkeleton|MacOSAlert" frontend/src/pages frontend/src/components
rg -l "@mui/material|@mui/icons-material" frontend/src
rg -l "Modern[A-Za-z]+" frontend/src/pages frontend/src/components
```

### Limitations

- Static-code audit only.
- Dev servers were not started.
- No live browser smoke was run.
- No full frontend/backend test suites were run.
- Large files were inventoried and spot-checked by search/import outline, not manually reviewed line by line.
- Route risk is inferred from `routeRegistry.js`, route tests, owner/component names, and static searches.
- Backend endpoint truth was not audited; this report only flags frontend-backend contract sensitivity.
- Some terminal output displays mojibake for Cyrillic text; paths and code ownership were still readable.

### Files Inspected

Docs and rules:

- `AGENTS.md`
- `.cursorrules`
- `.agents/skills/clinic-frontend-design/SKILL.md`
- `.agents/skills/clinic-frontend-design/agents/openai.yaml`
- `UI_UX_audit_for_GPT.md`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/APP_STATE_MIGRATION_BACKLOG.md`
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/package.json`

Core frontend anchors:

- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/PublicApp.jsx`
- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/routeSelectors.js`
- `frontend/src/routing/routeGuards.jsx`
- `frontend/src/routing/__tests__/routeContract.test.js`
- `frontend/src/routing/__tests__/routeOwnershipEnforcement.test.js`
- `frontend/e2e/frontend-10-route-smoke.spec.js`
- `frontend/src/components/ui/macos/index.js`
- `frontend/src/components/ui/macos/*`
- `frontend/src/theme/*`
- `frontend/src/styles/*`
- `frontend/src/design-system/*`
- `frontend/src/api/*`
- `frontend/src/services/*`
- `frontend/src/hooks/*`
- `frontend/src/stores/*`

Targeted manual/outline inspection:

- `Login.jsx`
- `LoginFormStyled.jsx`
- `PaymentSuccess.jsx`
- `PaymentCancel.jsx`
- `QueueJoin.jsx`
- `AdminPanel.jsx`
- `RegistrarPanel.jsx`
- `DoctorPanel.jsx`
- `CashierPanel.jsx`
- `LabPanel.jsx`
- `PatientPanel.jsx`
- `CardiologistPanelUnified.jsx`
- `DermatologistPanelUnified.jsx`
- `DentistPanelUnified.jsx`
- `AppointmentWizardV2.jsx`
- `ServiceCatalog.jsx`
- `QueueProfilesManager.jsx`
- `QueueLimitsManager.jsx`
- `PaymentManager.jsx`
- `LabReportWorkbench.jsx`
- `EMRContainerV2.jsx`

### Large Files Inventory

| Lines | Path |
| ---: | --- |
| 3804 | `frontend/src/pages/DentistPanelUnified.jsx` |
| 3585 | `frontend/src/pages/RegistrarPanel.jsx` |
| 3427 | `frontend/src/components/wizard/AppointmentWizardV2.jsx` |
| 2837 | `frontend/src/pages/AdminPanel.jsx` |
| 2549 | `frontend/src/pages/DermatologistPanelUnified.jsx` |
| 2253 | `frontend/src/pages/CardiologistPanelUnified.jsx` |
| 2189 | `frontend/src/components/tables/EnhancedAppointmentsTable.jsx` |
| 1615 | `frontend/src/components/admin/DepartmentManagement.jsx` |
| 1610 | `frontend/src/pages/QueueJoin.jsx` |
| 1554 | `frontend/src/components/ai/RiskAssessment.jsx` |
| 1482 | `frontend/src/pages/CashierPanel.jsx` |
| 1449 | `frontend/src/pages/DoctorPanel.jsx` |
| 1439 | `frontend/src/components/ai/SmartScheduling.jsx` |
| 1407 | `frontend/src/components/ai/DrugInteractionChecker.jsx` |
| 1405 | `frontend/src/routing/routeRegistry.js` |
| 1348 | `frontend/src/components/admin/ServiceCatalog.jsx` |
| 1332 | `frontend/src/pages/landingContent.js` |
| 1276 | `frontend/src/components/ai/AnalyticsInsights.jsx` |
| 1263 | `frontend/src/components/admin/DynamicPricingManager.jsx` |
| 1226 | `frontend/src/components/ai/QualityControl.jsx` |
| 1182 | `frontend/src/components/admin/QueueProfilesManager.jsx` |
| 1177 | `frontend/src/components/ai/VoiceToText.jsx` |
| 1161 | `frontend/src/components/settings/NotificationPreferences.jsx` |
| 1111 | `frontend/src/components/admin/DiscountBenefitsManager.jsx` |
| 1083 | `frontend/src/components/analytics/AIAnalytics.jsx` |
| 1078 | `frontend/src/components/chat/ChatWindow.jsx` |
| 1060 | `frontend/src/components/admin/CloudPrintingManager.jsx` |
| 1036 | `frontend/src/services/panelPrint.js` |
| 1007 | `frontend/src/pages/AnalyticsPage.jsx` |
| 992 | `frontend/src/components/ai/TreatmentRecommendations_backup.jsx` |
| 985 | `frontend/src/components/admin/MedicalEquipmentManager.jsx` |
| 980 | `frontend/src/pages/DisplayBoardUnified.jsx` |
| 946 | `frontend/src/components/ai/TreatmentRecommendations.jsx` |
| 942 | `frontend/src/locales/ru.js` |
| 942 | `frontend/src/locales/uz.js` |
| 937 | `frontend/src/components/laboratory/LabReportWorkbench.jsx` |
| 932 | `frontend/src/components/admin/BillingManager.jsx` |
| 931 | `frontend/src/components/security/TwoFactorManager.jsx` |
| 927 | `frontend/src/components/admin/GroupPermissionsManager.jsx` |
| 916 | `frontend/src/components/dental/VisitProtocol.jsx` |

### Route Inventory Summary

- Total canonical routes: 72.
- Groups: public 14, onboarding 1, admin 35, clinical 16, internal-demo 6.
- Auth: public 14, authenticated 3, role-scoped 55.
- Shells: landing 2, fullscreen 16, callback 2, setup 1, app-shell 51.
- Surfaces: screen 59, utility 11, callback 2.
- Lifecycles: stable 66, internal 6.
- Visible nav routes: 37.
- Legacy aliases: 37.
- Sidebar presets: `admin`, `default`, `registrar`, `doctor`, `patient`, `cashier`, `lab`, `cardiology`, `dermatology`, `dentistry`.
- `frontend/src/panels`: not present.

### Inventory Counts

- Page files at requested depth: 45.
- Component files at requested depth: 455.
- Frontend unit/spec files: 63.
- Frontend e2e files: 16.
- JS/TS/JSX/TSX files under `frontend/src`: 690.
- Files matching role/workflow search: 348.
- Files matching clinical/payment/queue/auth-sensitive search: 590.
- Files matching UI-layer search: 459.
- Files matching loading/empty/error search: 329.
- Files matching API/backend-contract search: 529.
- Files with `AppLoading`/`AppEmpty`/`AppError`: 10.

### Glossary

- SSOT: Single source of truth. Frontend route SSOT is `frontend/src/routing/routeRegistry.js`; backend remains SSOT for business/clinical/payment/queue/auth data.
- Backend-contract sensitive: frontend code depends on endpoint paths, payload shape, status values, or backend-owned decisions.
- Clinical-heavy: screens that touch diagnosis, prescription, EMR, lab results, visit state, AI medical copy, or patient medical data.
- Payment-sensitive: screens that display, create, update, or infer payment status, receipt, refund, invoice, provider, or mark-paid behavior.
- Queue-sensitive: screens that display, sort, create, or infer queue entries, queue status, queue profiles, doctor/specialist mapping, or `queue_time`.
- UI layer: component/style system used to render frontend surfaces.
- Safe PR strategy: narrow future change shape that avoids cross-domain behavior changes.
