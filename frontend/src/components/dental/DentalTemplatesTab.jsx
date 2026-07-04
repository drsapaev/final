/**
 * DentalTemplatesTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Шаблоны" tab: ProtocolTemplates + management button.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { FileText } from 'lucide-react';
import ProtocolTemplates from './ProtocolTemplates';

export function DentalTemplatesTab({
  onManageTemplates,
  templates = [],
  onApplyTemplate,
}) {
  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="lg">
        <div className="dental-flex-between-16">
          <div>
            <h3 className="dental-text-primary">Шаблоны протоколов</h3>
            <p className="dental-text-desc dental-text-secondary">
              Стандартные протоколы для быстрого создания протоколов визитов
            </p>
          </div>
          <Button onClick={onManageTemplates} className="dental-flex dental-gap-8">
            <FileText className="dental-icon-16" />
            Управление шаблонами
          </Button>
        </div>

        {templates.length > 0 ? (
          <div className="dental-grid-auto-fill-280 dental-mt-16">
            {templates.map((template) => (
              <div key={template.id} className="dental-protocol-card-flex">
                <div className="dental-text-primary">{template.name}</div>
                <div className="dental-text-desc dental-text-secondary">
                  {template.category} - {template.estimatedTime || '—'} мин
                </div>
                {template.description && (
                  <div className="dental-text-desc dental-text-secondary">
                    {template.description}
                  </div>
                )}
                <Button
                  variant="outline"
                  onClick={() => onApplyTemplate(template)}
                  className="dental-align-self-start dental-mt-8">
                  Применить
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="dental-text-center dental-p-48 dental-text-secondary">
            Шаблоны протоколов будут доступны в следующей версии. Используйте вкладку «Протоколы визитов» для создания протокола вручную.
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
