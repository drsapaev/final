import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Label, Select } from '../ui/native';
import { Users, ArrowRight, Search, CheckCircle, XCircle, AlertTriangle, History, BarChart3 } from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

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
      setAvailableDataTypes(response.data.data_types);
    } catch (error) {
      console.error('Ошибка загрузки типов данных:', error);
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
      setSearchResults(response.data.users);
    } catch (error) {
      console.error('Ошибка поиска пользователей:', error);
      toast.error('Ошибка поиска пользователей');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const getUserDataSummary = async (userId) => {
    try {
      const response = await api.get(`/admin/user-data/users/${userId}/data-summary`);
      setUserDataSummary(response.data);
    } catch (error) {
      console.error('Ошибка получения сводки данных:', error);
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
      
      if (!response.data.valid) {
        toast.error(response.data.message);
        return false;
      }

      return true;
    } catch (error) {
      console.error('Ошибка валидации:', error);
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

      if (response.data.success) {
        toast.success('Данные успешно переданы!');
        
        // Показываем результаты передачи
        const transferred = response.data.transferred;
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
      console.error('Ошибка передачи:', error);
      toast.error('Ошибка выполнения передачи');
    } finally {
      setIsTransferring(false);
    }
  };

  const loadTransferHistory = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/history?limit=50');
      setTransferHistory(response.data.history);
    } catch (error) {
      console.error('Ошибка загрузки истории:', error);
      toast.error('Ошибка загрузки истории');
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await api.get('/admin/user-data/transfer/statistics?period_days=30');
      setStatistics(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
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

  const handleDataTypeChange = (dataType) => {
    setSelectedDataTypes(prev => 
      prev.includes(dataType) 
        ? prev.filter(type => type !== dataType)
        : [...prev, dataType]
    );
  };

  const renderTransferTab = () => (
    <div className="space-y-6">
      {/* Поиск пользователей */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Search className="mr-2" size={20} />
          Поиск пользователей
        </h3>
        
        <div className="relative">
          <Input
            type="text"
            placeholder="Введите имя, телефон или email..."
            value={searchQuery}
            onChange={handleSearchChange}
            className="w-full"
          />
          
          {isSearching && (
            <div className="absolute right-3 top-3">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            </div>
          )}
          
          {searchResults.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
              {searchResults.map(user => (
                <div key={user.id} className="p-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium">{user.full_name || user.username}</div>
                      <div className="text-sm text-gray-500">
                        {user.phone} • {user.email}
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => selectUser(user, 'source')}
                        disabled={targetUser?.id === user.id}
                      >
                        Источник
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => selectUser(user, 'target')}
                        disabled={sourceUser?.id === user.id}
                      >
                        Получатель
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Выбранные пользователи */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Пользователь-источник</h3>
          {sourceUser ? (
            <div className="space-y-2">
              <div className="font-medium">{sourceUser.full_name || sourceUser.username}</div>
              <div className="text-sm text-gray-500">{sourceUser.phone}</div>
              <div className="text-sm text-gray-500">{sourceUser.email}</div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setSourceUser(null);
                  setUserDataSummary(null);
                }}
              >
                Очистить
              </Button>
            </div>
          ) : (
            <div className="text-gray-500 text-center py-8">
              Выберите пользователя-источника из результатов поиска
            </div>
          )}
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Пользователь-получатель</h3>
          {targetUser ? (
            <div className="space-y-2">
              <div className="font-medium">{targetUser.full_name || targetUser.username}</div>
              <div className="text-sm text-gray-500">{targetUser.phone}</div>
              <div className="text-sm text-gray-500">{targetUser.email}</div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setTargetUser(null)}
              >
                Очистить
              </Button>
            </div>
          ) : (
            <div className="text-gray-500 text-center py-8">
              Выберите пользователя-получателя из результатов поиска
            </div>
          )}
        </Card>
      </div>

      {/* Сводка данных источника */}
      {userDataSummary && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Данные для передачи</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{userDataSummary.data_counts.appointments}</div>
              <div className="text-sm text-gray-500">Назначений</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{userDataSummary.data_counts.visits}</div>
              <div className="text-sm text-gray-500">Визитов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{userDataSummary.data_counts.queue_entries}</div>
              <div className="text-sm text-gray-500">Записей в очереди</div>
            </div>
          </div>
        </Card>
      )}

      {/* Выбор типов данных */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Типы данных для передачи</h3>
        <div className="space-y-3">
          {availableDataTypes.map(dataType => (
            <label key={dataType.key} className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={selectedDataTypes.includes(dataType.key)}
                onChange={() => handleDataTypeChange(dataType.key)}
                className="rounded border-gray-300"
              />
              <div>
                <div className="font-medium">{dataType.name}</div>
                <div className="text-sm text-gray-500">{dataType.description}</div>
              </div>
            </label>
          ))}
        </div>
      </Card>

      {/* Кнопка передачи */}
      <div className="flex justify-center">
        <Button
          onClick={executeTransfer}
          disabled={!sourceUser || !targetUser || selectedDataTypes.length === 0 || isTransferring}
          className="px-8 py-3"
        >
          {isTransferring ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Передача данных...
            </>
          ) : (
            <>
              <ArrowRight className="mr-2" size={20} />
              Передать данные
            </>
          )}
        </Button>
      </div>
    </div>
  );

  const renderHistoryTab = () => (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">История передач</h3>
        <Button onClick={loadTransferHistory} variant="outline">
          <History className="mr-2" size={16} />
          Обновить
        </Button>
      </div>
      
      {transferHistory.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          История передач пуста
        </div>
      ) : (
        <div className="space-y-4">
          {transferHistory.map((transfer, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-medium">
                    {transfer.source_user} → {transfer.target_user}
                  </div>
                  <div className="text-sm text-gray-500">
                    {new Date(transfer.transfer_date).toLocaleString()}
                  </div>
                </div>
                <div className="flex items-center">
                  {transfer.success ? (
                    <CheckCircle className="text-green-500" size={20} />
                  ) : (
                    <XCircle className="text-red-500" size={20} />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const renderStatisticsTab = () => (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Статистика передач</h3>
        <Button onClick={loadStatistics} variant="outline">
          <BarChart3 className="mr-2" size={16} />
          Обновить
        </Button>
      </div>
      
      {statistics ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600">{statistics.total_transfers}</div>
            <div className="text-sm text-gray-500">Всего передач</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">{statistics.successful_transfers}</div>
            <div className="text-sm text-gray-500">Успешных</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-red-600">{statistics.failed_transfers}</div>
            <div className="text-sm text-gray-500">Неудачных</div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          Нажмите "Обновить" для загрузки статистики
        </div>
      )}
    </Card>
  );

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2 flex items-center">
          <Users className="mr-3" size={28} />
          Передача данных пользователей
        </h1>
        <p className="text-gray-600">
          Управление передачей назначений, визитов и записей в очереди между пользователями
        </p>
      </div>

      {/* Навигация по вкладкам */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        <button
          onClick={() => setActiveTab('transfer')}
          className={`px-4 py-2 rounded-md transition-colors ${
            activeTab === 'transfer'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Передача данных
        </button>
        <button
          onClick={() => {
            setActiveTab('history');
            loadTransferHistory();
          }}
          className={`px-4 py-2 rounded-md transition-colors ${
            activeTab === 'history'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          История
        </button>
        <button
          onClick={() => {
            setActiveTab('statistics');
            loadStatistics();
          }}
          className={`px-4 py-2 rounded-md transition-colors ${
            activeTab === 'statistics'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Статистика
        </button>
      </div>

      {/* Контент вкладок */}
      {activeTab === 'transfer' && renderTransferTab()}
      {activeTab === 'history' && renderHistoryTab()}
      {activeTab === 'statistics' && renderStatisticsTab()}
    </div>
  );
};

export default UserDataTransferManager;

