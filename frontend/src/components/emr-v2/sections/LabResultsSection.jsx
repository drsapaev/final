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
import { FileText, Download, TestTube, Plus } from 'lucide-react';
import EMRSection from './EMRSection';
import { labReportingApi } from '../../../api/labReporting';
import { Badge, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '../../ui/macos';
import logger from '../../../utils/logger';
import notify from '../../../services/notify';

const STATUS_LABELS = {
  DRAFT: 'Черновик',
  IN_PROGRESS: 'В работе',
  FINALIZED: 'Готов',
  PRINTED: 'Напечатан',
  ARCHIVED: 'Архив',
};

const STATUS_VARIANTS = {
  DRAFT: 'default',
  IN_PROGRESS: 'warning',
  FINALIZED: 'success',
  PRINTED: 'info',
  ARCHIVED: 'default',
};

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
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [ordering, setOrdering] = useState(false);

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
      return <div style={{ padding: '12px', color: 'var(--mac-text-secondary)' }}>Загрузка результатов анализов…</div>;
    }

    if (error) {
      return <div style={{ padding: '12px', color: 'var(--mac-error)' }}>{error}</div>;
    }

    if (instances.length === 0) {
      return (
        <div style={{ padding: '12px', color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          Нет готовых результатов анализов для этого пациента.
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
              <TestTube size={16} style={{ color: 'var(--mac-text-secondary)', flexShrink: 0 }} aria-hidden="true" />
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
              <Badge variant={STATUS_VARIANTS[instance.status] || 'default'} size="small">
                {STATUS_LABELS[instance.status] || instance.status}
              </Badge>
              {!disabled && (
                <Button
                  variant="outline"
                  size="small"
                  onClick={() => handleDownload(instance.id)}
                  aria-label={`Скачать PDF: ${instance.template_name || 'лабораторный отчёт'}`}>
                  <Download size={14} style={{ marginRight: 4 }} />
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
        icon={<FileText size={16} aria-hidden="true" />}
        disabled={disabled}
        defaultOpen={instances.length > 0}
        headerAction={!disabled && patientId ? (
          <Button variant="outline" size="small" onClick={handleOpenOrderModal}>
            <Plus size={14} style={{ marginRight: 4 }} />
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
                <div style={{ color: 'var(--mac-text-secondary)' }}>Загрузка шаблонов…</div>
              ) : templates.length === 0 ? (
                <div style={{ color: 'var(--mac-text-secondary)' }}>
                  Нет опубликованных шаблонов анализов.
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
                    <TestTube size={20} style={{ color: 'var(--mac-text-secondary)' }} />
                  </button>
                ))
              )}
            </div>
          </DialogContent>
          <DialogActions>
            <Button variant="outline" onClick={() => setShowOrderModal(false)}>Закрыть</Button>
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
