
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
import { getWorkspaceLabs, type WorkspaceLabs } from '@/api/emrWorkspace';
import { LabVersionReview, LabWorkspaceState } from '../workspace/LabWorkspaceState';

// UX-AUDIT-FIX10: STATUS_LABELS и STATUS_VARIANTS удалены —
// используются formatLabStatus() и getLabStatusVariant() из labUiLabels.js.

interface LabReportInstance {
  id: string | number;
  visit_id?: string | number | null;
  patient_id?: string | number;
  template?: { name: string; code: string } | null;
  template_name?: string;
  template_code?: string;
  finalized_at?: string;
  updated_at?: string;
  flagged_findings_count?: number;
  status?: string;
}

interface LabResultList {
  scope: string;
  refresh: number;
  rows: LabReportInstance[] | null;
}

type PdfDownloadPhase = 'loading' | 'error';

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
  reviewerId?: string | number | null;
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

export function LabResultsSection({ patientId, visitId, disabled = false, reviewerId }: LabResultsSectionProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  // ADR-0015: lab reporting API accessed via hook.
  const labReportingApi = useLabReporting();
  const { listInstances } = labReportingApi;
  const [resultList, setResultList] = useState<LabResultList>();
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [templates, setTemplates] = useState<LabTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [ordering, setOrdering] = useState(false);
  const orderIntentRef = useRef<number | null>(null);
  const [pdfDownloads, setPdfDownloads] = useState<{ scope: string; phases: Record<string, PdfDownloadPhase | undefined> }>();
  const pdfInFlight = useRef(new Set<string>());
  const labScope = `${visitId ?? ''}:${patientId ?? ''}`;
  const [labState, setLabState] = useState<{ scope: string; refresh: number; data?: WorkspaceLabs; error: boolean }>();
  const [labReload, setLabReload] = useState(0);
  const refreshLabs = useCallback(() => setLabReload(value => value + 1), []);
  const activeLabState = labState?.scope === labScope ? labState : undefined;
  const labs = activeLabState?.data;
  const activeResultList = resultList?.scope === labScope ? resultList : undefined;
  const instances = activeResultList?.rows ?? [];
  const loading = Boolean(patientId || visitId) && activeResultList?.refresh !== labReload;
  const resultsFailed = !loading && activeResultList?.rows === null;
  const metadataFailed = activeLabState?.refresh === labReload && activeLabState.error;
  const canReview = !loading && !resultsFailed && activeLabState?.refresh === labReload && !activeLabState.error;

  // UX-AUDIT-FIX9: useConfirm для подтверждения создания заказа на анализы.
  // Ранее один клик в модалке «Заказать анализы» мгновенно создавал заказ
  // через labReportingApi.createOrder — без подтверждения и без возможности
  // отмены. Лаборатория сразу видела новый заказ в очереди. Если врач
  // промахивался мимо нужного шаблона — приходилось идти в лабораторию
  // и просить отменить. Соответствует Nielsen Heuristic #5 (Error Prevention).
  const [confirm, orderConfirmation] = useConfirm();

  // EMRORDER-FE-001 (audit 3886, round 19): the mounted section can be
  // re-rendered in place for ANOTHER patient/visit while a confirmation
  // dialog or template fetch is pending. The latest mounted context is
  // tracked in a ref; every async completion (confirm resolution, template
  // list, createOrder ACK) re-checks it against the context the intent was
  // STARTED in and drops stale intents instead of dispatching them under
  // the new visit's header.
  const contextRef = useRef({ patientId, visitId });
  contextRef.current = { patientId, visitId };
  const contextEpoch = useRef(0);
  useEffect(() => () => { contextEpoch.current += 1; }, [labScope]);

  const loadInstances = useCallback(async (signal: AbortSignal) => {
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
          const result = await listInstances(params);
          if (signal.aborted) return;
          const list = Array.isArray(result)
            ? result
            : ((result as Record<string, unknown>)?.items || []);
          collected.push(...(list as LabReportInstance[]));
          if ((list as unknown[]).length < PAGE) break;
          offset += PAGE;
        }
      }
      // Второй пояс (render-time sanity): в списке — только финализированные
      // записи текущего контекста; дубли по id подавляются, порядок —
      // новее-первый по дате финализации.
      const seenIds = new Set<string>();
      const merged = collected
        .filter((r) => r.status === 'FINALIZED' || r.status === 'PRINTED')
        .filter((r) => (r.visit_id === undefined || visitId == null || String(r.visit_id) === String(visitId))
          && (r.patient_id === undefined || patientId == null || String(r.patient_id) === String(patientId)))
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
      setResultList({ scope: labScope, refresh: labReload, rows: merged });
    } catch (err: unknown) {
      if (signal.aborted) return;
      const errShape = err as { message?: string };
      logger.warn('[LabResultsSection] Failed to load lab instances', { error: errShape?.message });
      setResultList({ scope: labScope, refresh: labReload, rows: null });
    }
  }, [labReload, labScope, listInstances, patientId, visitId]);

  useEffect(() => {
    if (!patientId && !visitId) return;
    const controller = new AbortController();
    const { signal } = controller;
    void loadInstances(signal);
    if (visitId) {
      void getWorkspaceLabs(visitId, patientId ?? null, signal).then(
        data => {
          if (!signal.aborted) setLabState({ scope: labScope, refresh: labReload, data, error: false });
        },
        () => {
          if (!signal.aborted) setLabState(previous => ({
            scope: labScope, refresh: labReload,
            data: previous?.scope === labScope ? previous.data : undefined, error: true,
          }));
        },
      );
    }
    return () => controller.abort();
  }, [visitId, patientId, labScope, labReload, loadInstances]);

  const handleDownload = async (instanceId: string | number) => {
    const epoch = contextEpoch.current;
    const reportId = String(instanceId);
    const requestKey = `${epoch}:${reportId}`;
    if (pdfInFlight.current.has(requestKey)) return;
    pdfInFlight.current.add(requestKey);
    const contextChanged = () => contextEpoch.current !== epoch
      || contextRef.current.visitId !== visitId || contextRef.current.patientId !== patientId;
    const setPhase = (phase?: PdfDownloadPhase) => setPdfDownloads(previous => ({
      scope: labScope,
      phases: { ...(previous?.scope === labScope ? previous.phases : {}), [reportId]: phase },
    }));
    setPhase('loading');
    try {
      const blob = await labReportingApi.downloadPdf(instanceId);
      if (contextChanged()) return;
      const url = URL.createObjectURL(blob);
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      const link = window.document.createElement('a');
      link.href = url;
      link.download = `lab-${reportId}.pdf`;
      link.click();
      setPhase();
    } catch (err: unknown) {
      if (contextChanged()) return;
      setPhase('error');
      const errShape = err as { message?: string };
      logger.error('[LabResultsSection] PDF download failed', { error: errShape?.message });
    } finally {
      pdfInFlight.current.delete(requestKey);
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
    setOrdering(false);
    setPdfDownloads(undefined);
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
    const startContext = contextRef.current;
    const epoch = contextEpoch.current;
    if (orderIntentRef.current === epoch || disabled || !patientId || !visitId) return;
    orderIntentRef.current = epoch;
    setOrdering(true);
    const contextChanged = () =>
      contextRef.current.patientId !== startContext.patientId
      || contextRef.current.visitId !== startContext.visitId
      || contextEpoch.current !== epoch;

    try {
      const ok = await confirm({
        title: t('confirm.order_title'),
        message: t('confirm.order_message', { name: templateName }),
        description: t('confirm.order_description'),
        confirmLabel: t('confirm.order_confirm'),
        cancelLabel: t('confirm.cancel'),
        intent: 'primary',
      });
      if (!ok || contextChanged()) return;
      await labReportingApi.createOrder({
        template_id: templateId,
        patient_id: patientId,
        visit_id: visitId,
      });
      if (contextChanged()) return;
      notify.success(t('emr_workspace.lab_order_created'));
      setShowOrderModal(false);
      refreshLabs();
    } catch (err: unknown) {
      if (!contextChanged()) {
        const message = getErrorMessage(err) || t('emr_workspace.save_error');
        notify.error(typeof message === 'string' ? message : t('emr_workspace.save_error'));
      }
    } finally {
      if (orderIntentRef.current === epoch) orderIntentRef.current = null;
      if (!contextChanged()) setOrdering(false);
    }
  };

  const renderContent = () => {
    if (resultsFailed) return null;

    if (instances.length === 0) {
      return (
        <div style={{ padding: '12px', color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
          {loading ? t('empty.loading_results') : t('empty.no_lab_results')}
        </div>
      );
    }

    const reportOrder = new Map(labs?.orders.flatMap(order => order.reports.map(report => [report.id, order] as const)) ?? []);
    const reportDetails = new Map([
      ...(labs?.orders.flatMap(order => order.reports) ?? []), ...(labs?.unlinked_reports ?? []),
    ].map(report => [report.id, report]));
    const groups = new Map<number | undefined, LabReportInstance[]>();
    for (const instance of instances) {
      const orderId = reportOrder.get(Number(instance.id))?.id;
      const group = groups.get(orderId);
      if (group) group.push(instance);
      else groups.set(orderId, [instance]);
    }
    return (
      <div className="emr-workspace-result-list">
        {[...groups].map(([orderId, group]) => <section key={orderId ?? 'unlinked'}>
          {orderId != null && <h4>{t('emr_workspace.lab_order', { id: orderId })} · {t(
            `emr_workspace.lab_${reportOrder.get(Number(group[0]?.id))?.status}`,
            { defaultValue: reportOrder.get(Number(group[0]?.id))?.status },
          )}</h4>}
          {group.map((instance) => {
            const details = reportDetails.get(Number(instance.id));
            const pdfPhase = pdfDownloads?.scope === labScope ? pdfDownloads.phases[String(instance.id)] : undefined;
            const reportTitle = instance.template?.name || instance.template?.code || details?.template_name
              || instance.template_name || instance.template_code || t('emr_workspace.lab_report', { id: instance.id });
            return <div key={instance.id} className="emr-workspace-group">
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '10px 12px',
              border: '1px solid var(--mac-border)',
              borderRadius: '8px',
              background: 'var(--emr-v2-surface-secondary, var(--mac-bg-secondary))',
            }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
              <TestTube2 size={16} aria-hidden="true" style={{ color: 'var(--mac-text-secondary)' }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: '14px', color: 'var(--mac-text-primary)' }}>
                  {reportTitle}
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
                type="button"
                variant="outline"
                size="small"
                disabled={pdfPhase === 'loading'}
                aria-busy={pdfPhase === 'loading'}
                onClick={() => handleDownload(instance.id)}
                aria-label={t('emr_workspace.lab_download_pdf_aria', { name: reportTitle })}>
                <Download size={14} style={{ marginRight: 4 }} aria-hidden="true" />
                PDF
              </Button>
            </div>
          </div>
          {pdfPhase === 'error' && <p role="alert">{t('emr_workspace.lab_download_pdf_failed')}</p>}
          {details && visitId && patientId && <LabVersionReview key={`${labScope}:${details.id}`} report={details}
            visitId={visitId} patientId={patientId} reviewerId={canReview ? reviewerId : undefined} retry={refreshLabs} />}
          </div>;
          })}
        </section>)}
      </div>
    );
  };

  return (
    <>
      {visitId && <LabWorkspaceState labs={labs} error={Boolean(metadataFailed)} />}
      {resultsFailed && !metadataFailed && <p role="alert">{t('emr_workspace.load_error')}</p>}
      {/* EMRLAB-FE-004: секция интерактивна для ЧТЕНИЯ даже в
          signed/read-only EMR (аккордеон раскрывается, PDF доступен);
          disabled больше не глушит pointer-events всего блока. */}
      <EMRSection
        title="Результаты анализов"
        icon={<FileText size={16} aria-hidden="true" />}
        badge={instances.length ? String(instances.length) : undefined}
        defaultOpen={instances.length > 0}
        headerAction={patientId || visitId ? <div className="emr-workspace-controls">
          <Button type="button" variant="ghost" size="small" onClick={refreshLabs} disabled={loading}>
            {t(resultsFailed || metadataFailed ? 'emr_workspace.retry' : 'emr_workspace.lab_refresh')}
          </Button>
          {!disabled && patientId && <Button variant="outline" size="small" onClick={handleOpenOrderModal}>
            <Plus size={14} style={{ marginRight: 4 }} aria-hidden="true" />
            Заказать анализы
          </Button>}
        </div> : null}
      >
        {renderContent()}
      </EMRSection>

      {/* P1 fix: Order lab tests modal */}
      {showOrderModal && (
        <Dialog open={showOrderModal} onClose={() => setShowOrderModal(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Заказать анализы</DialogTitle>
          <DialogContent className="emr-workspace-dialog-body">
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
                      background: 'var(--emr-v2-surface-primary, var(--mac-bg-primary))',
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
      {orderConfirmation}
    </>
  );
}


export default LabResultsSection;
