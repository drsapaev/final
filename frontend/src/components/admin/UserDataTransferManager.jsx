import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import {
  MacOSCard, Button, Input, Checkbox, SegmentedControl,
} from '../ui/macos';
import { Users, ArrowRight, Search, CheckCircle, XCircle, History, BarChart3 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const toArray = (value, fallbackKeys = []) => {
  const { t } = useTranslation();
  if (Array.isArray(value)) return value;

  for (const key of fallbackKeys) {
    if (Array.isArray(value?.[key])) {
      return value[key];
    }
  }

  return [];
};

const normalizeDataTypes = (payload) =>
  toArray(payload, ['data_types', 'dataTypes', 'items', 'results']).map((item) => {
    if (typeof item === 'string') {
      return { key: item, name: item, description: '' };
    }

    const key = item?.key || item?.value || item?.id || item?.name;
    if (!key) return null;

    return {
      ...item,
      key,
      name: item?.name || item?.label || key,
      description: item?.description || ''
    };
  }).filter(Boolean);

const normalizeDataSummary = (payload) => ({
  ...(payload || {}),
  data_counts: {
    appointments: 0,
    visits: 0,
    queue_entries: 0,
    ...(payload?.data_counts || {})
  }
});

const normalizeStatistics = (payload) => ({
  total_transfers: 0,
  successful_transfers: 0,
  failed_transfers: 0,
  ...(payload || {})
});

const UserDataTransferManager = () => {
  const [activeTab, setActiveTab] = useState('transfer');
  const [sourceUser, setSourceUser] = useState(null);
  const [targetUser, setTargetUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedDataTypes, setSelectedDataTypes] = useState(['appointments', 'visits', 'queue_entries']);
  const [availableDataTypes, setAvailableDataTypes] = useState([]);
  const [isTransferring, setIsTransferring] = useState(false);
  const [transferHistory, setTransferHistory] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [userDataSummary, setUserDataSummary] = useState(null);

  // Загрузка доступных типов данных
  useEffect(() => {
    loadAvailableDataTypes();
  }, []);

  const loadAvailableDataTypes = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/data-types');
      setAvailableDataTypes(normalizeDataTypes(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки типов данных:', error);
      toast.error('Ошибка загрузки типов данных');
    }
  };

  const searchUsers = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const response = await api.get(`/admin/user-data/users/search?query=${encodeURIComponent(query)}&limit=10`);
      setSearchResults(toArray(response.data, ['users', 'items', 'results']));
    } catch (error) {
      logger.error('Ошибка поиска пользователей:', error);
      toast.error('Ошибка поиска пользователей');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const getUserDataSummary = async (userId) => {
    try {
      const response = await api.get(`/admin/user-data/users/${userId}/data-summary`);
      setUserDataSummary(normalizeDataSummary(response.data));
    } catch (error) {
      logger.error('Ошибка получения сводки данных:', error);
      toast.error('Ошибка получения данных пользователя');
    }
  };

  const validateTransfer = async () => {
    if (!sourceUser || !targetUser) {
      toast.error('Выберите пользователей для передачи');
      return false;
    }

    try {
      const response = await api.post(`/admin/user-data/transfer/validate?source_user_id=${sourceUser.id}&target_user_id=${targetUser.id}`);
      const validation = response.data || {};

      if (!validation.valid) {
        toast.error(validation.message || 'Transfer validation failed');
        return false;
      }

      return true;
    } catch (error) {
      logger.error('Ошибка валидации:', error);
      toast.error('Ошибка валидации передачи');
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
        source_user_id: sourceUser.id,
        target_user_id: targetUser.id,
        data_types: selectedDataTypes,
        confirmation_required: false
      });
      const transferResult = response.data || {};

      if (transferResult.success) {
        toast.success('Данные успешно переданы!');

        // Показываем результаты передачи
        const transferred = transferResult.transferred || {};
        let message = 'Передано:\n';

        if (transferred.appointments?.success) {
          message += `• Назначений: ${transferred.appointments.count}\n`;
        }
        if (transferred.visits?.success) {
          message += `• Визитов: ${transferred.visits.count}\n`;
        }
        if (transferred.queue_entries?.success) {
          message += `• Записей в очереди: ${transferred.queue_entries.count}\n`;
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
        toast.error('Ошибка передачи данных');
      }
    } catch (error) {
      logger.error('Ошибка передачи:', error);
      toast.error('Ошибка выполнения передачи');
    } finally {
      setIsTransferring(false);
    }
  };

  const loadTransferHistory = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/history?limit=50');
      setTransferHistory(toArray(response.data, ['history', 'items', 'results']));
    } catch (error) {
      logger.error('Ошибка загрузки истории:', error);
      toast.error('Ошибка загрузки истории');
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/statistics?period_days=30');
      setStatistics(normalizeStatistics(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      toast.error('Ошибка загрузки статистики');
    }
  };

  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    searchUsers(query);
  };

  const selectUser = (user, type) => {
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
          Поиск пользователей
        </h3>
        
        <div className="admin-pos-relative">
          <Input
          type="text"
          placeholder="Введите имя, телефон или email..."
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
                  size="sm"
                  variant="outline"
                  onClick={() => selectUser(user, 'source')}
                  disabled={targetUser?.id === user.id}>
                  
                        Источник
                      </Button>
                      <Button
                  size="sm"
                  variant="outline"
                  onClick={() => selectUser(user, 'target')}
                  disabled={sourceUser?.id === user.id}>
                  
                        Получатель
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
            Пользователь-источник
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
            size="sm"
            variant="outline"
            onClick={() => {
              setSourceUser(null);
              setUserDataSummary(null);
            }}
            className="admin-mt-8-alignself-0e92fc">
            
                Очистить
              </Button>
            </div> :

        <div className="admin-secondary-ta-center-p-32px0-sm">
              Выберите пользователя-источника из результатов поиска
            </div>
        }
        </MacOSCard>

        <MacOSCard className="admin-p-24">
          <h3 className="admin-lg-med-primary-m-0016px0">
            Пользователь-получатель
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
            size="sm"
            variant="outline"
            onClick={() => setTargetUser(null)}
            className="admin-mt-8-alignself-0e92fc">
            
                Очистить
              </Button>
            </div> :

        <div className="admin-secondary-ta-center-p-32px0-sm">
              Выберите пользователя-получателя из результатов поиска
            </div>
        }
        </MacOSCard>
      </div>

      {/* Сводка данных источника */}
      {userDataSummary &&
    <MacOSCard className="admin-p-24">
          <h3 className="admin-lg-med-primary-m-0016px0">
            Данные для передачи
          </h3>
          <div className="admin-grid-gtc-rauto-fitcminmax150pxc1fr-gap-16-mb-16">
            <div className="admin-text-center">
              <div className="admin-2xl-bold-blue">
                {userDataSummary.data_counts.appointments}
              </div>
              <div className="admin-xs-secondary">
                Назначений
              </div>
            </div>
            <div className="admin-text-center">
              <div className="admin-2xl-bold-success">
                {userDataSummary.data_counts.visits}
              </div>
              <div className="admin-xs-secondary">
                Визитов
              </div>
            </div>
            <div className="admin-text-center">
              <div className="admin-2xl-bold-warning">
                {userDataSummary.data_counts.queue_entries}
              </div>
              <div className="admin-xs-secondary">
                Записей в очереди
              </div>
            </div>
          </div>
        </MacOSCard>
    }

      {/* Выбор типов данных */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-lg-med-primary-m-0016px0">
          Типы данных для передачи
        </h3>
        <div className="admin-flex-col-12">
          {availableDataTypes.map((dataType) =>
        <label key={dataType.key} className="admin-flex-ai-center-gap-12-cursor-pointer-p-8-radius-var--mac-radius-sm-transit-87a65602"
        onMouseEnter={(e) => e.target.style.backgroundColor = 'var(--mac-bg-secondary)'}
        onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}>
          
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
              Передача данных...
            </> :

        <>
              <ArrowRight className="admin-w-20-h-20-mr-8" />
              Передать данные
            </>
        }
        </Button>
      </div>
    </div>;


  const renderHistoryTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-flex-jc-between-ai-center-mb-16">
        <h3 className="admin-lg-med-primary-m-0">
          История передач
        </h3>
        <Button onClick={loadTransferHistory} variant="outline">
          <History className="admin-icon-16-mr-8" />
          Обновить
        </Button>
      </div>
      
      {transferHistory.length === 0 ?
    <div className="admin-ta-center-p-32px0-secondary-sm">
          История передач пуста
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
          Статистика передач
        </h3>
        <Button onClick={loadStatistics} variant="outline">
          <BarChart3 className="admin-icon-16-mr-8" />
          Обновить
        </Button>
      </div>
      
      {statistics ?
    <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-24">
          <div className="admin-text-center">
            <div className="admin-3xl-bold-blue">
              {statistics.total_transfers}
            </div>
            <div className="admin-xs-secondary">
              Всего передач
            </div>
          </div>
          <div className="admin-text-center">
            <div className="admin-3xl-bold-success">
              {statistics.successful_transfers}
            </div>
            <div className="admin-xs-secondary">
              Успешных
            </div>
          </div>
          <div className="admin-text-center">
            <div className="admin-3xl-bold-error">
              {statistics.failed_transfers}
            </div>
            <div className="admin-xs-secondary">
              Неудачных
            </div>
          </div>
        </div> :

    <div className="admin-ta-center-p-32px0-secondary-sm">
          Нажмите «Обновить» для загрузки статистики
        </div>
    }
    </MacOSCard>;


  return (
    <div className="admin-maxw-1200-m-0auto-p-24-bg-bg-primary-minh-100vh">
      <div className="admin-mb-24">
        <h1 className="admin-2xl-semi-primary-m-008px0-flex-ai-center-gap-12">
          <Users className="admin-w-28-h-28" />
          Передача данных пользователей
        </h1>
        <p className="admin-secondary-sm-m-0">
          Управление передачей назначений, визитов и записей в очереди между пользователями
        </p>
      </div>

      {/* Навигация по вкладкам */}
      <div className="admin-maxw-100pct-overflowx-auto-pb-6-mb-24-scrollbarwidth-b2a750">
        <SegmentedControl
          aria-label="Разделы передачи данных пользователей"
          value={activeTab}
          onChange={(value) => {
            setActiveTab(value);
            if (value === 'history') {
              loadTransferHistory();
            }
            if (value === 'statistics') {
              loadStatistics();
            }
          }}
          options={[
            {
              value: 'transfer',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <ArrowRight size={14} aria-hidden="true" />
                  Передача данных
                </span>
              )
            },
            {
              value: 'history',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <History size={14} aria-hidden="true" />
                  История
                </span>
              )
            },
            {
              value: 'statistics',
              label: (
                <span className="admin-inline-flex-ai-center-gap-8">
                  <BarChart3 size={14} aria-hidden="true" />
                  Статистика
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
