import PropTypes from 'prop-types';
import { Alert, Card } from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * L-H-6 fix: PreviewTab выделен в отдельный файл (~70 строк).
 * Phase 4+ tab 4: read-only sample render of the template.
 * Shows branding + sections + fields as they'll appear in the PDF.
 */
function PreviewTab({ draftVersion }) {
  const { t } = useTranslation();
  const branding = draftVersion.branding_overrides || {};
  const signers = draftVersion.signer_defaults || {};

  return (
    <div className="ltw-grid-16">
      <Alert severity="info">
        Предпросмотр показывает структуру бланка. Финальный PDF рендерится на backend.
      </Alert>

      <Card variant="filled" padding="default">
        <div className="ltw-preview-header">
          {branding.clinic_name && <div className="ltw-section-title">{branding.clinic_name}</div>}
          {branding.document_title && <div className="ltw-text-18 ltw-fw-700">{branding.document_title}</div>}
          {branding.document_subtitle && <div className="ltw-text-13 ltw-text-secondary">{branding.document_subtitle}</div>}
          {branding.address && <div className="ltw-text-12 ltw-text-secondary">{branding.address}</div>}
          {branding.phone && <div className="ltw-text-12 ltw-text-secondary">{branding.phone}</div>}
        </div>

        {draftVersion.sections.map((section, sectionIndex) => (
          <div key={sectionIndex} className="ltw-preview-section">
            <div className="ltw-preview-section-title">
              {section.title || section.key}
            </div>
            <table className="ltw-preview-table">
              <thead>
                <tr className="ltw-preview-row">
                  <th className="ltw-preview-th">Показатель</th>
                  <th className="ltw-preview-th">Значение</th>
                  <th className="ltw-preview-th">Единица</th>
                  <th className="ltw-preview-th">Норма</th>
                </tr>
              </thead>
              <tbody>
                {section.fields.map((field, fieldIndex) => (
                  <tr key={fieldIndex} className="ltw-preview-row">
                    <td className="ltw-preview-td">
                      {field.label || field.field_key}
                      {field.required && <span className="ltw-text-error">*</span>}
                    </td>
                    <td className="ltw-preview-td-secondary">—</td>
                    <td className="ltw-preview-td-secondary">{field.unit || ''}</td>
                    <td className="ltw-preview-td-secondary">{field.reference_text || (field.reference_mode === 'rule_based' ? '(по правилам)' : '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        {draftVersion.footer_notes && (
          <div className="ltw-preview-footer">
            {draftVersion.footer_notes}
          </div>
        )}

        <div className="ltw-preview-signers">
          <div>
            <div className="ltw-text-secondary">{signers.lab_technician_label || 'Лаборант'}:</div>
            <div className="ltw-preview-signer-line">
              {signers.lab_technician_name || '_______________'}
            </div>
          </div>
          <div>
            <div className="ltw-text-secondary">{signers.approver_label || 'Подпись'}:</div>
            <div className="ltw-preview-signer-line">
              {signers.approver_name || '_______________'}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

PreviewTab.propTypes = {
  draftVersion: PropTypes.object.isRequired,
};

export default PreviewTab;
