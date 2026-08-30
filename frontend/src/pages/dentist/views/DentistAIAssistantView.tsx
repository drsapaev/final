import { Card } from '../../../components/ui/macos';
import AIAssistant from '../../../components/ai/AIAssistant';
import notify from '../../../services/notify';
import logger from '../../../utils/logger';

/**
 * PR-UI-15-6: the AI assistant tab view — verbatim JSX of the former
 * DentistPanelUnified.renderAIAssistant.
 */
export default function DentistAIAssistantView({
  tI18n,
}: {
  tI18n: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_ai_title')}</h3>
        <AIAssistant
        specialty="dentistry"
        onSuggestionSelect={(type, suggestion) => {
          logger.info('[Dentistry] AI suggestion:', { type, suggestion });
          if (type === 'icd10') {
            notify.success(tI18n('dental.icd_added_from_ai'));
          }
        }} />

      </Card>
    </div>);
}
