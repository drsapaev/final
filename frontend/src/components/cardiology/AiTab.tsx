/**
 * AiTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "AI" (AI помощник) tab content — AIAssistant for
 * ICD-10 suggestions and complaint analysis.
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import PropTypes from 'prop-types';
import AIAssistant from '../ai/AIAssistant';
import { useTranslation } from '../../i18n/useTranslation';

interface AiTabProps {
  onSuggestionSelect: (suggestion: unknown) => void;
}

export function AiTab({ onSuggestionSelect }: AiTabProps) {
  const { t } = useTranslation();
  void t;
  return (
    <div className="cardio-w-full-visible">
      <AIAssistant
        specialty="cardiology"
        onSuggestionSelect={onSuggestionSelect}
      />
    </div>
  );
}

AiTab.propTypes = {
  onSuggestionSelect: PropTypes.func.isRequired,
};

export default AiTab;
