/**
 * EMR v2 Components
 * 
 * Phase 1: Foundation (reducer, useEMR, basic container)
 * Phase 2: Reliability (autosave, navigation guard, status indicator)
 * Phase 3: Control (history, diff viewer, conflict dialog)
 * Phase 4: UI Migration (modular sections, EMRContainerV2)
 */

// ============================================
// PHASE 1 - Foundation
// ============================================
export { EMRContainer } from './EMRContainer';

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
export { useEMRVersion } from '../../hooks/useEMRVersion';
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
    useEMRAI,
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

