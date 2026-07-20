
/**
 * EMR v2 Components
 * 
 * Phase 1: Foundation (reducer, useEMR)
 * Phase 2: Reliability (autosave, navigation guard, status indicator)
 * Phase 3: Control (history, diff viewer, conflict dialog)
 * Phase 4: UI Migration (modular sections, EMRContainerV2)
 */

// ============================================
// PHASE 2 - Reliability
// ============================================
export { EMRStatusIndicator } from './EMRStatusIndicator';

// ============================================
// PHASE 3 - Control
// ============================================
export { EMRHistoryPanel } from './EMRHistoryPanel';
export { EMRDiffViewer } from './EMRDiffViewer';
export { EMRConflictDialog } from './EMRConflictDialog';

// ============================================
// PHASE 4 - UI Migration
// ============================================
export { EMRContainerV2 } from './EMRContainerV2';

// Sections (use for custom layouts)
export {
    EMRSection,
    EMRTextField,
    EMRSmartFieldV2,
    ComplaintsField,
    ExaminationMatrix,
    VitalsWidget,
    PrescriptionEditor,
    ComplaintsSection,
    AnamnesisMorbiSection,
    AnamnesisVitaeSection,
    ExaminationSection,
    DiagnosisSection,
    TreatmentSection,
    RecommendationsSection,
    NotesSection,
} from './sections';

// ============================================
// HOOKS
// ============================================
export { useEMR } from '../../hooks/useEMR';
export { useEMRAutosave } from '../../hooks/useEMRAutosave';
export { useNavigationGuard, useBeforeUnload } from '../../hooks/useNavigationGuard';
export { useEMRKeyboard } from '../../hooks/useEMRKeyboard';
export { useDoctorHistory } from '../../hooks/useDoctorHistory';
export { useEMRTelemetry } from '../../hooks/useEMRTelemetry';

// ============================================
// REDUCER
// ============================================
export { emrReducer, emrActions, EMR_ACTIONS } from '../../reducers/emrReducer';

// ============================================
// AI (suggestion only - doctor must confirm)
// ============================================
export {
    AISuggestionCard,
    AISuggestionPanel,
    AISuggestionPopover,
    SmartAssistButton,
    CompletenessChecker,
    PhraseSuggestions,
} from './ai';

// ============================================
// TEMPLATES (click-only insert)
// ============================================
export { TreatmentTemplatesPanel, TreatmentTemplatesButton } from './templates';

// ============================================
// DOCTOR TEMPLATES (universal "Мой опыт")
// ============================================
export { DoctorTemplatesPanel, DoctorTemplatesButton } from './DoctorTemplatesPanel';

