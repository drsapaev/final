import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Building2,
  CalendarDays,
  Edit,
  MapPin,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Users,
  X,
} from 'lucide-react';
import { toast } from 'react-toastify';

import { apiRequest } from '../../api/client';
import logger from '../../utils/logger';
import {
  MacOSBadge,
  MacOSButton,
  MacOSCard,
  MacOSEmptyState,
  MacOSInput,
  MacOSStatCard,
  MacOSTable,
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
  const [savingQueueId, setSavingQueueId] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [editingQueueId, setEditingQueueId] = useState(null);
  const [editValues, setEditValues] = useState({
    cabinet_number: '',
    cabinet_floor: '',
    cabinet_building: '',
  });

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

  const startEditing = useCallback((queue) => {
    setEditingQueueId(queue.id);
    setEditValues({
      cabinet_number: queue.cabinet_number ?? '',
      cabinet_floor: queue.cabinet_floor ?? '',
      cabinet_building: queue.cabinet_building ?? '',
    });
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingQueueId(null);
    setEditValues({
      cabinet_number: '',
      cabinet_floor: '',
      cabinet_building: '',
    });
  }, []);

  const saveQueue = useCallback(async (queueId) => {
    setSavingQueueId(queueId);
    try {
      const floorValue =
        editValues.cabinet_floor === '' || editValues.cabinet_floor === null
          ? null
          : Number(editValues.cabinet_floor);

      if (floorValue !== null && Number.isNaN(floorValue)) {
        toast.error('Этаж должен быть числом');
        return;
      }

      await apiRequest('PUT', `/admin/queues/${queueId}/cabinet-info`, {
        data: {
          cabinet_number: toOptionalString(editValues.cabinet_number),
          cabinet_floor: floorValue,
          cabinet_building: toOptionalString(editValues.cabinet_building),
        },
      });

      toast.success('Информация о кабинете обновлена');
      cancelEditing();
      await loadData(appliedFilters);
    } catch (error) {
      logger.error('Ошибка обновления кабинета очереди:', error);
      toast.error(error?.message || 'Ошибка обновления кабинета');
    } finally {
      setSavingQueueId(null);
    }
  }, [appliedFilters, cancelEditing, editValues, loadData]);

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
    cancelEditing();
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
        const isEditing = editingQueueId === queue.id;

        return {
          day: (
            <span style={{ color: 'var(--mac-text-primary)', fontSize: 'var(--mac-font-size-sm)' }}>
              {formatDate(queue.day)}
            </span>
          ),
          specialist_name: (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--mac-radius-full)',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                <Users style={{ width: '16px', height: '16px', color: 'var(--mac-accent-blue)' }} />
              </div>
              <div>
                <div style={{ fontWeight: 600, color: 'var(--mac-text-primary)' }}>
                  {queue.specialist_name || `Специалист #${queue.specialist_id}`}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
                  ID {queue.specialist_id}
                </div>
              </div>
            </div>
          ),
          queue_tag: (
            <span style={{ color: 'var(--mac-text-primary)' }}>
              {queue.queue_tag || '—'}
            </span>
          ),
          cabinet_number: isEditing ? (
            <MacOSInput
              value={editValues.cabinet_number}
              onChange={(event) =>
                setEditValues((current) => ({
                  ...current,
                  cabinet_number: event.target.value,
                }))
              }
              placeholder="101"
              style={{ minWidth: '90px' }}
            />
          ) : (
            <span style={{ color: 'var(--mac-text-primary)' }}>
              {queue.cabinet_number || 'Не указан'}
            </span>
          ),
          cabinet_floor: isEditing ? (
            <MacOSInput
              type="number"
              min="0"
              value={editValues.cabinet_floor}
              onChange={(event) =>
                setEditValues((current) => ({
                  ...current,
                  cabinet_floor: event.target.value,
                }))
              }
              placeholder="2"
              style={{ minWidth: '80px' }}
            />
          ) : (
            <span style={{ color: 'var(--mac-text-primary)' }}>
              {queue.cabinet_floor ?? '—'}
            </span>
          ),
          cabinet_building: isEditing ? (
            <MacOSInput
              value={editValues.cabinet_building}
              onChange={(event) =>
                setEditValues((current) => ({
                  ...current,
                  cabinet_building: event.target.value,
                }))
              }
              placeholder="A"
              style={{ minWidth: '90px' }}
            />
          ) : (
            <span style={{ color: 'var(--mac-text-primary)' }}>
              {queue.cabinet_building || '—'}
            </span>
          ),
          entries_count: (
            <span style={{ color: 'var(--mac-text-primary)', fontWeight: 600 }}>
              {queue.entries_count}
            </span>
          ),
          active: (
            <MacOSBadge
              variant={queue.active ? 'success' : 'secondary'}
              style={{
                fontSize: 'var(--mac-font-size-xs)',
                padding: '4px 10px',
              }}>
              {queue.active ? 'Активна' : 'Неактивна'}
            </MacOSBadge>
          ),
          actions: isEditing ? (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <MacOSButton
                onClick={() => saveQueue(queue.id)}
                disabled={savingQueueId === queue.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'var(--mac-success)',
                  border: 'none',
                }}>
                <Save style={{ width: '16px', height: '16px' }} />
                {savingQueueId === queue.id ? 'Сохранение...' : 'Сохранить'}
              </MacOSButton>
              <MacOSButton
                onClick={cancelEditing}
                disabled={savingQueueId === queue.id}
                variant="outline"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                <X style={{ width: '16px', height: '16px' }} />
                Отмена
              </MacOSButton>
            </div>
          ) : (
            <MacOSButton
              onClick={() => startEditing(queue)}
              variant="outline"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
              }}>
              <Edit style={{ width: '16px', height: '16px' }} />
              Изменить
            </MacOSButton>
          ),
        };
      }),
    [cancelEditing, editValues, editingQueueId, queues, saveQueue, savingQueueId, startEditing]
  );

  return (
    <div style={{ padding: 0, backgroundColor: 'var(--mac-bg-primary)' }}>
      <MacOSCard style={{ padding: 0 }}>
        <div style={{ padding: '24px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: '16px',
              marginBottom: '24px',
              paddingBottom: '24px',
              borderBottom: '1px solid var(--mac-border)',
            }}>
            <div>
              <h2
                style={{
                  fontSize: 'var(--mac-font-size-2xl)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                }}>
                <Building2 style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
                Кабинеты очередей
              </h2>
              <p
                style={{
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-sm)',
                  margin: 0,
                  lineHeight: 1.5,
                }}>
                SSOT-панель для просмотра и синхронизации кабинетов очередей с данными врачей.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <MacOSButton
                onClick={() => loadData(appliedFilters)}
                variant="outline"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                }}>
                <RefreshCw style={{ width: '16px', height: '16px' }} />
                Обновить
              </MacOSButton>
              <MacOSButton
                onClick={syncFromDoctors}
                disabled={syncing}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none',
                }}>
                <Sparkles style={{ width: '16px', height: '16px' }} />
                {syncing ? 'Синхронизация...' : 'Синхронизировать из врачей'}
              </MacOSButton>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '16px',
              marginBottom: '24px',
            }}>
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
            style={{
              padding: '20px',
              marginBottom: '24px',
              backgroundColor: 'var(--mac-bg-secondary)',
            }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '12px',
                alignItems: 'end',
              }}>
              <div>
                <label
                  htmlFor="queue-cabinet-day"
                  style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 600,
                  }}>
                  Дата
                </label>
                <MacOSInput
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
                  style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 600,
                  }}>
                  Specialist ID
                </label>
                <MacOSInput
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
                  style={{
                    display: 'block',
                    marginBottom: '8px',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 600,
                  }}>
                  Номер кабинета
                </label>
                <MacOSInput
                  id="queue-cabinet-number"
                  placeholder="101"
                  value={filters.cabinetNumber}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, cabinetNumber: event.target.value }))
                  }
                />
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <MacOSButton
                  onClick={applyFilters}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    backgroundColor: 'var(--mac-accent-blue)',
                    border: 'none',
                  }}>
                  <Search style={{ width: '16px', height: '16px' }} />
                  Применить
                </MacOSButton>
                <MacOSButton
                  onClick={resetFilters}
                  variant="outline"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <X style={{ width: '16px', height: '16px' }} />
                  Сбросить
                </MacOSButton>
              </div>
            </div>
          </MacOSCard>

          {!loading && queues.length === 0 ? (
            <MacOSEmptyState
              icon={Building2}
              title="Нет данных о кабинетах"
              description="Измените фильтры или нажмите синхронизацию, чтобы подтянуть кабинеты из таблицы врачей."
              action={
                <MacOSButton
                  onClick={() => loadData(appliedFilters)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <RefreshCw style={{ width: '16px', height: '16px' }} />
                  Повторить загрузку
                </MacOSButton>
              }
            />
          ) : (
            <MacOSTable
              columns={[
                { key: 'day', title: 'Дата', sortable: false },
                { key: 'specialist_name', title: 'Специалист', sortable: false },
                { key: 'queue_tag', title: 'Тег', sortable: false },
                { key: 'cabinet_number', title: 'Кабинет', sortable: false },
                { key: 'cabinet_floor', title: 'Этаж', sortable: false },
                { key: 'cabinet_building', title: 'Корпус', sortable: false },
                { key: 'entries_count', title: 'Записи', sortable: false },
                { key: 'active', title: 'Статус', sortable: false },
                { key: 'actions', title: 'Действия', sortable: false },
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
                    style={{
                      padding: '40px 16px',
                      textAlign: 'center',
                      color: 'var(--mac-text-secondary)',
                    }}>
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
