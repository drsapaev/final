# Sprint F3-0 — Caller Inventory

> Read-only analysis. No source files modified.
> Generated: 2026-07-22T17:29:03.910Z

> Scope: 17 components with `}: any)` cast.

## Summary

| # | Component | File | Declared props | Callers | Conflicts | Domain |
|---|-----------|------|----------------|---------|-----------|--------|
| 1 | WelcomeView | pages/registrar/views/WelcomeView.tsx:67 | 34 | 1 | 0 | Wizard/Cart |
| 2 | CartStepV2 | components/wizard/CartStepV2.tsx:25 | 15 | 1 | 0 | Wizard/Cart |
| 3 | PhoneVerification | components/auth/PhoneVerification.tsx:20 | 7 | 1 | 0 | Generic |
| 4 | EchoForm | components/cardiology/EchoForm.tsx:147 | 4 | 1 | 0 | EMR |
| 5 | DentalPatientsTab | components/dental/DentalPatientsTab.tsx:13 | 5 | 1 | 0 | Generic |
| 6 | TeethChart | components/dental/TeethChart.tsx:44 | 3 | 3 | 2 | Dental |
| 7 | QueuePositionCard | components/mobile/QueuePositionCard.tsx:9 | 1 | 1 | 0 | Queue |
| 8 | DoctorServiceSelector | components/doctor/DoctorServiceSelector.tsx:33 | 5 | 1 | 0 | Generic |
| 9 | renderStatCard | components/notifications/EmailSMSManager.tsx:342 | 5 | 4 | 0 | Generic |
| 10 | PatientCard | components/medical/PatientCard.tsx:11 | 8 | 2 | 1 | Patients |
| 11 | Table | components/common/Table.tsx:13 | 12 | 19 | 7 | Generic |
| 12 | AppointmentFlow | components/AppointmentFlow.tsx:13 | 1 | 1 | 0 | Scheduling |
| 13 | ModernQueueManager | components/queue/ModernQueueManager.tsx:28 | 7 | 2 | 2 | Generic |
| 14 | QueueTable | components/queue/QueueTable.tsx:15 | 4 | 1 | 0 | Generic |
| 15 | EMRSmartFieldV2 | components/emr-v2/sections/EMRSmartFieldV2.tsx:50 | 16 | 5 | 6 | Generic |
| 16 | ComplaintsField | components/emr-v2/sections/ComplaintsField.tsx:37 | 11 | 1 | 0 | Generic |
| 17 | PrescriptionEditor | components/emr-v2/sections/PrescriptionEditor.tsx:30 | 4 | 2 | 2 | Generic |

## Domain grouping (recommended F3 execution order)

| Domain | Components | Total callers | Total conflicts |
|--------|-----------|---------------|------------------|
| EMR | 1 | 1 | 0 |
| Queue | 1 | 1 | 0 |
| Scheduling | 1 | 1 | 0 |
| Wizard/Cart | 2 | 2 | 0 |
| Patients | 1 | 2 | 1 |
| Dental | 1 | 3 | 2 |
| Generic | 10 | 37 | 17 |

## Detailed inventory per component

### WelcomeView

- **File:** `pages/registrar/views/WelcomeView.tsx:67`
- **Declared props:** `t`, `language`, `theme`, `textColor`, `appointments`, `departmentStats`, `dataSource`, `appointmentsLoading`, `filteredAppointments`, `services`, `activeTab`, `historyDate`, `showCalendar`, `tempDateInput`, `loadAppointments`, `setShowWizard`, `setWizardEditMode`, `setWizardInitialData`, `setShowPaymentManager`, `setHistoryDate`, `setShowCalendar`, `setTempDateInput`, `setSearchParams`, `navigate`, `setPaymentDialog`, `setPrintDialog`, `setContextMenu`, `openRecordPreview`, `openRecordEditor`, `updateAppointmentStatus`, `handleStartVisit`, `generateCSV`, `downloadCSV`, `DataSourceIndicator`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Wizard/Cart → Cart domain types

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `t` | — |
| `language` | — |
| `theme` | — |
| `textColor` | — |
| `appointments` | — |
| `departmentStats` | — |
| `dataSource` | — |
| `appointmentsLoading` | — |
| `filteredAppointments` | — |
| `services` | — |
| `activeTab` | — |
| `historyDate` | — |
| `showCalendar` | — |
| `tempDateInput` | — |
| `loadAppointments` | — |
| `setShowWizard` | — |
| `setWizardEditMode` | — |
| `setWizardInitialData` | — |
| `setShowPaymentManager` | — |
| `setHistoryDate` | — |
| `setShowCalendar` | — |
| `setTempDateInput` | — |
| `setSearchParams` | — |
| `navigate` | — |
| `setPaymentDialog` | — |
| `setPrintDialog` | — |
| `setContextMenu` | — |
| `openRecordPreview` | — |
| `openRecordEditor` | — |
| `updateAppointmentStatus` | — |
| `handleStartVisit` | — |
| `generateCSV` | — |
| `downloadCSV` | — |
| `DataSourceIndicator` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `activeTab` | `string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `appointments` | `any[]` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `appointmentsLoading` | `boolean` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `dataSource` | `string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `DataSourceIndicator` | `() => import("react").JSX.Element` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `departmentStats` | `{}` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `downloadCSV` | `typeof downloadCSV` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `filteredAppointments` | `any[]` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `generateCSV` | `typeof generateCSV` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `handleStartVisit` | `(appointment: any) => Promise<any>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `historyDate` | `string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `language` | `string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `loadAppointments` | `(options?: Record<string, unknown>) => Promise<void>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `navigate` | `import("react-router").NavigateFunction` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `openRecordEditor` | `(row: any) => void` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `openRecordPreview` | `(row: any) => void` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `services` | `Record<string, unknown>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setContextMenu` | `import("react").Dispatch<import("react").SetStateAction<{ open: boolean; row: any; position: { x: number; y: number; }; }>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setHistoryDate` | `import("react").Dispatch<import("react").SetStateAction<string>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setPaymentDialog` | `import("react").Dispatch<import("react").SetStateAction<{ open: boolean; row: any; paid: boolean; source: any; }>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setPrintDialog` | `import("react").Dispatch<import("react").SetStateAction<{ open: boolean; type: string; data: any; }>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setSearchParams` | `import("react-router-dom").SetURLSearchParams` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setShowCalendar` | `import("react").Dispatch<import("react").SetStateAction<boolean>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setShowPaymentManager` | `import("react").Dispatch<import("react").SetStateAction<boolean>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setShowWizard` | `import("react").Dispatch<import("react").SetStateAction<boolean>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setTempDateInput` | `import("react").Dispatch<import("react").SetStateAction<string>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setWizardEditMode` | `import("react").Dispatch<import("react").SetStateAction<boolean>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `setWizardInitialData` | `import("react").Dispatch<import("react").SetStateAction<Record<string, unknown>>>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `showCalendar` | `boolean` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `t` | `(key: any) => string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `tempDateInput` | `string` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `textColor` | `"var(--mac-text-primary)"` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `theme` | `"light" | "dark"` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |
| `updateAppointmentStatus` | `(recordSelectionKey: any, status: any, reason?: string, sourceRecord?: any) => Promise<any>` ×1 | ../frontend/src/pages/RegistrarPanel.tsx:1484 |

#### Caller files

- `../frontend/src/pages/RegistrarPanel.tsx` — line: 1484

### CartStepV2

- **File:** `components/wizard/CartStepV2.tsx:25`
- **Declared props:** `cart`, `onAddToCart`, `onRemoveFromCart`, `servicesData`, `doctorsData`, `errors`, `activeCategory`, `searchQuery`, `editMode`, `getServiceName`, `onUpdateItem`, `repeatEligibilityByItemId`, `isRepeatEligibilityLoading`, `onApplyRepeatSuggestion`, `repeatSuggestionSummary`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Wizard/Cart → Cart domain types

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `cart` | — |
| `onAddToCart` | — |
| `onRemoveFromCart` | — |
| `servicesData` | — |
| `doctorsData` | — |
| `errors` | — |
| `activeCategory` | — |
| `searchQuery` | — |
| `editMode` | false |
| `getServiceName` | — |
| `onUpdateItem` | — |
| `repeatEligibilityByItemId` | — |
| `isRepeatEligibilityLoading` | — |
| `onApplyRepeatSuggestion` | — |
| `repeatSuggestionSummary` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `activeCategory` | `string` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `calculateTotal` | `() => number` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `cart` | `{ [k: string]: unknown; items: CartItem[]; discount_mode: string; all_free: boolean; notes: string; }` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `doctorsData` | `any[]` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `editMode` | `boolean` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `errors` | `Record<string, unknown>` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `getServiceName` | `(item: any) => any` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `isReloading` | `boolean` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `isRepeatEligibilityLoading` | `boolean` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onAddToCart` | `(service: any) => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onApplyRepeatSuggestion` | `() => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onReloadServices` | `() => Promise<void>` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onRemoveFromCart` | `(itemId: any) => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onToggleAllServices` | `() => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onUpdateCart` | `(field: any, value: any) => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `onUpdateItem` | `(itemId: any, field: any, value: any) => void` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `repeatEligibilityByItemId` | `Record<string, unknown>` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `repeatSuggestionSummary` | `{ hasConsultations: boolean; fullyEligible: boolean; hasMixed: boolean; maxDiscountPercent: number; hasUnknown: boolean; }` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `searchQuery` | `string` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `services` | `any[]` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `servicesData` | `any[]` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `setActiveCategory` | `import("react").Dispatch<import("react").SetStateAction<string>>` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `setSearchQuery` | `import("react").Dispatch<import("react").SetStateAction<string>>` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |
| `showAllServices` | `boolean` ×1 | ../frontend/src/components/wizard/AppointmentWizardV2.tsx:2967 |

#### Caller files

- `../frontend/src/components/wizard/AppointmentWizardV2.tsx` — line: 2967

### PhoneVerification

- **File:** `components/auth/PhoneVerification.tsx:20`
- **Declared props:** `phone`, `purpose`, `onVerified`, `onCancel`, `customMessage`, `showPhoneInput`, `title`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `phone` | — |
| `purpose` | 'verification' |
| `onVerified` | — |
| `onCancel` | — |
| `customMessage` | — |
| `showPhoneInput` | false |
| `title` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `onVerified` | `() => import("react-toastify").Id` ×1 | ../frontend/src/pages/Settings.tsx:433 |
| `showPhoneInput` | `true` ×1 | ../frontend/src/pages/Settings.tsx:433 |
| `title` | `string` ×1 | ../frontend/src/pages/Settings.tsx:433 |

#### Caller files

- `../frontend/src/pages/Settings.tsx` — line: 433

### EchoForm

- **File:** `components/cardiology/EchoForm.tsx:147`
- **Declared props:** `visitId`, `onSave`, `onDataUpdate`, `initialData`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** EMR → EMR visit/section types

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `visitId` | — |
| `onSave` | — |
| `onDataUpdate` | — |
| `initialData` | null |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `onDataUpdate` | `any` ×1 | ../frontend/src/components/cardiology/EcgTab.tsx:57 |
| `patientId` | `any` ×1 | ../frontend/src/components/cardiology/EcgTab.tsx:57 |
| `visitId` | `any` ×1 | ../frontend/src/components/cardiology/EcgTab.tsx:57 |

#### Caller files

- `../frontend/src/components/cardiology/EcgTab.tsx` — line: 57

### DentalPatientsTab

- **File:** `components/dental/DentalPatientsTab.tsx:13`
- **Declared props:** `patients`, `onSelectPatient`, `onDentalChart`, `onTreatment`, `onProsthetic`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `patients` | [] |
| `onSelectPatient` | — |
| `onDentalChart` | — |
| `onTreatment` | — |
| `onProsthetic` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `onDentalChart` | `(patient: any) => void` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1530 |
| `onSelectPatient` | `(patient: any) => void` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1530 |
| `patients` | `any[]` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1530 |

#### Caller files

- `../frontend/src/pages/DentistPanelUnified.tsx` — line: 1530

### TeethChart

- **File:** `components/dental/TeethChart.tsx:44`
- **Declared props:** `onToothClick`, `initialData`, `readOnly`
- **JSX callers:** 3
- **Conflicts:** 2
- **Recommended domain:** Dental → ToothChart domain types

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `onToothClick` | — |
| `initialData` | {} |
| `readOnly` | false |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `initialData` | `Record<string, unknown>` ×1<br>`{}` ×1<br>`Record<string, any>` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:2022 |
| `onToothClick` | `(toothNumber: any, toothData: any) => void` ×3 | ../frontend/src/pages/DentistPanelUnified.tsx:2022 |
| `patientId` | `any` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:2022 |
| `readOnly` | `false` ×2<br>`boolean` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:2022 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`initialData`**

- `Record<string, unknown>` ×1 — sample: ../frontend/src/pages/DentistPanelUnified.tsx:2022
- `{}` ×1 — sample: ../frontend/src/components/dental/DentalVisitScreen.tsx:713
- `Record<string, any>` ×1 — sample: ../frontend/src/components/emr-v2/sections/specialty/DentistrySection.tsx:142

**`readOnly`**

- `false` ×2 — sample: ../frontend/src/pages/DentistPanelUnified.tsx:2022
- `boolean` ×1 — sample: ../frontend/src/components/emr-v2/sections/specialty/DentistrySection.tsx:142

#### Caller files

- `../frontend/src/pages/DentistPanelUnified.tsx` — line: 2022
- `../frontend/src/components/dental/DentalVisitScreen.tsx` — line: 713
- `../frontend/src/components/emr-v2/sections/specialty/DentistrySection.tsx` — line: 142

### QueuePositionCard

- **File:** `components/mobile/QueuePositionCard.tsx:9`
- **Declared props:** `queueEntry`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Queue → QueueEntry | QueueData

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `queueEntry` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `onRefresh` | `() => Promise<void>` ×1 | ../frontend/src/pages/MobilePatientDashboard.tsx:185 |
| `queueEntry` | `{ id: any; number: any; status: any; peopleBefore: any; estimatedWaitTime: any; doctorName: any; specialty: any; cabinet: any; }` ×1 | ../frontend/src/pages/MobilePatientDashboard.tsx:185 |

#### Caller files

- `../frontend/src/pages/MobilePatientDashboard.tsx` — line: 185

### DoctorServiceSelector

- **File:** `components/doctor/DoctorServiceSelector.tsx:33`
- **Declared props:** `specialty`, `selectedServices`, `onServicesChange`, `canEditPrices`, `className`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `specialty` | 'cardiology' |
| `selectedServices` | [] |
| `onServicesChange` | — |
| `canEditPrices` | true |
| `className` | '' |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `canEditPrices` | `false` ×1 | ../frontend/src/components/cardiology/ServicesTab.tsx:19 |
| `selectedServices` | `undefined[]` ×1 | ../frontend/src/components/cardiology/ServicesTab.tsx:19 |
| `specialty` | `string` ×1 | ../frontend/src/components/cardiology/ServicesTab.tsx:19 |

#### Caller files

- `../frontend/src/components/cardiology/ServicesTab.tsx` — line: 19

### renderStatCard

- **File:** `components/notifications/EmailSMSManager.tsx:342`
- **Declared props:** `title`, `value`, `detail`, `icon`, `tone`
- **JSX callers:** 4
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `title` | — |
| `value` | — |
| `detail` | — |
| `icon` | — |
| `tone` | 'blue' |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `detail` | `string` ×2 | ../frontend/src/components/notifications/EmailSMSManager.tsx:378 |
| `icon` | `import("react").ForwardRefExoticComponent<Omit<import("lucide-react").LucideProps, "ref"> & import("react").RefAttributes<SVGSVGElement>>` ×4 | ../frontend/src/components/notifications/EmailSMSManager.tsx:378 |
| `title` | `string` ×4 | ../frontend/src/components/notifications/EmailSMSManager.tsx:378 |
| `tone` | `string` ×4 | ../frontend/src/components/notifications/EmailSMSManager.tsx:378 |
| `value` | `any` ×4 | ../frontend/src/components/notifications/EmailSMSManager.tsx:378 |

#### Caller files

- `../frontend/src/components/notifications/EmailSMSManager.tsx` — lines: 378, 385, 392, 398

### PatientCard

- **File:** `components/medical/PatientCard.tsx:11`
- **Declared props:** `patient`, `onView`, `onEdit`, `onDelete`, `onArchive`, `onRestore`, `className`, `props`
- **JSX callers:** 2
- **Conflicts:** 1
- **Recommended domain:** Patients → Patient

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `patient` | — |
| `onView` | — |
| `onEdit` | — |
| `onDelete` | — |
| `onArchive` | — |
| `onRestore` | — |
| `className` | '' |
| `props` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `className` | `string` ×1 | ../frontend/src/pages/MediLabDemo.tsx:530 |
| `key` | `number` ×1 | ../frontend/src/pages/MediLabDemo.tsx:530 |
| `onClose` | `() => void` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1903 |
| `onDelete` | `(patient: any) => void` ×1 | ../frontend/src/pages/MediLabDemo.tsx:530 |
| `onEdit` | `(patient: any) => void` ×1 | ../frontend/src/pages/MediLabDemo.tsx:530 |
| `onSave` | `(updatedPatient: any) => void` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1903 |
| `onView` | `(patient: any) => void` ×1 | ../frontend/src/pages/MediLabDemo.tsx:530 |
| `patient` | `any` ×1<br>`{ id: number; name: string; patientId: string; age: number; gender: string; lastVisit: string; department: string; status: string; avatar: any; }` ×1 | ../frontend/src/pages/DentistPanelUnified.tsx:1903 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`patient`**

- `any` ×1 — sample: ../frontend/src/pages/DentistPanelUnified.tsx:1903
- `{ id: number; name: string; patientId: string; age: number; gender: string; lastVisit: string; department: string; status: string; avatar: any; }` ×1 — sample: ../frontend/src/pages/MediLabDemo.tsx:530

#### Caller files

- `../frontend/src/pages/DentistPanelUnified.tsx` — line: 1903
- `../frontend/src/pages/MediLabDemo.tsx` — line: 530

### Table

- **File:** `components/common/Table.tsx:13`
- **Declared props:** `data`, `columns`, `sortable`, `filterable`, `pagination`, `pageSize`, `onSort`, `onFilter`, `onPageChange`, `loading`, `emptyMessage`, `props`
- **JSX callers:** 19
- **Conflicts:** 7
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `data` | [] |
| `columns` | [] |
| `sortable` | true |
| `filterable` | true |
| `pagination` | true |
| `pageSize` | 10 |
| `onSort` | — |
| `onFilter` | — |
| `onPageChange` | — |
| `loading` | false |
| `emptyMessage` | 'Нет данных' |
| `props` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `columns` | `{ key: string; title: string; render: (_actionValue: unknown, activation: Record<string, unknown>) => import("react").JSX.Element; }[]` ×1<br>`{ key: string; title: string; sortable: false; }[]` ×1<br>`({ key: string; header: string; render: (value: unknown) => import("react").JSX.Element; } | { key: string; header: string; align: string; render: (row: unknown) => import("react").JSX.Element; })[]` ×2<br>`({ key: string; title: import("react").JSX.Element; width: string; } | { key: string; title: string; width: string; })[]` ×1<br>`{ key: string; label: string; }[]` ×1<br>`{ key: string; title: string; render: (_: any, user: any) => import("react").JSX.Element; }[]` ×1<br>`({ key: string; label: string; width: string; } | { key: string; label: string; width: string; align: string; })[]` ×1<br>`{ key: string; title: string; render: (_value: any, request: any) => import("react").JSX.Element; }[]` ×1<br>`({ key: string; title: import("react").JSX.Element; render: (_value: any, file: any) => import("react").JSX.Element; } | { key: string; title: string; render: (_value: any, file: any) => import("react").JSX.Element; } | { key: string; title: string; render: (value: any) => string; })[]` ×1<br>`{ key: string; title: string; render: (_value: any, template: any) => import("react").JSX.Element; }[]` ×1<br>`{ key: string; title: string; sortable: boolean; }[]` ×7 | ../frontend/src/components/admin/ActivationSystem.tsx:382 |
| `data` | `Activation[]` ×1<br>`{ day: React.JSX.Element; specialist_name: React.JSX.Element; queue_tag: React.JSX.Element; cabinet_number: React.JSX.Element; cabinet_floor: React.JSX.Element; cabinet_building: React.JSX.Element; entries_count: React.JSX.Element; active: React.JSX.Element; sync_state: React.JSX.Element; }[]` ×1<br>`Record<string, unknown>[]` ×2<br>`{ id: any; select: import("react").JSX.Element; service: import("react").JSX.Element; category: import("react").JSX.Element; price: import("react").JSX.Element; duration: import("react").JSX.Element; doctor: import("react").JSX.Element; status: import("react").JSX.Element; actions: import("react").JSX.Element; }[]` ×1<br>`any[]` ×4<br>`{ model: import("react").JSX.Element; accuracy: string; speed: any; cost: string; satisfaction: string; reliability: string; }[]` ×1<br>`any` ×1<br>`{ id: number; name: string; email: string; role: string; }[]` ×1<br>`{ name: string; age: number; }[]` ×3<br>`undefined[]` ×2 | ../frontend/src/components/admin/ActivationSystem.tsx:382 |
| `emptyState` | `import("react").JSX.Element` ×4<br>`React.JSX.Element` ×2<br>`string` ×1 | ../frontend/src/components/admin/ActivationSystem.tsx:382 |
| `filterable` | `true` ×1 | ../frontend/src/components/test/ComponentTest.tsx:232 |
| `hoverable` | `false` ×2<br>`true` ×2<br>`boolean (true)` ×1 | ../frontend/src/components/admin/QueueCabinetManagement.tsx:443 |
| `loading` | `boolean` ×2<br>`true` ×1 | ../frontend/src/components/admin/QueueCabinetManagement.tsx:443 |
| `onSort` | `import("vitest").Mock<(...args: any[]) => any>` ×1 | ../frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx:45 |
| `pageSize` | `2` ×1 | ../frontend/src/components/test/ComponentTest.tsx:232 |
| `pagination` | `true` ×1 | ../frontend/src/components/test/ComponentTest.tsx:232 |
| `size` | `string` ×1 | ../frontend/src/components/cashier/RefundRequestsTable.tsx:381 |
| `sortable` | `false` ×4<br>`true` ×1 | ../frontend/src/components/admin/QueueCabinetManagement.tsx:443 |
| `striped` | `boolean (true)` ×1<br>`true` ×2 | ../frontend/src/components/admin/QueueCabinetManagement.tsx:443 |
| `style` | `{ minWidth: number; }` ×1 | ../frontend/src/components/TelegramManager.tsx:2173 |
| `variant` | `string` ×1 | ../frontend/src/components/cashier/RefundRequestsTable.tsx:381 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`columns`**

- `{ key: string; title: string; render: (_actionValue: unknown, activation: Record<string, unknown>) => import("react").JSX.Element; }[]` ×1 — sample: ../frontend/src/components/admin/ActivationSystem.tsx:382
- `{ key: string; title: string; sortable: false; }[]` ×1 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `({ key: string; header: string; render: (value: unknown) => import("react").JSX.Element; } | { key: string; header: string; align: string; render: (row: unknown) => import("react").JSX.Element; })[]` ×2 — sample: ../frontend/src/components/admin/ReportsManager.tsx:337
- `({ key: string; title: import("react").JSX.Element; width: string; } | { key: string; title: string; width: string; })[]` ×1 — sample: ../frontend/src/components/admin/ServiceCatalog.tsx:562
- `{ key: string; label: string; }[]` ×1 — sample: ../frontend/src/components/admin/SystemManagement.tsx:496
- `{ key: string; title: string; render: (_: any, user: any) => import("react").JSX.Element; }[]` ×1 — sample: ../frontend/src/components/admin/UserManagement.tsx:564
- `({ key: string; label: string; width: string; } | { key: string; label: string; width: string; align: string; })[]` ×1 — sample: ../frontend/src/components/analytics/AIAnalytics.tsx:691
- `{ key: string; title: string; render: (_value: any, request: any) => import("react").JSX.Element; }[]` ×1 — sample: ../frontend/src/components/cashier/RefundRequestsTable.tsx:381
- `({ key: string; title: import("react").JSX.Element; render: (_value: any, file: any) => import("react").JSX.Element; } | { key: string; title: string; render: (_value: any, file: any) => import("react").JSX.Element; } | { key: string; title: string; render: (value: any) => string; })[]` ×1 — sample: ../frontend/src/components/files/FileManager.tsx:614
- `{ key: string; title: string; render: (_value: any, template: any) => import("react").JSX.Element; }[]` ×1 — sample: ../frontend/src/components/notifications/EmailSMSManager.tsx:831
- `{ key: string; title: string; sortable: boolean; }[]` ×7 — sample: ../frontend/src/components/test/ComponentTest.tsx:232

**`data`**

- `Activation[]` ×1 — sample: ../frontend/src/components/admin/ActivationSystem.tsx:382
- `{ day: React.JSX.Element; specialist_name: React.JSX.Element; queue_tag: React.JSX.Element; cabinet_number: React.JSX.Element; cabinet_floor: React.JSX.Element; cabinet_building: React.JSX.Element; entries_count: React.JSX.Element; active: React.JSX.Element; sync_state: React.JSX.Element; }[]` ×1 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `Record<string, unknown>[]` ×2 — sample: ../frontend/src/components/admin/ReportsManager.tsx:337
- `{ id: any; select: import("react").JSX.Element; service: import("react").JSX.Element; category: import("react").JSX.Element; price: import("react").JSX.Element; duration: import("react").JSX.Element; doctor: import("react").JSX.Element; status: import("react").JSX.Element; actions: import("react").JSX.Element; }[]` ×1 — sample: ../frontend/src/components/admin/ServiceCatalog.tsx:562
- `any[]` ×4 — sample: ../frontend/src/components/admin/SystemManagement.tsx:496
- `{ model: import("react").JSX.Element; accuracy: string; speed: any; cost: string; satisfaction: string; reliability: string; }[]` ×1 — sample: ../frontend/src/components/analytics/AIAnalytics.tsx:691
- `any` ×1 — sample: ../frontend/src/components/notifications/EmailSMSManager.tsx:831
- `{ id: number; name: string; email: string; role: string; }[]` ×1 — sample: ../frontend/src/components/test/ComponentTest.tsx:232
- `{ name: string; age: number; }[]` ×3 — sample: ../frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx:19
- `undefined[]` ×2 — sample: ../frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx:65

**`emptyState`**

- `import("react").JSX.Element` ×4 — sample: ../frontend/src/components/admin/ActivationSystem.tsx:382
- `React.JSX.Element` ×2 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `string` ×1 — sample: ../frontend/src/components/files/FileManager.tsx:614

**`loading`**

- `boolean` ×2 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `true` ×1 — sample: ../frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx:57

**`sortable`**

- `false` ×4 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `true` ×1 — sample: ../frontend/src/components/test/ComponentTest.tsx:232

**`hoverable`**

- `false` ×2 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `true` ×2 — sample: ../frontend/src/components/admin/ReportsManager.tsx:337
- `boolean (true)` ×1 — sample: ../frontend/src/components/admin/UserManagement.tsx:564

**`striped`**

- `boolean (true)` ×1 — sample: ../frontend/src/components/admin/QueueCabinetManagement.tsx:443
- `true` ×2 — sample: ../frontend/src/components/admin/ReportsManager.tsx:337

#### Caller files

- `../frontend/src/components/TelegramManager.tsx` — line: 2173
- `../frontend/src/components/admin/ActivationSystem.tsx` — line: 382
- `../frontend/src/components/admin/QueueCabinetManagement.tsx` — line: 443
- `../frontend/src/components/admin/ReportsManager.tsx` — lines: 337, 422
- `../frontend/src/components/admin/ServiceCatalog.tsx` — line: 562
- `../frontend/src/components/admin/SystemManagement.tsx` — line: 496
- `../frontend/src/components/admin/UserManagement.tsx` — line: 564
- `../frontend/src/components/analytics/AIAnalytics.tsx` — line: 691
- `../frontend/src/components/cashier/RefundRequestsTable.tsx` — line: 381
- `../frontend/src/components/files/FileManager.tsx` — line: 614
- `../frontend/src/components/notifications/EmailSMSManager.tsx` — line: 831
- `../frontend/src/components/test/ComponentTest.tsx` — line: 232
- `../frontend/src/components/ui/macos/__tests__/MacOSTable.test.tsx` — lines: 19, 32, 45, 57, 65, 76

### AppointmentFlow

- **File:** `components/AppointmentFlow.tsx:13`
- **Declared props:** `appointment`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Scheduling → Appointment

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `appointment` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `appointment` | `any` ×1 | ../frontend/src/pages/Appointments.tsx:177 |
| `onPayment` | `(appointment: any) => void` ×1 | ../frontend/src/pages/Appointments.tsx:177 |
| `onStartVisit` | `(appointment: any) => void` ×1 | ../frontend/src/pages/Appointments.tsx:177 |

#### Caller files

- `../frontend/src/pages/Appointments.tsx` — line: 177

### ModernQueueManager

- **File:** `components/queue/ModernQueueManager.tsx:28`
- **Declared props:** `selectedDate`, `selectedDoctor`, `onQueueUpdate`, `language`, `doctors`, `onDoctorChange`, `onDateChange`
- **JSX callers:** 2
- **Conflicts:** 2
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `selectedDate` | getLocalDateString() |
| `selectedDoctor` | '' |
| `onQueueUpdate` | — |
| `language` | 'ru' |
| `doctors` | [] |
| `onDoctorChange` | — |
| `onDateChange` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `doctors` | `{ id: any; specialty: any; department: any; full_name: any; name: any; cabinet: any; active: boolean; user: { full_name: any; is_active: boolean; }; }[]` ×1<br>`never` ×1 | ../frontend/src/components/QueueIntegration.tsx:138 |
| `language` | `string` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |
| `onDateChange` | `(newDate: string) => void` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |
| `onDoctorChange` | `(newDoctorId: string) => void` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |
| `onQueueUpdate` | `() => void` ×1<br>`() => void | Promise<void>` ×1 | ../frontend/src/components/QueueIntegration.tsx:138 |
| `searchQuery` | `string` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |
| `selectedDate` | `string` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |
| `selectedDoctor` | `string` ×2 | ../frontend/src/components/QueueIntegration.tsx:138 |
| `theme` | `string` ×1 | ../frontend/src/pages/registrar/views/QueueView.tsx:88 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`doctors`**

- `{ id: any; specialty: any; department: any; full_name: any; name: any; cabinet: any; active: boolean; user: { full_name: any; is_active: boolean; }; }[]` ×1 — sample: ../frontend/src/components/QueueIntegration.tsx:138
- `never` ×1 — sample: ../frontend/src/pages/registrar/views/QueueView.tsx:88

**`onQueueUpdate`**

- `() => void` ×1 — sample: ../frontend/src/components/QueueIntegration.tsx:138
- `() => void | Promise<void>` ×1 — sample: ../frontend/src/pages/registrar/views/QueueView.tsx:88

#### Caller files

- `../frontend/src/components/QueueIntegration.tsx` — line: 138
- `../frontend/src/pages/registrar/views/QueueView.tsx` — line: 88

### QueueTable

- **File:** `components/queue/QueueTable.tsx:15`
- **Declared props:** `queueData`, `effectiveDoctor`, `loading`, `t`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `queueData` | null |
| `effectiveDoctor` | null |
| `loading` | false |
| `t` | {} |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `effectiveDoctor` | `any` ×1 | ../frontend/src/components/queue/ModernQueueManager.tsx:612 |
| `loading` | `boolean` ×1 | ../frontend/src/components/queue/ModernQueueManager.tsx:612 |
| `onGenerateQR` | `() => Promise<void>` ×1 | ../frontend/src/components/queue/ModernQueueManager.tsx:612 |
| `queueData` | `import("../../hooks/useQueueManager").QueueData` ×1 | ../frontend/src/components/queue/ModernQueueManager.tsx:612 |
| `t` | `{ selectDoctor: string; patient: string; phone: string; time: string; status: string; actions: string; called: string; queueEmpty: string; queueNotFound: string; }` ×1 | ../frontend/src/components/queue/ModernQueueManager.tsx:612 |

#### Caller files

- `../frontend/src/components/queue/ModernQueueManager.tsx` — line: 612

### EMRSmartFieldV2

- **File:** `components/emr-v2/sections/EMRSmartFieldV2.tsx:50`
- **Declared props:** `value`, `onChange`, `placeholder`, `multiline`, `rows`, `disabled`, `id`, `fieldName`, `suggestions`, `aiLoading`, `onApplySuggestion`, `onDismissSuggestion`, `onRequestAI`, `showAIButton`, `experimentalGhostMode`, `onTelemetry`
- **JSX callers:** 5
- **Conflicts:** 6
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `value` | '' |
| `onChange` | — |
| `placeholder` | 'Начните ввод...' |
| `multiline` | true |
| `rows` | 3 |
| `disabled` | false |
| `id` | — |
| `fieldName` | — |
| `suggestions` | [] |
| `aiLoading` | false |
| `onApplySuggestion` | — |
| `onDismissSuggestion` | — |
| `onRequestAI` | — |
| `showAIButton` | true |
| `experimentalGhostMode` | false |
| `onTelemetry` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `aiDisabledTooltip` | `"Для AI сначала заполните жалобы"` ×1 | ../frontend/src/components/emr-v2/sections/ExaminationSection.tsx:158 |
| `aiLoading` | `boolean` ×4 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `disabled` | `boolean` ×5 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `experimentalGhostMode` | `boolean` ×3 | ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128 |
| `fieldName` | `string` ×4 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `id` | `string` ×4 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `label` | `string` ×1 | ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128 |
| `multiline` | `boolean (true)` ×5 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `onApplySuggestion` | `(s: unknown) => void` ×4 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `onChange` | `(value: string) => void` ×1<br>`(v: string) => void` ×1<br>`(value: string, options?: Record<string, unknown>) => void` ×2<br>`(value: any) => void` ×1 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `onDismissSuggestion` | `(s: unknown) => void` ×4 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `onRequestAI` | `(text: string) => void` ×1<br>`(fieldName: any) => void` ×2 | ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128 |
| `onTelemetry` | `(payload: Record<string, unknown>) => void` ×3 | ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128 |
| `placeholder` | `string` ×5 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `required` | `boolean (true)` ×1 | ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128 |
| `rows` | `3` ×2<br>`2` ×1<br>`4` ×2 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `showAIButton` | `false` ×1<br>`boolean` ×2 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `suggestions` | `{ id: unknown; content: unknown; source: string; confidence: number; }[]` ×1<br>`unknown[]` ×3 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |
| `value` | `string` ×3<br>`any` ×1<br>`unknown` ×1 | ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`value`**

- `string` ×3 — sample: ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112
- `any` ×1 — sample: ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128
- `unknown` ×1 — sample: ../frontend/src/components/emr-v2/sections/specialty/DermatologySection.tsx:264

**`onChange`**

- `(value: string) => void` ×1 — sample: ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112
- `(v: string) => void` ×1 — sample: ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128
- `(value: string, options?: Record<string, unknown>) => void` ×2 — sample: ../frontend/src/components/emr-v2/sections/ExaminationSection.tsx:158
- `(value: any) => void` ×1 — sample: ../frontend/src/components/emr-v2/sections/specialty/DermatologySection.tsx:264

**`rows`**

- `3` ×2 — sample: ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112
- `2` ×1 — sample: ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128
- `4` ×2 — sample: ../frontend/src/components/emr-v2/sections/ExaminationSection.tsx:158

**`suggestions`**

- `{ id: unknown; content: unknown; source: string; confidence: number; }[]` ×1 — sample: ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112
- `unknown[]` ×3 — sample: ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128

**`showAIButton`**

- `false` ×1 — sample: ../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx:112
- `boolean` ×2 — sample: ../frontend/src/components/emr-v2/sections/ExaminationSection.tsx:158

**`onRequestAI`**

- `(text: string) => void` ×1 — sample: ../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx:128
- `(fieldName: any) => void` ×2 — sample: ../frontend/src/components/emr-v2/sections/ExaminationSection.tsx:158

#### Caller files

- `../frontend/src/components/emr-v2/sections/AnamnesisMorbiSection.tsx` — line: 112
- `../frontend/src/components/emr-v2/sections/DiagnosisSection.tsx` — line: 128
- `../frontend/src/components/emr-v2/sections/ExaminationSection.tsx` — line: 158
- `../frontend/src/components/emr-v2/sections/TreatmentSection.tsx` — line: 204
- `../frontend/src/components/emr-v2/sections/specialty/DermatologySection.tsx` — line: 264

### ComplaintsField

- **File:** `components/emr-v2/sections/ComplaintsField.tsx:37`
- **Declared props:** `value`, `onChange`, `isEditable`, `aiEnabled`, `onRequestAI`, `error`, `autoFocus`, `onFieldTouch`, `onBlur`, `label`, `placeholder`
- **JSX callers:** 1
- **Conflicts:** _none_
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `value` | '' |
| `onChange` | — |
| `isEditable` | true |
| `aiEnabled` | true |
| `onRequestAI` | — |
| `error` | — |
| `autoFocus` | false |
| `onFieldTouch` | — |
| `onBlur` | — |
| `label` | 'Жалобы' |
| `placeholder` | 'Введите жалобы пациента...' |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `aiEnabled` | `boolean` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |
| `isEditable` | `boolean` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |
| `label` | `string` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |
| `onChange` | `(value: string) => void` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |
| `onRequestAI` | `(text: any) => Promise<any>` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |
| `value` | `string` ×1 | ../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx:127 |

#### Caller files

- `../frontend/src/components/emr-v2/sections/ComplaintsSection.tsx` — line: 127

### PrescriptionEditor

- **File:** `components/emr-v2/sections/PrescriptionEditor.tsx:30`
- **Declared props:** `prescriptions`, `onChange`, `isEditable`, `onFieldTouch`
- **JSX callers:** 2
- **Conflicts:** 2
- **Recommended domain:** Generic → Build ad-hoc Props interface from observed prop names

#### Declared props (destructured in component signature)

| Prop | Default |
|------|--------|
| `prescriptions` | [] |
| `onChange` | — |
| `isEditable` | true |
| `onFieldTouch` | — |

#### Props observed in callers (with inferred TS types)

| Prop | Distinct types observed | Sample |
|------|--------------------------|--------|
| `isEditable` | `boolean` ×1<br>`true` ×1 | ../frontend/src/components/emr-v2/sections/TreatmentSection.tsx:228 |
| `onChange` | `(list: unknown[]) => void` ×1 | ../frontend/src/components/emr-v2/sections/TreatmentSection.tsx:228 |
| `prescriptions` | `unknown[]` ×1<br>`{ id: number; name: string; dose: string; frequency: string; duration: string; }[]` ×1 | ../frontend/src/components/emr-v2/sections/TreatmentSection.tsx:228 |

#### ⚠ Conflicts

Same prop name receives different types across callers. Resolve before writing the Props interface:

**`prescriptions`**

- `unknown[]` ×1 — sample: ../frontend/src/components/emr-v2/sections/TreatmentSection.tsx:228
- `{ id: number; name: string; dose: string; frequency: string; duration: string; }[]` ×1 — sample: ../frontend/src/components/emr-v2/sections/__tests__/PrescriptionEditor.accessibility.test.tsx:11

**`isEditable`**

- `boolean` ×1 — sample: ../frontend/src/components/emr-v2/sections/TreatmentSection.tsx:228
- `true` ×1 — sample: ../frontend/src/components/emr-v2/sections/__tests__/PrescriptionEditor.accessibility.test.tsx:11

#### Caller files

- `../frontend/src/components/emr-v2/sections/TreatmentSection.tsx` — line: 228
- `../frontend/src/components/emr-v2/sections/__tests__/PrescriptionEditor.accessibility.test.tsx` — line: 11

## Recommended execution order

Sprint F3 sub-sprints, ordered by ascending conflict count. Start with the lowest-conflict domain to validate the Props-interface migration pattern before tackling harder domains.

### EMR — 1 components, 0 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| EchoForm | 1 | 0 |

### Queue — 1 components, 0 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| QueuePositionCard | 1 | 0 |

### Scheduling — 1 components, 0 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| AppointmentFlow | 1 | 0 |

### Wizard/Cart — 2 components, 0 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| WelcomeView | 1 | 0 |
| CartStepV2 | 1 | 0 |

### Patients — 1 components, 1 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| PatientCard | 2 | 1 |

### Dental — 1 components, 2 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| TeethChart | 3 | 2 |

### Generic — 10 components, 17 conflicts

| Component | Callers | Conflicts |
|-----------|---------|-----------|
| PhoneVerification | 1 | 0 |
| DentalPatientsTab | 1 | 0 |
| DoctorServiceSelector | 1 | 0 |
| renderStatCard | 4 | 0 |
| Table | 19 | 7 |
| ModernQueueManager | 2 | 2 |
| QueueTable | 1 | 0 |
| EMRSmartFieldV2 | 5 | 6 |
| ComplaintsField | 1 | 0 |
| PrescriptionEditor | 2 | 2 |

