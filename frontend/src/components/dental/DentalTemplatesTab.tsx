
/**
 * DentalTemplatesTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Шаблоны" tab: ProtocolTemplates + management button.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { FileText } from 'lucide-react';
import ProtocolTemplates from './ProtocolTemplates';
import { useTranslation } from '../../i18n/useTranslation';

type TFunc = (key: string, options?: Record<string, unknown>) => string;

interface DentalTemplate {
  id: string | number;
  name: string;
  category?: string;
  estimatedTime?: string;
  description?: string;
}

export function DentalTemplatesTab({
  onManageTemplates,
  templates = [],
  onApplyTemplate,
}: {
  onManageTemplates?: () => void;
  templates?: DentalTemplate[];
  onApplyTemplate?: (template: DentalTemplate) => void;
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as TFunc;
  const typedTemplates: DentalTemplate[] = templates;
  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <div className="dental-flex-between-16">
          <div>
            <h3 className="dental-text-primary">{t('dental.dental_dtt_title')}</h3>
            <p className="dental-text-desc dental-text-secondary">
              {t('dental.dental_dtt_subtitle')}
            </p>
          </div>
          <Button onClick={onManageTemplates} className="dental-flex dental-gap-8">
            <FileText className="dental-icon-16" />
            {t('dental.dental_dtt_btn_manage')}
          </Button>
        </div>

        {typedTemplates.length > 0 ? (
          <div className="dental-grid-auto-fill-280 dental-mt-16">
            {typedTemplates.map((template) => (
              <div key={template.id} className="dental-protocol-card-flex">
                <div className="dental-text-primary">{template.name}</div>
                <div className="dental-text-desc dental-text-secondary">
                  {t('dental.dental_dtt_template_meta', { category: template.category, time: template.estimatedTime || '—' })}
                </div>
                {template.description && (
                  <div className="dental-text-desc dental-text-secondary">
                    {template.description}
                  </div>
                )}
                <Button
                  variant="outline"
                  onClick={() => onApplyTemplate?.(template)}
                  className="dental-align-self-start dental-mt-8">
                  {t('dental.dental_dtt_btn_apply')}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="dental-text-center dental-p-48 dental-text-secondary">
            {t('dental.dental_dtt_empty')}
          </div>
        )}
      </Card>
    </div>
  );
}

DentalTemplatesTab.propTypes = {
  onManageTemplates: PropTypes.func,
  templates: PropTypes.array,
  onApplyTemplate: PropTypes.func,
};

export default DentalTemplatesTab;
