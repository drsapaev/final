
import { useTranslation } from '../../i18n/useTranslation';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Building2,
  CalendarDays,
  MapPin,
  RefreshCw,
  Search,
  Users,
  X,
} from 'lucide-react';
import { toast } from 'react-toastify';

import { api, apiRequest } from '../../api/client';
import logger from '../../utils/logger';
import {
  Badge,
  Button,
  Card,
  AppEmpty,
  AppError,
  Input,
  Modal,
  Select,
  StatCard,
} from '../ui/macos';
import { DataTable } from '../ui/DataTable';

const INITIAL_FILTERS = {
  day: '',
  specialistId: '',
  cabinetNumber: '',
};

interface QueueRow {
  id: number;
  day?: string;
  owner_type: 'doctor' | 'resource';
  owner_id: number;
  owner_name: string;
  owner_default_cabinet: string | null;
  queue_tag?: string;
  cabinet_number?: string | number;
  cabinet_floor?: string | number;
  cabinet_building?: string | number;
  entries_count?: number;
  active?: boolean;
  sync_status?: string;
  linked_doctor_found?: boolean;
  doctor_has_cabinet?: boolean;
  integrity_warnings?: string[];
}

type ReassignmentReasonCode =
  | 'room_unavailable'
  | 'equipment_issue'
  | 'schedule_change'
  | 'administrative_correction';

type ReassignmentBlockingReason =
  | 'patient_called'
  | 'clinical_work_in_progress'
  | 'active_service_execution';

const BLOCKING_REASON_TRANSLATION_KEYS: Record<ReassignmentBlockingReason, string> = {
  patient_called: 'admin2.qcm_block_patient_called',
  clinical_work_in_progress: 'admin2.qcm_block_clinical_work',
  active_service_execution: 'admin2.qcm_block_active_execution',
};

interface ReassignmentPreviewItem {
  queue_id: number;
  owner_type: 'doctor' | 'resource';
  owner_id: number;
  owner_name: string;
  old_cabinet_number: string | null;
  new_cabinet_number: string | null;
  waiting_count: number;
  blocking_reasons: ReassignmentBlockingReason[];
  can_apply: boolean;
}

interface ReassignmentPreview {
  clinic_day: string;
  items: ReassignmentPreviewItem[];
  can_apply: boolean;
}

const createIdempotencyKey = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `cabinet-${Date.now()}-${Math.random().toString(36).slice(2, 14)}`;
};

const readSafeErrorDetail = (error: unknown): string | null => {
  if (typeof error === 'string') return error;
  if (!error || typeof error !== 'object') return null;
  const detail = (error as { detail?: unknown }).detail;
  return typeof detail === 'string' ? detail : null;
};

const readSafeErrorCode = (error: unknown): string | null => {
  if (!error || typeof error !== 'object') return null;
  const code = (error as { code?: unknown }).code;
  return typeof code === 'string' ? code : null;
};

// Summary values are derived from the same queue rows shown in the table.
interface StatsSummary {
  totalQueues: number;
  queuesWithCabinet: number;
  uniqueCabinets: number;
  totalEntries: number;
}

const formatDate = (
  value: unknown,
  _t: (key: string, options?: Record<string, unknown>) => string,
): string => {
  if (!value) return '—';
  const date = new Date(value as string | number | Date);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
};

const toOptionalNumber = (value: unknown): number | null => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
};

const toOptionalString = (value: unknown): string | null => {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized.length ? normalized : null;
};

const buildStatsSummary = (queues: QueueRow[]): StatsSummary => {
  const safeQueues = Array.isArray(queues) ? queues : [];
  const cabinets = new Set<string | number>();
  let totalEntries = 0;

  safeQueues.forEach((queue) => {
    if (queue?.cabinet_number) cabinets.add(queue.cabinet_number);
    totalEntries += Number(queue?.entries_count || 0);
  });

  return {
    totalQueues: safeQueues.length,
    queuesWithCabinet: safeQueues.filter((queue) => queue?.cabinet_number).length,
    uniqueCabinets: cabinets.size,
    totalEntries,
  };
};

const QueueCabinetManagement = () => {
  const { t } = useTranslation();
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(INITIAL_FILTERS);
  const [queues, setQueues] = useState<QueueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [reassignmentQueue, setReassignmentQueue] = useState<QueueRow | null>(null);
  const [newCabinetNumber, setNewCabinetNumber] = useState('');
  const [reasonCode, setReasonCode] = useState<ReassignmentReasonCode>('administrative_correction');
  const [reassignmentPreview, setReassignmentPreview] = useState<ReassignmentPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyOutcomeUnknown, setApplyOutcomeUnknown] = useState(false);
  const [reassignmentError, setReassignmentError] = useState<string | null>(null);
  const applyKeyRef = useRef<string | null>(null);
  const previewGenerationRef = useRef(0);
  const loadRequestSequence = useRef(0);

  const loadData = useCallback(async (filterSnapshot = INITIAL_FILTERS) => {
    const requestSequence = ++loadRequestSequence.current;
    setLoading(true);
    setLoadError(false);
    try {
      const queueParams = {
        day: filterSnapshot.day || undefined,
        specialist_id: toOptionalNumber(filterSnapshot.specialistId) ?? undefined,
        cabinet_number: toOptionalString(filterSnapshot.cabinetNumber) ?? undefined,
      };
      const result = await apiRequest('GET', '/admin/queues/cabinet-info', {
        params: queueParams,
      });
      if (requestSequence !== loadRequestSequence.current) return;
      setQueues(Array.isArray(result) ? (result as QueueRow[]) : []);
    } catch {
      if (requestSequence !== loadRequestSequence.current) return;
      logger.warn('API /api/v1/admin/queues/cabinet-info недоступен');
      setQueues([]);
      setLoadError(true);
    } finally {
      if (requestSequence === loadRequestSequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData(INITIAL_FILTERS);
  }, [loadData]);

  const summary = useMemo(
    () => buildStatsSummary(queues),
    [queues],
  );

  const applyFilters = async () => {
    const nextFilters = {
      day: filters.day,
      specialistId: filters.specialistId,
      cabinetNumber: filters.cabinetNumber,
    };
    setAppliedFilters(nextFilters);
    await loadData(nextFilters);
  };

  const resetFilters = async () => {
    setFilters(INITIAL_FILTERS);
    setAppliedFilters(INITIAL_FILTERS);
    await loadData(INITIAL_FILTERS);
  };

  const openReassignment = (queue: QueueRow) => {
    previewGenerationRef.current += 1;
    setReassignmentQueue(queue);
    setNewCabinetNumber(String(queue.cabinet_number ?? ''));
    setReasonCode('administrative_correction');
    setReassignmentPreview(null);
    setReassignmentError(null);
    setPreviewing(false);
    setApplyOutcomeUnknown(false);
    applyKeyRef.current = null;
  };

  const closeReassignment = useCallback(() => {
    if (applying || applyOutcomeUnknown) return;
    previewGenerationRef.current += 1;
    setReassignmentQueue(null);
    setReassignmentPreview(null);
    setReassignmentError(null);
    applyKeyRef.current = null;
  }, [applying, applyOutcomeUnknown]);

  const updateReassignmentDraft = (nextCabinet: string, nextReason: ReassignmentReasonCode) => {
    previewGenerationRef.current += 1;
    setNewCabinetNumber(nextCabinet);
    setReasonCode(nextReason);
    setReassignmentPreview(null);
    setReassignmentError(null);
    setPreviewing(false);
    setApplyOutcomeUnknown(false);
    applyKeyRef.current = null;
  };

  const previewReassignment = async () => {
    if (!reassignmentQueue) return;
    const requestGeneration = ++previewGenerationRef.current;
    const queueId = reassignmentQueue.id;
    const normalizedCabinet = newCabinetNumber.trim();
    const targetCabinet = normalizedCabinet || null;
    setPreviewing(true);
    setReassignmentError(null);
    try {
      const result = await apiRequest<ReassignmentPreview>(
        'POST',
        '/admin/queues/cabinet-info/preview',
        {
          data: {
            queue_ids: [queueId],
            new_cabinet_number: targetCabinet,
          },
        },
      );
      if (requestGeneration === previewGenerationRef.current) {
        setReassignmentPreview(result);
        applyKeyRef.current = createIdempotencyKey();
      }
    } catch (error: unknown) {
      if (requestGeneration === previewGenerationRef.current) {
        const detail = readSafeErrorDetail(error);
        setReassignmentError(detail || t('admin2.qcm_preview_error'));
      }
    } finally {
      if (requestGeneration === previewGenerationRef.current) setPreviewing(false);
    }
  };

  const applyReassignment = async () => {
    if (!reassignmentQueue || !reassignmentPreview?.can_apply) return;
    const retryingUncertainOutcome = applyOutcomeUnknown;
    const previewItem = reassignmentPreview.items.find(
      (item) => item.queue_id === reassignmentQueue.id,
    );
    const idempotencyKey = applyKeyRef.current;
    if (!previewItem || !idempotencyKey) {
      setReassignmentError(t('admin2.qcm_preview_again'));
      return;
    }
    const requestBody = {
      targets: [
        {
          queue_id: previewItem.queue_id,
          expected_owner_type: previewItem.owner_type,
          expected_owner_id: previewItem.owner_id,
          expected_cabinet_number: previewItem.old_cabinet_number,
        },
      ],
      new_cabinet_number: previewItem.new_cabinet_number,
      reason_code: reasonCode,
    };

    setApplying(true);
    setApplyOutcomeUnknown(false);
    setReassignmentError(null);
    try {
      await api.request({
        method: 'POST',
        url: '/admin/queues/cabinet-info/apply',
        data: requestBody,
        headers: { 'Idempotency-Key': idempotencyKey },
      });
      applyKeyRef.current = null;
      setReassignmentQueue(null);
      setReassignmentPreview(null);
      toast.success(t('admin2.qcm_apply_success'));
      await loadData(appliedFilters);
    } catch (error: unknown) {
      const response = (error as { response?: { status?: number; data?: unknown } })?.response;
      const detail = readSafeErrorDetail(response?.data) || readSafeErrorDetail(error);
      const errorCode = readSafeErrorCode(response?.data);
      const statusCode = response?.status;
      if (errorCode === 'idempotency_in_flight') {
        // Keep the request body and key unchanged so a retry joins or replays it.
        setApplyOutcomeUnknown(true);
        setReassignmentError(t('admin2.qcm_apply_in_flight'));
      } else if (retryingUncertainOutcome && statusCode === 429) {
        // A cooldown/rate-limit refusal on the retry does not resolve the first
        // attempt: the retry may have been refused before it reached the server.
        setApplyOutcomeUnknown(true);
        setReassignmentError(detail || t('admin2.qcm_apply_error'));
      } else if (statusCode && statusCode >= 400 && statusCode < 500) {
        applyKeyRef.current = null;
        setReassignmentPreview(null);
        setApplyOutcomeUnknown(false);
        setReassignmentError(detail || t('admin2.qcm_apply_error'));
      } else {
        // Keep the same payload and key available for a safe retry when the
        // server may have committed but the response did not reach the browser.
        setApplyOutcomeUnknown(true);
        setReassignmentError(detail || t('admin2.qcm_apply_error'));
      }
    } finally {
      setApplying(false);
    }
  };

  const tableRows = useMemo(
    () =>
      queues.map((queue) => {
        const resourceOwned = queue.owner_type === 'resource';
        return {
          day: (
            <span className="admin-primary-fs-sm">
              {formatDate(queue.day, t)}
            </span>
          ),
          specialist_name: (
            <div className="admin-d-flex-ai-center-gap-10">
              <div
                className="admin-w-32-h-32-radius-var-mac-radius-full-bgc-bg-secondary-d-flex-ai-center-jc-center">
                <Users className="admin-w-16-h-16-blue" />
              </div>
              <div>
                <div className="admin-fw-600-primary">
                  {queue.owner_name}
                </div>
                <div className="admin-fs-xs-tertiary-3">
                  {t(
                    resourceOwned
                      ? 'admin2.qcm_owner_type_resource'
                      : 'admin2.qcm_owner_type_doctor',
                  )}{' '}
                  #{queue.owner_id}
                  {resourceOwned ? (
                    <span>
                      {' · '}
                      {t('admin2.qcm_resource_tag_line', {
                        tag: queue.queue_tag || '—',
                      })}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          ),
          queue_tag: (
            <span className="text-[var(--mac-text-primary)]">
              {queue.queue_tag || '—'}
            </span>
          ),
          cabinet_number: (
            <div>
              <div className="admin-primary-fw-600-1">
                {queue.cabinet_number || t('admin2.qcm_not_specified')}
              </div>
              <div className="admin-fs-xs-tertiary-2">
                {t('admin2.qcm_owner_default_cabinet')}: {queue.owner_default_cabinet || '—'}
              </div>
            </div>
          ),
          cabinet_floor: (
            <span className="text-[var(--mac-text-primary)]">
              {queue.cabinet_floor ?? '—'}
            </span>
          ),
          cabinet_building: (
            <span className="text-[var(--mac-text-primary)]">
              {queue.cabinet_building || '—'}
            </span>
          ),
          entries_count: (
            <span className="admin-primary-fw-600">
              {queue.entries_count}
            </span>
          ),
          active: (
            <Badge
              variant={queue.active ? 'success' : 'secondary'}
              className="admin-fs-xs-p-4px-10px">
              {queue.active ? t('admin2.qcm_status_active') : t('admin2.qcm_status_inactive')}
            </Badge>
          ),
          sync_state: (
            <div className="admin-d-flex-fd-column-gap-6">
              {resourceOwned ? (
                <>
                  <Badge variant="success">
                    {t('admin2.qcm_sync_state_resource')}
                  </Badge>
                  <div className="admin-d-flex-fw-wrap-gap-6">
                    <Badge variant="secondary" className="admin-fs-xs">
                      {t('admin2.qcm_resource_owner')}
                    </Badge>
                  </div>
                  <div className="admin-fs-xs-tertiary-1">
                    {t('admin2.qcm_snapshot_hint')}
                  </div>
                </>
              ) : (
                <>
                  <Badge
                    variant={
                      queue.sync_status === 'synced'
                        ? 'success'
                        : queue.sync_status === 'default_differs'
                          ? 'secondary'
                          : 'warning'
                    }
                  >
                    {queue.sync_status === 'synced'
                      ? t('admin2.qcm_sync_state_synced')
                      : queue.sync_status === 'default_differs'
                        ? t('admin2.qcm_sync_state_default_differs')
                        : queue.sync_status === 'missing_doctor'
                          ? t('admin2.qcm_sync_state_missing_doctor')
                          : t('admin2.qcm_sync_state_missing_cabinet')}
                  </Badge>
                  <div className="admin-d-flex-fw-wrap-gap-6">
                    <Badge
                      variant={queue.linked_doctor_found ? 'success' : 'warning'}
                      className="admin-fs-xs"
                    >
                      {queue.linked_doctor_found ? t('admin2.qcm_doctor_found') : t('admin2.qcm_doctor_not_found')}
                    </Badge>
                    <Badge
                      variant={queue.doctor_has_cabinet ? 'success' : 'warning'}
                      className="admin-fs-xs"
                    >
                      {queue.doctor_has_cabinet ? t('admin2.qcm_doctor_cabinet_set') : t('admin2.qcm_doctor_cabinet_empty')}
                    </Badge>
                  </div>
                  <div className="admin-fs-xs-tertiary-1">
                    {t('admin2.qcm_snapshot_hint')}
                  </div>
                </>
              )}
              {Array.isArray(queue.integrity_warnings) && queue.integrity_warnings.length > 0 ? (
                <div className="admin-fs-xs-tertiary">
                  {queue.integrity_warnings.join(', ')}
                </div>
              ) : null}
            </div>
          ),
          actions: (
            <Button
              size="small"
              variant="outline"
              onClick={() => openReassignment(queue)}
              disabled={!Number.isInteger(queue.id) || queue.id <= 0}
            >
              {t('admin2.qcm_reassign')}
            </Button>
          ),
        };
      }),
    [queues, t],
  );

  return (
    <div className="admin-p-0-bgc-bg-primary">
      <Card className="p-0">
        <div className="p-6">
          <div
            className="admin-d-flex-ai-start-jc-between-gap-16-mb-24-pb-24-bd-b-1px-solid-var-mac-bo">
            <div>
              <h2
                className="admin-fs-2xl-fw-semi-primary-m-0-0-8px-0-d-flex-ai-center-gap-12">
                <Building2 className="admin-w-32-h-32-blue" />
                {t('admin2.qcm_title')}
              </h2>
              <p
                className="admin-secondary-fs-sm-m-0-lh-1p5">
                {t('admin2.qcm_subtitle')}
              </p>
            </div>

            <div className="admin-d-flex-gap-12-fw-wrap">
              <Button
                onClick={() => loadData(appliedFilters)}
                variant="outline"
                className="admin-d-inline-flex-ai-center-gap-8">
                <RefreshCw className="w-4 h-4" />
                {t('admin2.qcm_refresh')}
              </Button>
            </div>
          </div>

          {!loadError ? (
            <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-24">
              <StatCard
                title={t('admin2.qcm_stat_queues')}
                value={summary.totalQueues}
                icon={CalendarDays}
                color="blue"
                loading={loading}
              />
              <StatCard
                title={t('admin2.qcm_stat_with_cabinet')}
                value={summary.queuesWithCabinet}
                icon={MapPin}
                color="green"
                loading={loading}
              />
              <StatCard
                title={t('admin2.qcm_stat_cabinets')}
                value={summary.uniqueCabinets}
                icon={Building2}
                color="purple"
                loading={loading}
              />
              <StatCard
                title={t('admin2.qcm_stat_entries')}
                value={summary.totalEntries}
                icon={Users}
                color="orange"
                loading={loading}
              />
            </div>
          ) : null}

          <Card
            className="admin-p-20-mb-24-bgc-bg-secondary">
            <div
              className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-12-ai-end">
              <div>
                <label
                  htmlFor="queue-cabinet-day"
                  className="admin-d-block-mb-8-secondary-fs-sm-fw-600-2">
                  {t('admin2.qcm_filter_date')}
                </label>
                <Input
                  id="queue-cabinet-day"
                  type="date"
                  value={filters.day}
                  onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                    setFilters((current) => ({ ...current, day: event.target.value }))
                  }
                />
                <p className="admin-fs-xs-tertiary-1">
                  {t('admin2.qcm_clinic_day_hint')}
                </p>
              </div>

              <div>
                <label
                  htmlFor="queue-cabinet-specialist"
                  className="admin-d-block-mb-8-secondary-fs-sm-fw-600-1">
                  Specialist ID
                </label>
                <Input
                  id="queue-cabinet-specialist"
                  type="number"
                  placeholder={t('admin2.qcm_filter_specialist_placeholder')}
                  value={filters.specialistId}
                  onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                    setFilters((current) => ({ ...current, specialistId: event.target.value }))
                  }
                />
              </div>

              <div>
                <label
                  htmlFor="queue-cabinet-number"
                  className="admin-d-block-mb-8-secondary-fs-sm-fw-600">
                  {t('admin2.qcm_filter_cabinet_number')}
                </label>
                <Input
                  id="queue-cabinet-number"
                  placeholder="101"
                  value={filters.cabinetNumber}
                  onChange={(event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                    setFilters((current) => ({ ...current, cabinetNumber: event.target.value }))
                  }
                />
              </div>

              <div className="admin-d-flex-gap-8-fw-wrap">
                <Button
                  onClick={applyFilters}
                  className="admin-d-inline-flex-ai-center-gap-8-bgc-blue-bd-none">
                  <Search className="w-4 h-4" />
                  {t('admin2.qcm_apply')}
                </Button>
                <Button
                  onClick={resetFilters}
                  variant="outline"
                  className="admin-d-inline-flex-ai-center-gap-8">
                  <X className="w-4 h-4" />
                  {t('admin2.qcm_reset')}
                </Button>
              </div>
            </div>
          </Card>

          {!loading && loadError ? (
            <AppError
              title={t('admin2.qcm_load_error')}
              description={t('admin2.qcm_load_error_description')}
              action={
                <Button
                  onClick={() => loadData(appliedFilters)}
                  className="admin-d-inline-flex-ai-center-gap-8">
                  <RefreshCw className="w-4 h-4" />
                  {t('admin2.qcm_retry_load')}
                </Button>
              }
            />
          ) : !loading && queues.length === 0 ? (
            <AppEmpty
              icon={Building2}
              title={t('admin2.qcm_empty_title')}
              description={t('admin2.qcm_empty_description')}
              action={
                <Button
                  onClick={() => loadData(appliedFilters)}
                  className="admin-d-inline-flex-ai-center-gap-8">
                  <RefreshCw className="w-4 h-4" />
                  {t('admin2.qcm_retry_load')}
                </Button>
              }
            />
          ) : (
            <DataTable
              columns={[
                { key: 'day', title: t('admin2.col_day'), sortable: false },
                { key: 'specialist_name', title: t('admin2.qcm_owner'), sortable: false },
                { key: 'queue_tag', title: t('admin2.col_tag'), sortable: false },
                { key: 'cabinet_number', title: t('admin2.col_cabinet'), sortable: false },
                { key: 'cabinet_floor', title: t('admin2.col_floor'), sortable: false },
                { key: 'cabinet_building', title: t('admin2.col_building'), sortable: false },
                { key: 'entries_count', title: t('admin2.col_entries'), sortable: false },
                { key: 'active', title: t('admin2.col_active'), sortable: false },
                { key: 'sync_state', title: t('admin2.qcm_snapshot_state'), sortable: false },
                { key: 'actions', title: t('admin2.qcm_actions'), sortable: false },
              ]}
              data={tableRows}
              loading={loading}
              sortable={false}
              hoverable={false}
              striped
              emptyState={
                <tr>
                  <td
                    colSpan={10}
                    className="admin-p-40px-16px-ta-center-secondary">
                    {t('admin2.qcm_empty_table')}
                  </td>
                </tr>
              }
            />
          )}
        </div>
      </Card>
      <Modal
        isOpen={reassignmentQueue !== null}
        onClose={closeReassignment}
        title={t('admin2.qcm_reassign_title')}
        size="default"
        closeOnBackdrop={!applying && !applyOutcomeUnknown}
        closeOnEscape={!applying && !applyOutcomeUnknown}
        actions={(
          <>
            <Button variant="outline" onClick={closeReassignment} disabled={applying || applyOutcomeUnknown}>
              {t('admin2.qcm_cancel')}
            </Button>
            {reassignmentPreview ? (
              <Button
                variant="primary"
                onClick={() => void applyReassignment()}
                disabled={!reassignmentPreview.can_apply || applying || previewing}
                loading={applying}
              >
                {applyOutcomeUnknown ? t('admin2.qcm_retry_apply') : t('admin2.qcm_confirm_reassign')}
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={() => void previewReassignment()}
                disabled={previewing || applying}
                loading={previewing}
              >
                {t('admin2.qcm_preview_reassign')}
              </Button>
            )}
          </>
        )}
      >
        {reassignmentQueue ? (
          <div className="admin-d-grid-gap-16">
            <p>{t('admin2.qcm_reassign_scope_hint')}</p>
            <div>
              <strong>{reassignmentQueue.owner_name}</strong>
              {' · '}{reassignmentQueue.day || '—'}
              {' · '}{reassignmentQueue.cabinet_number || t('admin2.qcm_not_specified')}
            </div>
            <div>
              <label htmlFor="qcm-new-cabinet">{t('admin2.qcm_new_cabinet')}</label>
              <Input
                id="qcm-new-cabinet"
                value={newCabinetNumber}
                maxLength={20}
                onChange={(event) => updateReassignmentDraft(event.target.value, reasonCode)}
                disabled={applying || applyOutcomeUnknown}
              />
              <small>{t('admin2.qcm_clear_cabinet_hint')}</small>
            </div>
            <div>
              <Select
                id="qcm-reason-code"
                label={t('admin2.qcm_reason')}
                value={reasonCode}
                options={[
                  { value: 'room_unavailable', label: t('admin2.qcm_reason_room') },
                  { value: 'equipment_issue', label: t('admin2.qcm_reason_equipment') },
                  { value: 'schedule_change', label: t('admin2.qcm_reason_schedule') },
                  { value: 'administrative_correction', label: t('admin2.qcm_reason_admin') },
                ]}
                onValueChange={(value) => {
                  if (typeof value === 'string') {
                    updateReassignmentDraft(newCabinetNumber, value as ReassignmentReasonCode);
                  }
                }}
                disabled={applying || applyOutcomeUnknown}
              />
            </div>
            {reassignmentPreview ? (
              <div aria-live="polite">
                <strong>{t('admin2.qcm_preview_result', { day: reassignmentPreview.clinic_day })}</strong>
                {reassignmentPreview.items.map((item) => (
                  <div key={item.queue_id}>
                    {item.owner_name}: {item.old_cabinet_number || '—'} → {item.new_cabinet_number || '—'}
                    {' · '}{t('admin2.qcm_waiting_count', { count: item.waiting_count })}
                    {item.blocking_reasons.length > 0 ? (
                      <ul role="alert">
                        {item.blocking_reasons.map((reason) => (
                          <li key={reason}>{t(BLOCKING_REASON_TRANSLATION_KEYS[reason])}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
            {applyOutcomeUnknown ? <p role="alert">{t('admin2.qcm_uncertain_outcome')}</p> : null}
            {reassignmentError ? <p role="alert">{reassignmentError}</p> : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default QueueCabinetManagement;
