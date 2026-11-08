
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

import { useEffect, useRef, useState, useCallback } from 'react';
// UX-AUDIT-FIX6 (история, направление ОТМЕНЕНО Track 3-2, §3.3 / Plan v2.10):
// macos-Icon обёртка → прямые lucide-react импорты. Канонический end-state —
// одна иконок-система (lucide), Nielsen Heuristic #4 сохраняется в обратную
// сторону: консистентность с 146+ lucide-файлов проекта.
import EMRSection from './EMRSection';
import React from 'react';
// ADR-0015: use useLabReporting hook instead of importing api/labReporting directly.
import { useLabReporting } from '@/hooks/useLabReporting';
import { Badge, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '../../ui/macos';
import { useConfirm } from '../../common/ConfirmDialog';
// UX-AUDIT-FIX10: ранее STATUS_LABELS / STATUS_VARIANTS дублировались локально.
// Комментарий "PR-58: unified with labUiLabels.js" обещал SSOT, но реально
// был вынесен только один лейбл. При добавлении нового статуса (например,
// CANCELLED) забыли бы обновить LabResultsSection — пациенту показалось бы
// 'Unknown'. Теперь используется единый источник истины.
import { formatLabStatus, getLabStatusVariant } from '../../laboratory/labUiLabels';
// STRAT#12: t() и tInterpolate() для i18n — order confirm dialog мигрирован.
import logger from '@/utils/logger';
import notify from '@/services/notify';
import { useTranslation } from '@/i18n/useTranslation';
import { getErrorMessage } from '../../../utils/type-guards';
import { Download, FileText, Plus, TestTube2 } from 'lucide-react';

// UX-AUDIT-FIX10: STATUS_LABELS и STATUS_VARIANTS удалены —
// используются formatLabStatus() и getLabStatusVariant() из labUiLabels.js.

interface LabReportInstance {
  id: string | number;
  template_name?: string;
  template_code?: string;
  finalized_at?: string;
  updated_at?: string;
  flagged_findings_count?: number;
  status?: string;
}

interface LabTemplate {
  id: string | number;
  name?: string;
  code?: string;
  family?: string;
  published_version_id?: string | number | null;
}

interface LabResultsSectionProps {
  patientId?: string | number | null;
  visitId?: string | number | null;
  disabled?: boolean;
}

function formatDate(dateStr: unknown): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr as string | number | Date).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

export function LabResultsSection({ patientId, visitId, disabled = false }: LabResultsSectionProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  // ADR-0015: lab reporting API accessed via hook.
  const labReportingApi = useLabReporting();
  const [instances, setInstances] = useState<LabReportInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [templates, setTemplates] = useState<LabTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [ordering, setOrdering] = useState(false);

  // UX-AUDIT-FIX9: useConfirm для подтверждения создания заказа на анализы.
  // Ранее один клик в модалке «Заказать анализы» мгновенно создавал заказ
  // через labReportingApi.createOrder — без подтверждения и без возможности
  // отмены. Лаборатория сразу видела новый заказ в очереди. Если врач
  // промахивался мимо нужного шаблона — приходилось идти в лабораторию
  // и просить отменить. Соответствует Nielsen Heuristic #5 (Error Prevention).
  const [confirm] = useConfirm();

  // EMRLAB-FE-002 (audit 3886, round 15): epoch-guard — ответы/ошибки
  // superseded-контекста больше не могут перезаписать списки/spinner
  // нового пациента; пустой контекст (null/null) немедленно чистит
  // предыдущие строки.
  const requestEpochRef = useRef(0);

  // EMRORDER-FE-001 (audit 3886, round 19): the mounted section can be
  // re-rendered in place for ANOTHER patient/visit while a confirmation
  // dialog or template fetch is pending. The latest mounted context is
  // tracked in a ref; every async completion (confirm resolution, template
  // list, createOrder ACK) re-checks it against the context the intent was
  // STARTED in and drops stale intents instead of dispatching them under
  // the new visit's header.
  const contextRef = useRef({ patientId, visitId });
  contextRef.current = { patientId, visitId };

  const loadInstances = useCallback(async (epoch: number) => {
    if (epoch !== requestEpochRef.current) return;
    if (!patientId && !visitId) {
      setInstances([]);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // EMRLAB-FE-001: канонические параметры контракта list-роута —
      // visit_ids-МАССИВ (не несуществующий singular visit_id, который
      // сервер игнорировал, отдавая Doctor'у все его визиты) плюс
      // patient_id ОБА, когда известны оба. Render-time второй пояс
      // ниже отбрасывает записи с чужим контекстом.
      // EMRLAB-FE-003: статус фильтруется СЕРВЕРОМ ДО лимита: без
      // статус-параметра 20 более новых черновиков могли вытеснить
      // старые финализированные записи за пределы limit, и клиентский
      // фильтр показывал «нет результатов». Постранично добираем каждый
      // статус до исчерпания (защитный потолок на цикл пагинации).
      const collected: LabReportInstance[] = [];
      const PAGE = 50;
      const MAX_PAGES_PER_STATUS = 5;
      for (const status of ['FINALIZED', 'PRINTED'] as const) {
        let offset = 0;
        for (let page = 0; page < MAX_PAGES_PER_STATUS; page += 1) {
          const params: Record<string, unknown> = {
            limit: PAGE,
            offset,
            status,
          };
          if (patientId != null) params.patient_id = patientId;
          if (visitId != null) params.visit_ids = [visitId];
          const result = await labReportingApi.listInstances(params);
          if (epoch !== requestEpochRef.current) return;
          const list = Array.isArray(result)
            ? result
            : ((result as Record<string, unknown>)?.items || []);
          collected.push(...(list as LabReportInstance[]));
          if ((list as unknown[]).length < PAGE) break;
          offset += PAGE;
        }
      }
      if (epoch !== requestEpochRef.current) return;
      // Второй пояс (render-time sanity): в списке — только финализированные
      // записи текущего контекста; дубли по id подавляются, порядок —
      // новее-первый по дате финализации.
      const seenIds = new Set<string>();
      const merged = collected
        .filter((r) => r.status === 'FINALIZED' || r.status === 'PRINTED')
        .filter((r) => {
          const key = String(r.id);
          if (seenIds.has(key)) return false;
          seenIds.add(key);
          return true;
        })
        .sort(
          (a, b) =>
            new Date(b.finalized_at || b.updated_at || 0).getTime()
            - new Date(a.finalized_at || a.updated_at || 0).getTime(),
        );
      setInstances(merged);
    } catch (err: unknown) {
      if (epoch !== requestEpochRef.current) return;
      const errShape = err as { message?: string };
      logger.warn('[LabResultsSection] Failed to load lab instances', { error: errShape?.message });
      setError('Не удалось загрузить результаты анализов.');
      setInstances([]);
    } finally {
      if (epoch === requestEpochRef.current) setLoading(false);
    }
  }, [patientId, visitId]);

  useEffect(() => {
    // EMRLAB-FE-002: смена контекста — мгновенная очистка и новая эпоха;
    // поздние ответы предыдущей эпохи отбрасываются целиком.
    const epoch = requestEpochRef.current + 1;
    requestEpochRef.current = epoch;
    setInstances([]);
    setError(null);
    setLoading(Boolean(patientId || visitId));
    void loadInstances(epoch);
    return () => {
      requestEpochRef.current += 1;
    };
  }, [patientId, visitId, loadInstances]);

  const handleDownload = async (instanceId: string | number) => {
    try {
      const blob = await labReportingApi.downloadPdf(instanceId);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err: unknown) {
      const errShape = err as { message?: string };
      logger.error('[LabResultsSection] PDF download failed', { error: errShape?.message });
    }
  };

  // EMRORDER-FE-001 (audit 3886, round 19): a patient/visit switch
  // invalidates the order-modal state — the pending confirmation intent
  // and the async template list belonged to the PREVIOUS visit and must
  // not survive into the new context's UI. (The confirm promise itself is
  // resolved by the shared dialog; the recheck in handleOrder drops it.)
  useEffect(() => {
    setShowOrderModal(false);
    setTemplates([]);
    setTemplatesLoading(false);
  }, [patientId, visitId]);

  // P1 fix: Order lab tests — opens a modal listing published templates.
  const handleOpenOrderModal = async () => {
    const startContext = contextRef.current;
    setShowOrderModal(true);
    setTemplatesLoading(true);
    try {
      const result = await labReportingApi.listTemplates();
      // EMRORDER-FE-001: the modal was (re)opened under `startContext` —
      // a template list resolving after a context switch stays attached to
      // the old visit and is dropped.
      if (contextRef.current.patientId !== startContext.patientId
        || contextRef.current.visitId !== startContext.visitId) {
        return;
      }
      const list = Array.isArray(result) ? result : ((result as Record<string, unknown>)?.items || []);
      // Only show templates that have a published version.
      setTemplates((list as LabTemplate[]).filter((tpl) => tpl.published_version_id));
    } catch (err: unknown) {
      if (contextRef.current.patientId !== startContext.patientId
        || contextRef.current.visitId !== startContext.visitId) {
        return;
      }
      const errShape = err as { message?: string };
      logger.warn('[LabResultsSection] Failed to load templates', { error: errShape?.message });
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  };

  const handleOrder = async (templateId: string | number, templateName: string) => {
    // The intent is bound to the context it was started in.
    const startContext = contextRef.current;
    // UX-AUDIT-FIX9: подтверждение перед созданием заказа.
    // STRAT#12: строки мигрированы на t() / tInterpolate() из labTranslations.
    const ok = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
      title: t('confirm.order_title'),
      message: t('confirm.order_message', { name: templateName }),
      description: t('confirm.order_description'),
      confirmLabel: t('confirm.order_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'primary',
    });
    if (!ok) return;
    // EMRORDER-FE-001: recheck before the irreversible createOrder — the
    // mounted EMR must still belong to the patient/visit the intent was
    // started in; a late confirm of visit A must not create A's order (and
    // show a success toast) inside visit B's active EMR.
    if (contextRef.current.patientId !== startContext.patientId
      || contextRef.current.visitId !== startContext.visitId) {
      logger.info('[LabResultsSection] Dropped stale order intent', {
        templateId: String(templateId),
        // No PHI in logs: template ids only, never patient/visit ids.
      });
      return;
    }
    setOrdering(true);
    try {
      await labReportingApi.createOrder({
        template_id: templateId,
        patient_id: patientId,
        visit_id: visitId,
      });
      // Second recheck: if the context switched while the POST was in
      // flight, the order exists server-side, but its success must not be
      // celebrated inside the new visit's EMR.
      if (contextRef.current.patientId !== startContext.patientId
        || contextRef.current.visitId !== startContext.visitId) {
        return;
      }
      notify.success(`Заказ «${templateName}» создан. Лаборатория увидит его в очереди.`);
      setShowOrderModal(false);
    } catch (err: unknown) {
      const msg = getErrorMessage(err) || 'Не удалось создать заказ.';
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
              <TestTube2 size={16} aria-hidden="true" style={{ color: 'var(--mac-text-secondary)' }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: '14px', color: 'var(--mac-text-primary)' }}>
                  {instance.template_name || instance.template_code || 'Лабораторный отчёт'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                  {formatDate(instance.finalized_at || instance.updated_at)}
                  {(instance.flagged_findings_count ?? 0) > 0 && (
                    <span style={{ marginLeft: '8px', color: 'var(--mac-warning)' }}>
                      ⚠ {instance.flagged_findings_count ?? 0} отклонений
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
              <Badge variant={getLabStatusVariant(instance.status || '') || 'default'} size="small">
                {formatLabStatus(instance.status || '') || instance.status}
              </Badge>
              {/* EMRLAB-FE-004 (audit 3886, round 15): read-only просмотр
                  не отзывает права читать канонический PDF (бэкенд
                  разрешает Doctor'у finalized/printed). disabled гейтит
                  только мутации (create order), а не чтение. */}
              <Button
                variant="outline"
                size="small"
                onClick={() => handleDownload(instance.id)}
                aria-label={`Скачать PDF: ${instance.template_name || 'лабораторный отчёт'}`}>
                <Download size={14} style={{ marginRight: 4 }} aria-hidden="true" />
                PDF
              </Button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      {/* EMRLAB-FE-004: секция интерактивна для ЧТЕНИЯ даже в
          signed/read-only EMR (аккордеон раскрывается, PDF доступен);
          disabled больше не глушит pointer-events всего блока. */}
      <EMRSection
        title="Результаты анализов"
        icon={<FileText size={16} aria-hidden="true" />}
        defaultOpen={instances.length > 0}
        headerAction={!disabled && patientId ? (
          <Button variant="outline" size="small" onClick={handleOpenOrderModal}>
            <Plus size={14} style={{ marginRight: 4 }} aria-hidden="true" />
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
                    onClick={() => handleOrder(template.id, template.name || '')}
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
                    <TestTube2 size={20} aria-hidden="true" style={{ color: 'var(--mac-text-secondary)' }} />
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


export default LabResultsSection;
