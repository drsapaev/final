
import { Alert, Button, Card } from '../../ui/macos';
import React, { useState } from 'react';
import { labReportingApi } from '../../../api/labReporting';
import { FileText } from 'lucide-react';

interface PreviewTabField {
  label?: string;
  field_key?: string;
  required?: boolean;
  unit?: string;
  reference_text?: string;
  reference_mode?: string;
}

interface PreviewTabSection {
  title?: string;
  key?: string;
  fields: PreviewTabField[];
}

interface PreviewTabDraftVersion {
  id?: string | number;
  branding_overrides?: Record<string, string>;
  signer_defaults?: Record<string, string>;
  sections: PreviewTabSection[];
  footer_notes?: string;
  [key: string]: unknown;
}

interface PreviewTabProps {
  draftVersion: PreviewTabDraftVersion;
}

/**
 * L-H-6 fix: PreviewTab выделен в отдельный файл (~70 строк).
 * Phase 4+ tab 4: read-only sample render of the template.
 * Shows branding + sections + fields as they'll appear in the PDF.
 *
 * PR8 (codex-lab-workflow-hardening-plan): добавлен серверный PDF-preview —
 * точный A4-рендер ТОГО ЖЕ движка, что пойдёт на печать. Рендерится
 * СОХРАНЁННАЯ версия шаблона (синтетические placeholder-значения, без
 * данных пациентов; неопубликованная версия помечена watermark
 * «Черновик»). Unsaved-изменения редактора в PDF не попадают — сначала
 * Save (PUT /lab/template-versions/{id}).
 */
function PreviewTab({ draftVersion }: PreviewTabProps) {
  const branding = draftVersion.branding_overrides || {};
  const signers = draftVersion.signer_defaults || {};
  const [pdfPending, setPdfPending] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  async function handleServerPdfPreview() {
    const versionId = draftVersion?.id;
    if (!versionId || pdfPending) return;
    setPdfPending(true);
    setPdfError(null);
    try {
      const blob = await labReportingApi.previewTemplateVersionPdf(versionId);
      if (!blob || !(blob instanceof Blob)) {
        setPdfError('PDF сформирован некорректно. Обратитесь к администратору.');
        return;
      }
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setPdfError('Не удалось сформировать PDF-предпросмотр. Сохраните черновик и попробуйте снова.');
    } finally {
      setPdfPending(false);
    }
  }

  return (
    <div className="ltw-grid-16">
      <Alert severity="info">
        Предпросмотр показывает структуру бланка. Финальный PDF рендерится на backend.
      </Alert>

      <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
        <Button
          variant="outline"
          onClick={handleServerPdfPreview}
          disabled={pdfPending || !draftVersion?.id}
          title="Серверный A4-рендер сохранённой версии — тот же движок, что печать; неопубликованная версия помечена «Черновик»"
        >
          <FileText size={16} aria-hidden="true" />
          {pdfPending ? 'Формирую…' : 'PDF-предпросмотр (сервер)'}
        </Button>
        <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
          показывает сохранённую версию — сначала «Сохранить черновик»
        </span>
      </div>
      {pdfError && (
        <Alert severity="error">{pdfError}</Alert>
      )}

      <Card variant="filled" padding="default">
        <div className="ltw-preview-header">
          {branding.clinic_name && <div className="ltw-section-title">{branding.clinic_name}</div>}
          {branding.document_title && <div className="ltw-text-18 ltw-fw-700">{branding.document_title}</div>}
          {branding.document_subtitle && <div className="ltw-text-13 ltw-text-secondary">{branding.document_subtitle}</div>}
          {branding.address && <div className="ltw-text-12 ltw-text-secondary">{branding.address}</div>}
          {branding.phone && <div className="ltw-text-12 ltw-text-secondary">{branding.phone}</div>}
        </div>

        {draftVersion.sections.map((section: PreviewTabSection, sectionIndex: number) => (
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
                {section.fields.map((field: PreviewTabField, fieldIndex: number) => (
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


export default PreviewTab;
