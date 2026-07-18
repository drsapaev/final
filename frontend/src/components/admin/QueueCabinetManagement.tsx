
import { useTranslation } from '../../i18n/useTranslation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Building2,
  CalendarDays,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  Users,
  X,
} from 'lucide-react';
import { toast } from 'react-toastify';

import { apiRequest } from '../../api/client';
import logger from '../../utils/logger';
import React from "react";
import {
  Badge,
  Button,
  MacOSCard,
  MacOSEmptyState,
  Input,
  MacOSStatCard,
  Table,
} from '../ui/macos';

const INITIAL_FILTERS = {
  day: '',
  specialistId: '',
  cabinetNumber: '',
};

const formatDate = (value, t) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
};

const toOptionalNumber = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
};

const toOptionalString = (value) => {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized.length ? normalized : null;
};

const buildStatsSummary = (stats, queues) => {
  const safeQueues = Array.isArray(queues) ? queues : [];
  const cabinets = new Set();
  let totalEntries = 0;
  let activeQueues = 0;

  safeQueues.forEach((queue) => {
    if (queue?.cabinet_number) cabinets.add(queue.cabinet_number);
    totalEntries += Number(queue?.entries_count || 0);
    if (queue?.active) activeQueues += 1;
  });

  return {
    totalQueues: stats?.total_queues ?? safeQueues.length,
    queuesWithCabinet: stats?.queues_with_cabinet ?? safeQueues.filter((queue) => queue?.cabinet_number).length,
    uniqueCabinets: stats?.cabinets?.length ?? cabinets.size,
    activeQueues,
    totalEntries,
  };
};

const QueueCabinetManagement = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(INITIAL_FILTERS);
  const [queues, setQueues] = useState([]);
  const [statistics, setStatistics] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const loadData = useCallback(async (filterSnapshot = INITIAL_FILTERS) => {
    setLoading(true);
    try {
      const queueParams = {
        day: filterSnapshot.day || undefined,
        specialist_id: toOptionalNumber(filterSnapshot.specialistId) ?? undefined,
        cabinet_number: toOptionalString(filterSnapshot.cabinetNumber) ?? undefined,
      };
      const statsParams = {
        date_from: filterSnapshot.day || undefined,
        date_to: filterSnapshot.day || undefined,
      };

      const [queuesResult, statisticsResult] = await Promise.allSettled([
        apiRequest('GET', '/admin/queues/cabinet-info', { params: queueParams }),
        apiRequest('GET', '/admin/queues/cabinet-statistics', { params: statsParams }),
      ]);

      if (queuesResult.status === 'fulfilled') {
        setQueues(Array.isArray(queuesResult.value) ? queuesResult.value : []);
      } else {
        logger.warn('API /api/v1/admin/queues/cabinet-info недоступен', queuesResult.reason);
        setQueues([]);
      }

      if (statisticsResult.status === 'fulfilled') {
        const payload = (statisticsResult.value || {}) as Record<string, any>;
        setStatistics(payload.statistics || payload);
      } else {
        logger.warn(
          'API /api/v1/admin/queues/cabinet-statistics недоступен',
          statisticsResult.reason
        );
        setStatistics(null);
      }
    } catch (error) {
      logger.error('Ошибка загрузки информации о кабинетах:', error);
      toast.error(t('admin2.qcm_load_error'));
      setQueues([]);
      setStatistics(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData(INITIAL_FILTERS);
  }, [loadData]);

  const summary = useMemo(
    () => buildStatsSummary(statistics, queues),
    [queues, statistics]
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

  const syncFromDoctors = async () => {
    setSyncing(true);
    try {
      const params = {
        day: appliedFilters.day || undefined,
        specialist_id: toOptionalNumber(appliedFilters.specialistId) ?? undefined,
      };
      const result = await apiRequest('POST', '/admin/queues/sync-cabinet-info', {
        params,
      });

      toast.success((result as Record<string, any>)?.message || t('admin2.qcm_sync_success'));
      await loadData(appliedFilters);
    } catch (error) {
      logger.error('Ошибка синхронизации кабинетов:', error);
      toast.error((error as Record<string, any>)?.message || t('admin2.qcm_sync_error'));
    } finally {
      setSyncing(false);
    }
  };

  const tableRows = useMemo(
    () =>
      queues.map((queue) => {
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
                  {queue.specialist_name || t('admin2.qcm_specialist_fallback', { id: queue.specialist_id })}
                </div>
                <div className="admin-fs-xs-tertiary-3">
                  ID {queue.specialist_id}
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
                {queue.effective_cabinet || t('admin2.qcm_not_specified')}
              </div>
              <div className="admin-fs-xs-tertiary-2">
                {t('admin2.qcm_queue_doctor_line', { queue: queue.cabinet_number || '—', doctor: queue.doctor_cabinet || '—' })}
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
              <Badge
                variant={
                  queue.sync_status === 'synced'
                    ? 'success'
                    : queue.sync_status === 'stale'
                      ? 'warning'
                      : 'secondary'
                }
              >
                {queue.sync_status === 'synced'
                  ? t('admin2.qcm_sync_state_synced')
                  : queue.sync_status === 'stale'
                    ? t('admin2.qcm_sync_state_stale')
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
                {t('admin2.qcm_canonical_hint')}
              </div>
              {Array.isArray(queue.integrity_warnings) && queue.integrity_warnings.length > 0 ? (
                <div className="admin-fs-xs-tertiary">
                  {queue.integrity_warnings.join(', ')}
                </div>
              ) : null}
            </div>
          ),
        };
      }),
    [queues]
  );

  return (
    <div className="admin-p-0-bgc-bg-primary">
      <MacOSCard className="p-0">
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
              <Button
                onClick={syncFromDoctors}
                disabled={syncing}
                className="admin-d-inline-flex-ai-center-gap-8-bgc-blue-bd-none-1">
                <Sparkles className="w-4 h-4" />
                {syncing ? t('admin2.qcm_syncing') : t('admin2.qcm_sync_from_doctors')}
              </Button>
            </div>
          </div>

          <div
            className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-24">
            <MacOSStatCard
              title={t('admin2.qcm_stat_queues')}
              value={summary.totalQueues}
              icon={CalendarDays}
              color="blue"
              loading={loading}
            />
            <MacOSStatCard
              title={t('admin2.qcm_stat_with_cabinet')}
              value={summary.queuesWithCabinet}
              icon={MapPin}
              color="green"
              loading={loading}
            />
            <MacOSStatCard
              title={t('admin2.qcm_stat_cabinets')}
              value={summary.uniqueCabinets}
              icon={Building2}
              color="purple"
              loading={loading}
            />
            <MacOSStatCard
              title={t('admin2.qcm_stat_entries')}
              value={summary.totalEntries}
              icon={Users}
              color="orange"
              loading={loading}
            />
          </div>

          <MacOSCard
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
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, day: event.target.value }))
                  }
                />
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
                  onChange={(event) =>
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
                  onChange={(event) =>
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
          </MacOSCard>

          {!loading && queues.length === 0 ? (
            <MacOSEmptyState
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
            <Table
              columns={[
                { key: 'day', title: t('admin2.col_day'), sortable: false },
                { key: 'specialist_name', title: t('admin2.col_specialist'), sortable: false },
                { key: 'queue_tag', title: t('admin2.col_tag'), sortable: false },
                { key: 'cabinet_number', title: t('admin2.col_cabinet'), sortable: false },
                { key: 'cabinet_floor', title: t('admin2.col_floor'), sortable: false },
                { key: 'cabinet_building', title: t('admin2.col_building'), sortable: false },
                { key: 'entries_count', title: t('admin2.col_entries'), sortable: false },
                { key: 'active', title: t('admin2.col_active'), sortable: false },
                { key: 'sync_state', title: t('admin2.col_sync'), sortable: false },
              ]}
              data={tableRows}
              loading={loading}
              sortable={false}
              hoverable={false}
              striped
              emptyState={
                <tr>
                  <td
                    colSpan={9}
                    className="admin-p-40px-16px-ta-center-secondary">
                    {t('admin2.qcm_empty_table')}
                  </td>
                </tr>
              }
            />
          )}
        </div>
      </MacOSCard>
    </div>
  );
};

export default QueueCabinetManagement;
