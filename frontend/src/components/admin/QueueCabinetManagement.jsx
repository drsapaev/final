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

const formatDate = (value) => {
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
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState(INITIAL_FILTERS);
  const [queues, setQueues] = useState([]);
  const [statistics, setStatistics] = useState(null);
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
        const payload = statisticsResult.value || {};
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
      toast.error('Ошибка загрузки информации о кабинетах');
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

      toast.success(result?.message || 'Кабинеты синхронизированы');
      await loadData(appliedFilters);
    } catch (error) {
      logger.error('Ошибка синхронизации кабинетов:', error);
      toast.error(error?.message || 'Ошибка синхронизации кабинетов');
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
              {formatDate(queue.day)}
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
                  {queue.specialist_name || `Специалист #${queue.specialist_id}`}
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
                {queue.effective_cabinet || 'Не указан'}
              </div>
              <div className="admin-fs-xs-tertiary-2">
                Очередь: {queue.cabinet_number || '—'} · Врач: {queue.doctor_cabinet || '—'}
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
              {queue.active ? 'Активна' : 'Неактивна'}
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
                  ? 'Синхронизировано'
                  : queue.sync_status === 'stale'
                    ? 'Очередь устарела'
                    : queue.sync_status === 'missing_doctor'
                      ? 'Нет врача'
                      : 'Нет кабинета врача'}
              </Badge>
              <div className="admin-d-flex-fw-wrap-gap-6">
                <Badge
                  variant={queue.linked_doctor_found ? 'success' : 'warning'}
                  className="admin-fs-xs"
                >
                  {queue.linked_doctor_found ? 'Врач найден' : 'Врач не найден'}
                </Badge>
                <Badge
                  variant={queue.doctor_has_cabinet ? 'success' : 'warning'}
                  className="admin-fs-xs"
                >
                  {queue.doctor_has_cabinet ? 'Кабинет врача задан' : 'Кабинет врача пуст'}
                </Badge>
              </div>
              <div className="admin-fs-xs-tertiary-1">
                Канонический кабинет берётся из карточки врача. Здесь можно только проверить и
                синхронизировать очередь.
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
                Кабинеты очередей
              </h2>
              <p
                className="admin-secondary-fs-sm-m-0-lh-1p5">
                SSOT-панель для просмотра и синхронизации кабинетов очередей с данными врачей.
              </p>
            </div>

            <div className="admin-d-flex-gap-12-fw-wrap">
              <Button
                onClick={() => loadData(appliedFilters)}
                variant="outline"
                className="admin-d-inline-flex-ai-center-gap-8">
                <RefreshCw className="w-4 h-4" />
                Обновить
              </Button>
              <Button
                onClick={syncFromDoctors}
                disabled={syncing}
                className="admin-d-inline-flex-ai-center-gap-8-bgc-blue-bd-none-1">
                <Sparkles className="w-4 h-4" />
                {syncing ? 'Синхронизация...' : 'Синхронизировать из врачей'}
              </Button>
            </div>
          </div>

          <div
            className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-24">
            <MacOSStatCard
              title="Очередей"
              value={summary.totalQueues}
              icon={CalendarDays}
              color="blue"
              loading={loading}
            />
            <MacOSStatCard
              title="С кабинетом"
              value={summary.queuesWithCabinet}
              icon={MapPin}
              color="green"
              loading={loading}
            />
            <MacOSStatCard
              title="Кабинетов"
              value={summary.uniqueCabinets}
              icon={Building2}
              color="purple"
              loading={loading}
            />
            <MacOSStatCard
              title="Записей"
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
                  Дата
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
                  placeholder="Например, 12"
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
                  Номер кабинета
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
                  Применить
                </Button>
                <Button
                  onClick={resetFilters}
                  variant="outline"
                  className="admin-d-inline-flex-ai-center-gap-8">
                  <X className="w-4 h-4" />
                  Сбросить
                </Button>
              </div>
            </div>
          </MacOSCard>

          {!loading && queues.length === 0 ? (
            <MacOSEmptyState
              icon={Building2}
              title="Нет данных о кабинетах"
              description="Измените фильтры или нажмите синхронизацию, чтобы подтянуть кабинеты из таблицы врачей."
              action={
                <Button
                  onClick={() => loadData(appliedFilters)}
                  className="admin-d-inline-flex-ai-center-gap-8">
                  <RefreshCw className="w-4 h-4" />
                  Повторить загрузку
                </Button>
              }
            />
          ) : (
            <Table
              columns={[
                { key: 'day', title: 'Дата', sortable: false },
                { key: 'specialist_name', title: 'Специалист', sortable: false },
                { key: 'queue_tag', title: 'Тег', sortable: false },
                { key: 'cabinet_number', title: 'Кабинет', sortable: false },
                { key: 'cabinet_floor', title: 'Этаж', sortable: false },
                { key: 'cabinet_building', title: 'Корпус', sortable: false },
                { key: 'entries_count', title: 'Записи', sortable: false },
                { key: 'active', title: 'Статус', sortable: false },
                { key: 'sync_state', title: 'Синхронизация', sortable: false },
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
                    Нет данных для отображения
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
