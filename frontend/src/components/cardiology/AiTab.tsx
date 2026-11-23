/**
 * AiTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "AI" (AI помощник) tab content — AIAssistant for
 * ICD-10 suggestions and complaint analysis.
 *
 * Cardioplan slice 4: the AI tab is READ-ONLY for the cardiology panel —
 * no "apply" action and no success notification, because applying a hint
 * here only mutated detached panel-local state. Applying suggestions stays
 * inside the EMR editor (AISuggestionPopover → setField), where the doctor
 * sees and confirms the resulting values (save/sign).
 *
 * CARDAI-FE-001 (audit 3886): this mount passes no patient/clinical
 * `data`, so the assistant renders its explicit no-context state (no
 * provider controls, no refresh action) instead of an inert false
 * affordance. Contextual AI analysis lives in the EMR editor.
 */

import AIAssistant from '../ai/AIAssistant';
import { useTranslation } from '../../i18n/useTranslation';

export function AiTab(): React.JSX.Element | null {
  const { t } = useTranslation();
  void t;
  return (
    <div className="cardio-w-full-visible">
      {/* No onSuggestionSelect → AIAssistant renders no per-item apply button. */}
      <AIAssistant specialty="cardiology" />
    </div>
  );
}


export default AiTab;
