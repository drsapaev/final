import { useState, useEffect } from 'react';
import {
  Card, Button, Input, Checkbox, SegmentedControl,
} from '../ui/macos';
import { Users, ArrowRight, Search, CheckCircle, XCircle, History, BarChart3 } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const toArray = (value, fallbackKeys = []) => {
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
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Поиск пользователей */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-text-primary)',
        margin: '0 0 16px 0',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
          <Search style={{ width: '20px', height: '20px' }} />
          Поиск пользователей
        </h3>
        
        <div style={{ position: 'relative' }}>
          <Input
          type="text"
          placeholder="Введите имя, телефон или email..."
          value={searchQuery}
          onChange={handleSearchChange}
          style={{ width: '100%' }} />
        
          
          {isSearching &&
        <div style={{ position: 'absolute', right: '12px', top: '12px' }}>
              <div style={{
            width: '16px',
            height: '16px',
            border: '2px solid var(--mac-accent-blue)',
            borderTop: '2px solid transparent',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }}></div>
            </div>
        }
          
          {searchResults.length > 0 &&
        <div style={{
          position: 'absolute',
          zIndex: 10,
          width: '100%',
          marginTop: '4px',
          backgroundColor: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-md)',
          boxShadow: 'var(--mac-shadow-lg)',
          maxHeight: '240px',
          overflowY: 'auto'
        }}>
              {searchResults.map((user) =>
          <div key={user.id} style={{
            padding: '12px',
            borderBottom: '1px solid var(--mac-border)',
            transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
          }}>
            
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)'
                }}>
                        {user.full_name || user.username}
                      </div>
                      <div style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-secondary)'
                }}>
                        {user.phone} • {user.email}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
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
      </Card>

      {/* Выбранные пользователи */}
      <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
      gap: '24px'
    }}>
        <Card style={{ padding: '24px' }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0'
        }}>
            Пользователь-источник
          </h3>
          {sourceUser ?
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{
            fontWeight: 'var(--mac-font-weight-medium)',
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
                {sourceUser.full_name || sourceUser.username}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                {sourceUser.phone}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                {sourceUser.email}
              </div>
              <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSourceUser(null);
              setUserDataSummary(null);
            }}
            style={{ marginTop: '8px', alignSelf: 'flex-start' }}>
            
                Очистить
              </Button>
            </div> :

        <div style={{
          color: 'var(--mac-text-secondary)',
          textAlign: 'center',
          padding: '32px 0',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
              Выберите пользователя-источника из результатов поиска
            </div>
        }
        </Card>

        <Card style={{ padding: '24px' }}>
          <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0'
        }}>
            Пользователь-получатель
          </h3>
          {targetUser ?
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{
            fontWeight: 'var(--mac-font-weight-medium)',
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)'
          }}>
                {targetUser.full_name || targetUser.username}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                {targetUser.phone}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                {targetUser.email}
              </div>
              <Button
            size="sm"
            variant="outline"
            onClick={() => setTargetUser(null)}
            style={{ marginTop: '8px', alignSelf: 'flex-start' }}>
            
                Очистить
              </Button>
            </div> :

        <div style={{
          color: 'var(--mac-text-secondary)',
          textAlign: 'center',
          padding: '32px 0',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
              Выберите пользователя-получателя из результатов поиска
            </div>
        }
        </Card>
      </div>

      {/* Сводка данных источника */}
      {userDataSummary &&
    <Card style={{ padding: '24px' }}>
          <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-text-primary)',
        margin: '0 0 16px 0'
      }}>
            Данные для передачи
          </h3>
          <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '16px',
        marginBottom: '16px'
      }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-accent-blue)'
          }}>
                {userDataSummary.data_counts.appointments}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                Назначений
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-success)'
          }}>
                {userDataSummary.data_counts.visits}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                Визитов
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-warning)'
          }}>
                {userDataSummary.data_counts.queue_entries}
              </div>
              <div style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary)'
          }}>
                Записей в очереди
              </div>
            </div>
          </div>
        </Card>
    }

      {/* Выбор типов данных */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-text-primary)',
        margin: '0 0 16px 0'
      }}>
          Типы данных для передачи
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {availableDataTypes.map((dataType) =>
        <label key={dataType.key} style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          cursor: 'pointer',
          padding: '8px',
          borderRadius: 'var(--mac-radius-sm)',
          transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
        }}
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
                <div style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
                  {dataType.name}
                </div>
                <div style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-text-secondary)'
            }}>
                  {dataType.description}
                </div>
              </div>
            </label>
        )}
        </div>
      </Card>

      {/* Кнопка передачи */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <Button
        type="button"
        onClick={executeTransfer}
        disabled={!sourceUser || !targetUser || selectedDataTypes.length === 0 || isTransferring}
        aria-label="Transfer selected user data"
        style={{ padding: '12px 32px' }}>
        
          {isTransferring ?
        <>
              <div style={{
            width: '16px',
            height: '16px',
            border: '2px solid white',
            borderTop: '2px solid transparent',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginRight: '8px'
          }}></div>
              Передача данных...
            </> :

        <>
              <ArrowRight style={{ width: '20px', height: '20px', marginRight: '8px' }} />
              Передать данные
            </>
        }
        </Button>
      </div>
    </div>;


  const renderHistoryTab = () =>
  <Card style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-text-primary)',
        margin: 0
      }}>
          История передач
        </h3>
        <Button onClick={loadTransferHistory} variant="outline">
          <History style={{ width: '16px', height: '16px', marginRight: '8px' }} />
          Обновить
        </Button>
      </div>
      
      {transferHistory.length === 0 ?
    <div style={{
      textAlign: 'center',
      padding: '32px 0',
      color: 'var(--mac-text-secondary)',
      fontSize: 'var(--mac-font-size-sm)'
    }}>
          История передач пуста
        </div> :

    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {transferHistory.map((transfer, index) =>
      <div key={index} style={{
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
        padding: '16px',
        backgroundColor: 'var(--mac-bg-secondary)',
        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
      }}>
        
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
                    {transfer.source_user} → {transfer.target_user}
                  </div>
                  <div style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-text-secondary)'
            }}>
                    {new Date(transfer.transfer_date).toLocaleString()}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {transfer.success ?
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} /> :

            <XCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
            }
                </div>
              </div>
            </div>
      )}
        </div>
    }
    </Card>;


  const renderStatisticsTab = () =>
  <Card style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-text-primary)',
        margin: 0
      }}>
          Статистика передач
        </h3>
        <Button onClick={loadStatistics} variant="outline">
          <BarChart3 style={{ width: '16px', height: '16px', marginRight: '8px' }} />
          Обновить
        </Button>
      </div>
      
      {statistics ?
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '24px'
    }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
          fontSize: 'var(--mac-font-size-3xl)',
          fontWeight: 'var(--mac-font-weight-bold)',
          color: 'var(--mac-accent-blue)'
        }}>
              {statistics.total_transfers}
            </div>
            <div style={{
          fontSize: 'var(--mac-font-size-xs)',
          color: 'var(--mac-text-secondary)'
        }}>
              Всего передач
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
          fontSize: 'var(--mac-font-size-3xl)',
          fontWeight: 'var(--mac-font-weight-bold)',
          color: 'var(--mac-success)'
        }}>
              {statistics.successful_transfers}
            </div>
            <div style={{
          fontSize: 'var(--mac-font-size-xs)',
          color: 'var(--mac-text-secondary)'
        }}>
              Успешных
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{
          fontSize: 'var(--mac-font-size-3xl)',
          fontWeight: 'var(--mac-font-weight-bold)',
          color: 'var(--mac-error)'
        }}>
              {statistics.failed_transfers}
            </div>
            <div style={{
          fontSize: 'var(--mac-font-size-xs)',
          color: 'var(--mac-text-secondary)'
        }}>
              Неудачных
            </div>
          </div>
        </div> :

    <div style={{
      textAlign: 'center',
      padding: '32px 0',
      color: 'var(--mac-text-secondary)',
      fontSize: 'var(--mac-font-size-sm)'
    }}>
          Нажмите «Обновить» для загрузки статистики
        </div>
    }
    </Card>;


  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{
          fontSize: 'var(--mac-font-size-2xl)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 8px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <Users style={{ width: '28px', height: '28px' }} />
          Передача данных пользователей
        </h1>
        <p style={{
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)',
          margin: 0
        }}>
          Управление передачей назначений, визитов и записей в очереди между пользователями
        </p>
      </div>

      {/* Навигация по вкладкам */}
      <div style={{
        maxWidth: '100%',
        overflowX: 'auto',
        paddingBottom: '6px',
        marginBottom: '24px',
        scrollbarWidth: 'thin'
      }}>
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
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <ArrowRight size={14} aria-hidden="true" />
                  Передача данных
                </span>
              )
            },
            {
              value: 'history',
              label: (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <History size={14} aria-hidden="true" />
                  История
                </span>
              )
            },
            {
              value: 'statistics',
              label: (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <BarChart3 size={14} aria-hidden="true" />
                  Статистика
                </span>
              )
            }
          ]}
          size="large"
          style={{
            minWidth: 'max-content',
            background: 'var(--mac-gradient-sidebar)',
            border: '1px solid var(--mac-main-shell-border)',
            borderRadius: '14px',
            boxShadow: 'var(--mac-main-shell-shadow)'
          }} />
      </div>

      {/* Контент вкладок */}
      {activeTab === 'transfer' && renderTransferTab()}
      {activeTab === 'history' && renderHistoryTab()}
      {activeTab === 'statistics' && renderStatisticsTab()}
    </div>);

};

export default UserDataTransferManager;
