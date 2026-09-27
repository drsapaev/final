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
