/**
 * LabResultsSection — displays lab report instances for the current patient/visit.
 *
 * P0 fix: previously doctors had no way to see lab panel results during a visit.
 * Cardiologist had a separate CardioBloodTest table (manually entered), derma/dental
 * had nothing. This section reads from the canonical LabReportInstance model via
 * labReportingApi, so all doctor panels see the same data the lab panel produces.
 *
 * Renders:
 *   - List of finalized/printed lab reports (template name, date, status badge)
 *   - "Open PDF" button per report (downloads via labReportingApi.downloadPdf)
 *   - Empty state when no results exist
 *   - Collapsible (defaultOpen=false — supplementary data, not needed on every visit)
 */

import { useEffect, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
// UX-AUDIT-FIX6: lucide-react заменён на macos Icon для консистентности со
// всеми остальными lab-компонентами. Смешивание двух библиотек иконок
// (lucide + macos SF-Symbol-style) нарушало Nielsen Heuristic #4
// (Consistency & Standards) — разные stroke-width, optical size, padding.
import EMRSection from './EMRSection';
import { labReportingApi } from '../../../api/labReporting';
import { Badge, Button, Dialog, DialogTitle, DialogContent, DialogActions, Icon } from '../../ui/macos';
import { useConfirm } from '../../common/ConfirmDialog';
// UX-AUDIT-FIX10: ранее STATUS_LABELS / STATUS_VARIANTS дублировались локально.
// Комментарий "PR-58: unified with labUiLabels.js" обещал SSOT, но реально
// был вынесен только один лейбл. При добавлении нового статуса (например,
// CANCELLED) забыли бы обновить LabResultsSection — пациенту показалось бы
// 'Unknown'. Теперь используется единый источник истины.
import { formatLabStatus, getLabStatusVariant } from '../../laboratory/labUiLabels';
// STRAT#12: t() и tInterpolate() для i18n — order confirm dialog мигрирован.
import logger from '../../../utils/logger';
import notify from '../../../services/notify';
import { useTranslation } from '../../../i18n/useTranslation';

// UX-AUDIT-FIX10: STATUS_LABELS и STATUS_VARIANTS удалены —
// используются formatLabStatus() и getLabStatusVariant() из labUiLabels.js.

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

export function LabResultsSection({ patientId, visitId, disabled = false }) {
  const { t } = useTranslation();
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [ordering, setOrdering] = useState(false);

  // UX-AUDIT-FIX9: useConfirm для подтверждения создания заказа на анализы.
  // Ранее один клик в модалке «Заказать анализы» мгновенно создавал заказ
  // через labReportingApi.createOrder — без подтверждения и без возможности
  // отмены. Лаборатория сразу видела новый заказ в очереди. Если врач
  // промахивался мимо нужного шаблона — приходилось идти в лабораторию
  // и просить отменить. Соответствует Nielsen Heuristic #5 (Error Prevention).
  const [confirm] = useConfirm();

  const loadInstances = useCallback(async () => {
    if (!patientId && !visitId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 20 };
      if (visitId) params.visit_id = visitId;
      else if (patientId) params.patient_id = patientId;

      const result = await labReportingApi.listInstances(params);
      const list = Array.isArray(result) ? result : (result?.items || []);
      // Only show finalized/printed — drafts are lab-internal.
      setInstances(list.filter((r) => r.status === 'FINALIZED' || r.status === 'PRINTED'));
    } catch (err) {
      logger.warn('[LabResultsSection] Failed to load lab instances', { error: err?.message });
      setError('Не удалось загрузить результаты анализов.');
      setInstances([]);
    } finally {
      setLoading(false);
    }
  }, [patientId, visitId]);

  useEffect(() => {
    loadInstances();
  }, [loadInstances]);

  const handleDownload = async (instanceId) => {
    try {
      const blob = await labReportingApi.downloadPdf(instanceId);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      logger.error('[LabResultsSection] PDF download failed', { error: err?.message });
    }
  };

  // P1 fix: Order lab tests — opens a modal listing published templates.
  const handleOpenOrderModal = async () => {
    setShowOrderModal(true);
    setTemplatesLoading(true);
    try {
      const result = await labReportingApi.listTemplates();
      const list = Array.isArray(result) ? result : (result?.items || []);
      // Only show templates that have a published version.
      setTemplates(list.filter((t) => t.published_version_id));
    } catch (err) {
      logger.warn('[LabResultsSection] Failed to load templates', { error: err?.message });
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  };

  const handleOrder = async (templateId, templateName) => {
    // UX-AUDIT-FIX9: подтверждение перед созданием заказа.
    // STRAT#12: строки мигрированы на t() / tInterpolate() из labTranslations.
    const ok = await confirm({
      title: t('confirm.order_title'),
      message: t('confirm.order_message', { name: templateName }),
      description: t('confirm.order_description'),
      confirmLabel: t('confirm.order_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'primary',
    });
    if (!ok) return;
    setOrdering(true);
    try {
      await labReportingApi.createOrder({
        template_id: templateId,
        patient_id: patientId,
        visit_id: visitId,
      });
      notify.success(`Заказ «${templateName}» создан. Лаборатория увидит его в очереди.`);
      setShowOrderModal(false);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Не удалось создать заказ.';
      notify.error(typeof msg === 'string' ? msg : 'Не удалось создать заказ.');
    } finally {
      setOrdering(false);
    }
  };

  const renderContent = () => {
    if (loading) {
      return <div style={{ padding: '12px', color: 'var(--mac-text-secondary)' }}>{t('empty.loading_results')}</div>;
    }

    if (error) {
      return <div style={{ padding: '12px', color: 'var(--mac-error)' }}>{error}</div>;
    }

    if (instances.length === 0) {
      return (
        <div style={{ padding: '12px', color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          {t('empty.no_lab_results')}
        </div>
      );
    }

    return (
      <div style={{ display: 'grid', gap: '8px', padding: '8px 0' }}>
        {instances.map((instance) => (
          <div
            key={instance.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '10px 12px',
              border: '1px solid var(--mac-border)',
              borderRadius: '8px',
              background: 'var(--mac-bg-secondary)',
            }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
              <Icon name="testtube.2" size={16} color="secondary" aria-hidden="true" />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: '14px', color: 'var(--mac-text-primary)' }}>
                  {instance.template_name || instance.template_code || 'Лабораторный отчёт'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                  {formatDate(instance.finalized_at || instance.updated_at)}
                  {instance.flagged_findings_count > 0 && (
                    <span style={{ marginLeft: '8px', color: 'var(--mac-warning)' }}>
                      ⚠ {instance.flagged_findings_count} отклонений
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <Badge variant={getLabStatusVariant(instance.status) || 'default'} size="small">
                {formatLabStatus(instance.status) || instance.status}
              </Badge>
              {!disabled && (
                <Button
                  variant="outline"
                  size="small"
                  onClick={() => handleDownload(instance.id)}
                  aria-label={`Скачать PDF: ${instance.template_name || 'лабораторный отчёт'}`}>
                  <Icon name="square.and.arrow.down" size={14} style={{ marginRight: 4 }} aria-hidden="true" />
                  PDF
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      <EMRSection
        title="Результаты анализов"
        icon={<Icon name="doc.text" size={16} aria-hidden="true" />}
        disabled={disabled}
        defaultOpen={instances.length > 0}
        headerAction={!disabled && patientId ? (
          <Button variant="outline" size="small" onClick={handleOpenOrderModal}>
            <Icon name="plus" size={14} style={{ marginRight: 4 }} aria-hidden="true" />
            Заказать анализы
          </Button>
        ) : null}
      >
        {renderContent()}
      </EMRSection>

      {/* P1 fix: Order lab tests modal */}
      {showOrderModal && (
        <Dialog open={showOrderModal} onClose={() => setShowOrderModal(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Заказать анализы</DialogTitle>
          <DialogContent>
            <div style={{ paddingTop: '8px', display: 'grid', gap: '8px' }}>
              {templatesLoading ? (
                <div style={{ color: 'var(--mac-text-secondary)' }}>{t('empty.loading_templates')}</div>
              ) : templates.length === 0 ? (
                <div style={{ color: 'var(--mac-text-secondary)' }}>
                  {t('empty.no_templates')}
                </div>
              ) : (
                templates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => handleOrder(template.id, template.name)}
                    disabled={ordering}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '8px',
                      padding: '12px',
                      border: '1px solid var(--mac-border)',
                      borderRadius: '10px',
                      background: 'var(--mac-bg-primary)',
                      cursor: ordering ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                    }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--mac-text-primary)' }}>
                        {template.name}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                        {template.code} • {template.family}
                      </div>
                    </div>
                    <Icon name="testtube.2" size={20} color="secondary" aria-hidden="true" />
                  </button>
                ))
              )}
            </div>
          </DialogContent>
          <DialogActions>
            <Button variant="outline" onClick={() => setShowOrderModal(false)}>{t('common.close')}</Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}

LabResultsSection.propTypes = {
  patientId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  visitId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  disabled: PropTypes.bool,
};

export default LabResultsSection;
