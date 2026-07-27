import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import {
  MacOSCard, Button, Input, Checkbox, SegmentedControl,
} from '../ui/macos';
import { Users, ArrowRight, Search, CheckCircle, XCircle, History, BarChart3 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

interface TransferUser {
  id: string | number;
  full_name?: string;
  username?: string;
  phone?: string;
  email?: string;
}

interface DataTypeItem {
  key: string;
  name: string;
  description: string;
}

interface DataCounts {
  appointments: number;
  visits: number;
  queue_entries: number;
  [k: string]: unknown;
}

interface DataSummary {
  data_counts: DataCounts;
  [k: string]: unknown;
}

interface TransferHistoryEntry {
  source_user: string;
  target_user: string;
  transfer_date: string;
  success: boolean;
  [k: string]: unknown;
}

interface TransferStatistics {
  total_transfers: number;
  successful_transfers: number;
  failed_transfers: number;
  [k: string]: unknown;
}

const toArray = (value: unknown, fallbackKeys: string[] = []): unknown[] => {
  if (Array.isArray(value)) return value;

  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    for (const key of fallbackKeys) {
      if (Array.isArray(obj[key])) {
        return obj[key] as unknown[];
      }
    }
  }

  return [];
};

const normalizeDataTypes = (payload: unknown): DataTypeItem[] =>
  (toArray(payload, ['data_types', 'dataTypes', 'items', 'results']) as Array<Record<string, unknown> | string>).map((item): DataTypeItem | null => {
    if (typeof item === 'string') {
      return { key: item, name: item, description: '' };
    }

    const key = (item?.key ?? item?.value ?? item?.id ?? item?.name) as string | undefined;
    if (!key) return null;

    return {
      key,
      name: (item?.name ?? item?.label ?? key) as string,
      description: (item?.description ?? '') as string
    };
  }).filter((item): item is DataTypeItem => item !== null);

const normalizeDataSummary = (payload: unknown): DataSummary => {
  const base = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const counts = (base.data_counts && typeof base.data_counts === 'object' ? base.data_counts : {}) as Record<string, unknown>;
  return {
    ...base,
    data_counts: {
      appointments: Number(counts.appointments ?? 0),
      visits: Number(counts.visits ?? 0),
      queue_entries: Number(counts.queue_entries ?? 0)
    }
  };
};

const normalizeStatistics = (payload: unknown): TransferStatistics => {
  const base = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  return {
    total_transfers: Number(base.total_transfers ?? 0),
    successful_transfers: Number(base.successful_transfers ?? 0),
    failed_transfers: Number(base.failed_transfers ?? 0),
    ...base
  };
};

const UserDataTransferManager = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeTab, setActiveTab] = useState<'transfer' | 'history' | 'statistics'>('transfer');
  const [sourceUser, setSourceUser] = useState<TransferUser | null>(null);
  const [targetUser, setTargetUser] = useState<TransferUser | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<TransferUser[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedDataTypes, setSelectedDataTypes] = useState<string[]>(['appointments', 'visits', 'queue_entries']);
  const [availableDataTypes, setAvailableDataTypes] = useState<DataTypeItem[]>([]);
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferHistory, setTransferHistory] = useState<TransferHistoryEntry[]>([]);
  const [statistics, setStatistics] = useState<TransferStatistics | null>(null);
  const [userDataSummary, setUserDataSummary] = useState<DataSummary | null>(null);

  // Загрузка доступных типов данных
  useEffect(() => {
    loadAvailableDataTypes();
  }, []);

  const loadAvailableDataTypes = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/data-types') as import('axios').AxiosResponse<Record<string, unknown>>;
      setAvailableDataTypes(normalizeDataTypes(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки типов данных:', error);
      toast.error(t('admin2.udtm_err_load_data_types'));
    }
  };

  const searchUsers = async (query: string) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await api.get(`/admin/user-data/users/search?query=${encodeURIComponent(query)}&limit=10`) as import('axios').AxiosResponse<Record<string, unknown>>;
      setSearchResults(toArray(response.data, ['users', 'items', 'results']) as TransferUser[]);
    } catch (error) {
      logger.error('Ошибка поиска пользователей:', error);
      toast.error(t('admin2.udtm_err_search_users'));
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const getUserDataSummary = async (userId: string | number) => {
    try {
      const response = (await api.get(`/admin/user-data/users/${userId}/data-summary`)) as import('axios').AxiosResponse<Record<string, unknown>>;
      setUserDataSummary(normalizeDataSummary(response.data));
    } catch (error) {
      logger.error('Ошибка получения сводки данных:', error);
      toast.error(t('admin2.udtm_err_user_data'));
    }
  };



  const validateTransfer = async () => {
    if (!sourceUser || !targetUser) {
      toast.error(t('admin2.udtm_err_select_users'));
      return false;
    }

    try {
      const response = (await api.post(`/admin/user-data/transfer/validate?source_user_id=${sourceUser!.id}&target_user_id=${targetUser!.id}`)) as import('axios').AxiosResponse<Record<string, unknown>>;
      const validation = (response.data as { valid?: boolean; message?: string; appointments?: unknown; visits?: unknown; queue_entries?: unknown; [k: string]: unknown }) || {};

      if (!validation.valid) {
        toast.error(String(validation.message || 'Transfer validation failed'));
        return false;
      }

      return true;
    } catch (error) {
      logger.error('Ошибка валидации:', error);
      toast.error(t('admin2.udtm_err_validation'));
      return false;
    }
  };

  const executeTransfer = async () => {
    if (!(await validateTransfer())) {
      return;
    }

    setIsTransferring(true);
    try {
      const response = await api.post('/admin/user-data/transfer', {
        source_user_id: sourceUser!.id,
        target_user_id: targetUser!.id,
        data_types: selectedDataTypes,
        confirmation_required: false
      }) as import('axios').AxiosResponse<Record<string, unknown>>;
      const transferResult = (response.data as { success?: boolean; transferred?: { appointments?: { success?: boolean; count?: number }; visits?: { success?: boolean; count?: number }; queue_entries?: { success?: boolean; count?: number }; [k: string]: unknown }; [k: string]: unknown }) || {};

      if (transferResult.success) {
        toast.success(t('admin2.udtm_success_transferred'));

        // Показываем результаты передачи
        const transferred = transferResult.transferred || {};
        let message = t('admin2.udtm_transferred_prefix');

        if (transferred.appointments?.success) {
          message += t('admin2.udtm_transferred_appointments', { count: transferred.appointments.count });
        }
        if (transferred.visits?.success) {
          message += t('admin2.udtm_transferred_visits', { count: transferred.visits.count });
        }
        if (transferred.queue_entries?.success) {
          message += t('admin2.udtm_transferred_queue', { count: transferred.queue_entries.count });
        }

        toast.info(message);

        // Сбрасываем форму
        setSourceUser(null);
        setTargetUser(null);
        setUserDataSummary(null);

        // Обновляем историю
        if (activeTab === 'history') {
          loadTransferHistory();
        }
      } else {
        toast.error(t('admin2.udtm_err_transfer'));
      }
    } catch (error) {
      logger.error('Ошибка передачи:', error);
      toast.error(t('admin2.udtm_err_transfer_execution'));
    } finally {
      setIsTransferring(false);
    }
  };

  const loadTransferHistory = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/history?limit=50') as import('axios').AxiosResponse<Record<string, unknown>>;
      setTransferHistory(toArray(response.data, ['history', 'items', 'results']) as TransferHistoryEntry[]);
    } catch (error) {
      logger.error('Ошибка загрузки истории:', error);
      toast.error(t('admin2.udtm_err_load_history'));
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/statistics?period_days=30') as import('axios').AxiosResponse<Record<string, unknown>>;
      setStatistics(normalizeStatistics(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      toast.error(t('admin2.udtm_err_load_statistics'));
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    searchUsers(query);
  };

  const selectUser = (user: TransferUser, type: 'source' | 'target') => {
    if (type === 'source') {
      setSourceUser(user);
      getUserDataSummary(user.id);
    } else {
      setTargetUser(user);
    }
    setSearchQuery('');
    setSearchResults([]);
  };









  const renderTransferTab = () =>
  <div className="admin-flex-col-24">
      {/* Поиск пользователей */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-lg-med-primary-m-0016px0-flex-ai-center-gap-8">
          <Search className="admin-icon-20" />
          {t('admin2.udtm_search_users_title')}
        </h3>
        
        <div className="admin-pos-relative">
          <Input
          type="text"
          placeholder={t('admin2.udtm_search_placeholder')}
          value={searchQuery}
          onChange={handleSearchChange}
          className="admin-w-full" />
        
          
          {isSearching &&
        <div className="admin-pos-absolute-right-12-top-12">
              <div className="admin-w-16-h-16-bd-2solidvar-mac-accent-blue-bordertop-0dfa98-radius-50pct-anim--9890e947"></div>
            </div>
        }
          
          {searchResults.length > 0 &&
        <div className="admin-pos-absolute-z-10-w-100pct-mt-4-bg-bg-primary-bd-1solidvar-mac-border-radi-46eacfce">
              {searchResults.map((user) =>
          <div key={user.id} className="admin-p-12-borderbottom-0a48a6-transition-background-colorvar--mac-durat">
            
                  <div className="admin-flex-jc-between-ai-center">
                    <div>
                      <div className="admin-med-sm-primary">
                        {user.full_name || user.username}
                      </div>
                      <div className="admin-xs-secondary">
                        {user.phone} • {user.email}
                      </div>
                    </div>
                    <div className="admin-flex-gap-8">
                      <Button
                  size="small"
                  variant="outline"
                  onClick={() => selectUser(user, 'source')}
                  disabled={targetUser?.id === user.id}>
                  
                        {t('admin2.udtm_btn_source')}
                      </Button>
                      <Button
                  size="small"
                  variant="outline"
                  onClick={() => selectUser(user, 'target')}
                  disabled={sourceUser?.id === user.id}>
                  
                        {t('admin2.udtm_btn_target')}
                      </Button>
                    </div>
                  </div>
                </div>
          )}
            </div>
        }
        </div>
      </MacOSCard>

      {/* Выбранные пользователи */}
      <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-24">
        <MacOSCard className="admin-p-24">
          <h3 className="admin-lg-med-primary-m-0016px0">
            {t('admin2.udtm_source_user_title')}
          </h3>
          {sourceUser ?
        <div className="admin-flex-col-8">
              <div className="admin-med-sm-primary">
                {sourceUser.full_name || sourceUser.username}
              </div>
              <div className="admin-xs-secondary">
                {sourceUser.phone}
              </div>
              <div className="admin-xs-secondary">
                {sourceUser.email}
              </div>
              <Button
            size="small"
            variant="outline"
            onClick={() => {
              setSourceUser(null);
              setUserDataSummary(null);
            }}
            className="admin-mt-8-alignself-0e92fc">
            
                {t('admin2.udtm_clear_btn')}
              </Button>
            </div> :

        <div className="admin-secondary-ta-center-p-32px0-sm">
              {t('admin2.udtm_source_user_hint')}
            </div>
        }
        </MacOSCard>

        <MacOSCard className="admin-p-24">
          <h3 className="admin-lg-med-primary-m-0016px0">
            {t('admin2.udtm_target_user_title')}
          </h3>
          {targetUser ?
        <div className="admin-flex-col-8">
              <div className="admin-med-sm-primary">
                {targetUser.full_name || targetUser.username}
              </div>
              <div className="admin-xs-secondary">
                {targetUser.phone}
              </div>
              <div className="admin-xs-secondary">
                {targetUser.email}
              </div>
              <Button
            size="small"
            variant="outline"
            onClick={() => setTargetUser(null)}
            className="admin-mt-8-alignself-0e92fc">
            
                {t('admin2.udtm_clear_btn')}
              </Button>
            </div> :

        <div className="admin-secondary-ta-center-p-32px0-sm">
              {t('admin2.udtm_target_user_hint')}
            </div>
        }
        </MacOSCard>
      </div>

      {/* Сводка данных источника */}
      {userDataSummary &&
    <MacOSCard className="admin-p-24">
          <h3 className="admin-lg-med-primary-m-0016px0">
            {t('admin2.udtm_data_to_transfer')}
          </h3>
          <div className="admin-grid-gtc-rauto-fitcminmax150pxc1fr-gap-16-mb-16">
            <div className="admin-text-center">
              <div className="admin-2xl-bold-blue">
                {userDataSummary.data_counts.appointments}
              </div>
              <div className="admin-xs-secondary">
                {t('admin2.udtm_stat_appointments')}
              </div>
            </div>
            <div className="admin-text-center">
              <div className="admin-2xl-bold-success">
                {userDataSummary.data_counts.visits}
              </div>
              <div className="admin-xs-secondary">
                {t('admin2.udtm_stat_visits')}
              </div>
            </div>
            <div className="admin-text-center">
              <div className="admin-2xl-bold-warning">
                {userDataSummary.data_counts.queue_entries}
              </div>
              <div className="admin-xs-secondary">
                {t('admin2.udtm_stat_queue')}
              </div>
            </div>
          </div>
        </MacOSCard>
    }

      {/* Выбор типов данных */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-lg-med-primary-m-0016px0">
          {t('admin2.udtm_data_types_title')}
        </h3>
        <div className="admin-flex-col-12">
          {availableDataTypes.map((dataType) =>
        <label key={dataType.key} className="admin-flex-ai-center-gap-12-cursor-pointer-p-8-radius-var--mac-radius-sm-transit-87a65602"
        onMouseEnter={(e: React.MouseEvent<HTMLElement>) => (e.target as HTMLElement).style.backgroundColor = 'var(--mac-bg-secondary)'}
        onMouseLeave={(e: React.MouseEvent<HTMLElement>) => (e.target as HTMLElement).style.backgroundColor = 'transparent'}>
          
              <Checkbox
            checked={selectedDataTypes.includes(dataType.key)}
            onChange={(checked) => {
              if (checked) {
                setSelectedDataTypes((prev) => [...prev, dataType.key]);
              } else {
                setSelectedDataTypes((prev) => prev.filter((type) => type !== dataType.key));
              }
            }} />
          
              <div>
                <div className="admin-med-sm-primary">
                  {dataType.name}
                </div>
                <div className="admin-xs-secondary">
                  {dataType.description}
                </div>
              </div>
            </label>
        )}
        </div>
      </MacOSCard>

      {/* Кнопка передачи */}
      <div className="admin-flex-jc-center">
        <Button
        type="button"
        onClick={executeTransfer}
        disabled={!sourceUser || !targetUser || selectedDataTypes.length === 0 || isTransferring}
        aria-label="Transfer selected user data"
        className="admin-p-12px32">
        
          {isTransferring ?
        <>
              <div className="admin-w-16-h-16-bd-2solidwhite-bordertop-0dfa98-radius-50pct-anim-spin1slinearin-62066832"></div>
              {t('admin2.udtm_transferring')}
            </> :

        <>
              <ArrowRight className="admin-w-20-h-20-mr-8" />
              {t('admin2.udtm_transfer_btn')}
            </>
        }
        </Button>
      </div>
    </div>;


  const renderHistoryTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-flex-jc-between-ai-center-mb-16">
        <h3 className="admin-lg-med-primary-m-0">
          {t('admin2.udtm_history_title')}
        </h3>
        <Button onClick={loadTransferHistory} variant="outline">
          <History className="admin-icon-16-mr-8" />
          {t('admin2.udtm_refresh_btn')}
        </Button>
      </div>
      
      {transferHistory.length === 0 ?
    <div className="admin-ta-center-p-32px0-secondary-sm">
          {t('admin2.udtm_history_empty')}
        </div> :

    <div className="admin-flex-col-16">
          {transferHistory.map((transfer, index) =>
      <div key={index} className="admin-bd-1solidvar-mac-border-radius-var--mac-radius-md-p-16-bg-bg-secondary-tra-c057944f">
        
              <div className="admin-flex-jc-between-ai-start">
                <div>
                  <div className="admin-med-sm-primary">
                    {transfer.source_user} → {transfer.target_user}
                  </div>
                  <div className="admin-xs-secondary">
                    {new Date(transfer.transfer_date).toLocaleString()}
                  </div>
                </div>
                <div className="admin-flex-ai-center">
                  {transfer.success ?
            <CheckCircle className="admin-w-20-h-20-success" /> :

            <XCircle className="admin-w-20-h-20-error" />
            }
                </div>
              </div>
            </div>
      )}
        </div>
    }
    </MacOSCard>;


  const renderStatisticsTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-flex-jc-between-ai-center-mb-16">
        <h3 className="admin-lg-med-primary-m-0">
          {t('admin2.udtm_statistics_title')}
        </h3>
        <Button onClick={loadStatistics} variant="outline">
          <BarChart3 className="admin-icon-16-mr-8" />
          {t('admin2.udtm_refresh_btn')}
        </Button>
      </div>
      
      {statistics ?
    <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-24">
          <div className="admin-text-center">
            <div className="admin-3xl-bold-blue">
              {statistics.total_transfers}
            </div>
            <div className="admin-xs-secondary">
              {t('admin2.udtm_total_transfers')}
            </div>
          </div>
          <div className="admin-text-center">
            <div className="admin-3xl-bold-success">
              {statistics.successful_transfers}
            </div>
            <div className="admin-xs-secondary">
              {t('admin2.udtm_successful')}
            </div>
          </div>
          <div className="admin-text-center">
            <div className="admin-3xl-bold-error">
              {statistics.failed_transfers}
            </div>
            <div className="admin-xs-secondary">
              {t('admin2.udtm_failed')}
            </div>
          </div>
        </div> :

    <div className="admin-ta-center-p-32px0-secondary-sm">
          {t('admin2.udtm_statistics_hint')}
        </div>
    }
    </MacOSCard>;


  return (
    <div className="admin-maxw-1200-m-0auto-p-24-bg-bg-primary-minh-100vh">
      <div className="admin-mb-24">
        <h1 className="admin-2xl-semi-primary-m-008px0-flex-ai-center-gap-12">
          <Users className="admin-w-28-h-28" />
          {t('admin2.udtm_page_title')}
        </h1>
        <p className="admin-secondary-sm-m-0">
          {t('admin2.udtm_page_subtitle')}
        </p>
      </div>

      {/* Навигация по вкладкам */}
      <div className="admin-maxw-100pct-overflowx-auto-pb-6-mb-24-scrollbarwidth-b2a750">
        <SegmentedControl
          aria-label={t('admin2.udtm_tabs_aria')}
          value={activeTab}
          onChange={(value: unknown) => {
            const v = String(value) as 'transfer' | 'history' | 'statistics';
            setActiveTab(v);
            if (v === 'history') {
              loadTransferHistory();
            }
            if (v === 'statistics') {
              loadStatistics();
            }
          }}
          options={[
            {
              value: 'transfer',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <ArrowRight size={14} aria-hidden="true" />
                  {t('admin2.udtm_tab_transfer')}
                </span>
              )
            },
            {
              value: 'history',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <History size={14} aria-hidden="true" />
                  {t('admin2.udtm_tab_history')}
                </span>
              )
            },
            {
              value: 'statistics',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <BarChart3 size={14} aria-hidden="true" />
                  {t('admin2.udtm_tab_statistics')}
                </span>
              )
            }
          ]}
          size="large"
          className="admin-minw-max-content-background-3dc2d0-bd-1solidvar-mac-main-shell-border-radi-b45562d1" />
      </div>

      {/* Контент вкладок */}
      {activeTab === 'transfer' && renderTransferTab()}
      {activeTab === 'history' && renderHistoryTab()}
      {activeTab === 'statistics' && renderStatisticsTab()}
    </div>);

};

export default UserDataTransferManager;
