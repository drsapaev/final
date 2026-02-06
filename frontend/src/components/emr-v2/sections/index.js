/**
 * EMR v2 Sections
 * 
 * Phase 4: UI Migration - Modular sections
 * 
 * Each section:
 * - Receives data + setField from parent
 * - Has no internal EMR state
 * - Does not know about API, version, autosave
 * - Is testable in isolation
 */

// Base components
export { EMRSection } from './EMRSection';
export { EMRTextField } from './EMRTextField';
export { EMRSmartFieldV2 } from './EMRSmartFieldV2';

// Phase 4.1 - Simple text sections
export { ComplaintsSection } from './ComplaintsSection';
export { AnamnesisMorbiSection } from './AnamnesisMorbiSection';
export { AnamnesisVitaeSection } from './AnamnesisVitaeSection';
export { RecommendationsSection } from './RecommendationsSection';

// Phase 4.2 - Structured but local
export { ExaminationSection } from './ExaminationSection';
export { NotesSection } from './NotesSection';
export { TreatmentSection } from './TreatmentSection';

// Phase 4.3 - Connected to external
export { DiagnosisSection } from './DiagnosisSection';
