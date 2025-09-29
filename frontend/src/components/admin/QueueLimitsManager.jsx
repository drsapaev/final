import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  Users, 
  AlertCircle, 
  CheckCircle, 
  Edit, 
  Save, 
  X, 
  RefreshCw,
  TrendingUp,
  Clock,
  Shield
} from 'lucide-react';
import { toast } from 'react-toastify';

/**
 * Компонент управления лимитами очередей
 * Позволяет настраивать максимальное количество записей по специальностям
 */
const QueueLimitsManager = () => {
  const [limits, setLimits] = useState([]);
  const [queueStatus, setQueueStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingSpecialty, setEditingSpecialty] = useState(null);
  const [editValues, setEditValues] = useState({});

  // Загрузка данных
  const loadData = async () => {
    setLoading(true);
    try {
      const [limitsResponse, statusResponse] = await Promise.all([
        fetch('/api/admin/queue-limits', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }),
        fetch('/api/admin/queue-status', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
      ]);

      if (limitsResponse.ok) {
        const limitsData = await limitsResponse.json();
        setLimits(limitsData);
      }

      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setQueueStatus(statusData);
      }
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных о лимитах');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Начать редактирование
  const startEditing = (specialty, currentLimits) => {
    setEditingSpecialty(specialty);
    setEditValues({
      max_per_day: currentLimits.max_per_day,
      start_number: currentLimits.start_number
    });
  };

  // Отменить редактирование
  const cancelEditing = () => {
    setEditingSpecialty(null);
    setEditValues({});
  };

  // Сохранить изменения
  const saveChanges = async (specialty) => {
    setSaving(true);
    try {
      const response = await fetch('/api/admin/queue-limits', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify([{
          specialty: specialty,
          max_per_day: parseInt(editValues.max_per_day),
          start_number: parseInt(editValues.start_number)
        }])
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        setEditingSpecialty(null);
        setEditValues({});
        await loadData(); // Перезагружаем данные
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      toast.error('Ошибка сохранения изменений');
    } finally {
      setSaving(false);
    }
  };

  // Сброс лимитов
  const resetLimits = async (specialty = null) => {
    if (!confirm(specialty ? 
      `Сбросить лимиты для специальности "${specialty}"?` : 
      'Сбросить все лимиты к значениям по умолчанию?'
    )) {
      return;
    }

    try {
      const url = specialty ? 
        `/api/admin/reset-queue-limits?specialty=${specialty}` : 
        '/api/admin/reset-queue-limits';
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        await loadData();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка сброса');
      }
    } catch (error) {
      console.error('Ошибка сброса:', error);
      toast.error('Ошибка сброса лимитов');
    }
  };

  // Получить статистику по специальности
  const getSpecialtyStats = (specialty) => {
    return queueStatus.filter(status => status.specialty === specialty);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-600">Загрузка лимитов...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-500" />
            Лимиты очередей
          </h2>
          <p className="text-gray-600 mt-1">
            Управление максимальным количеством онлайн записей по специальностям
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => loadData()}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Обновить
          </button>
          <button
            onClick={() => resetLimits()}
            className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
          >
            Сбросить все
          </button>
        </div>
      </div>

      {/* Карточки специальностей */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {limits.map((limit) => {
          const specialtyStats = getSpecialtyStats(limit.specialty);
          const isEditing = editingSpecialty === limit.specialty;
          const totalCurrentEntries = specialtyStats.reduce((sum, stat) => sum + stat.current_entries, 0);
          const totalMaxEntries = specialtyStats.reduce((sum, stat) => sum + stat.max_entries, 0);
          const utilizationPercent = totalMaxEntries > 0 ? (totalCurrentEntries / totalMaxEntries) * 100 : 0;

          return (
            <div key={limit.specialty} className="bg-white rounded-lg shadow-md p-6 border">
              {/* Заголовок специальности */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 capitalize">
                    {limit.specialty}
                  </h3>
                  <p className="text-sm text-gray-500">
                    {limit.doctors_count} врач(ей)
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {utilizationPercent > 80 ? (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                </div>
              </div>

              {/* Статистика использования */}
              <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">Использование сегодня</span>
                  <span className="text-sm font-medium">
                    {totalCurrentEntries} / {totalMaxEntries}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-300 ${
                      utilizationPercent > 80 ? 'bg-red-500' : 
                      utilizationPercent > 60 ? 'bg-yellow-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(utilizationPercent, 100)}%` }}
                  ></div>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {utilizationPercent.toFixed(1)}% заполнено
                </div>
              </div>

              {/* Настройки лимитов */}
              <div className="space-y-3">
                {/* Максимум в день */}
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700">
                    Максимум в день:
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={editValues.max_per_day}
                      onChange={(e) => setEditValues({
                        ...editValues,
                        max_per_day: e.target.value
                      })}
                      className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                    />
                  ) : (
                    <span className="text-sm font-semibold text-gray-900">
                      {limit.max_per_day}
                    </span>
                  )}
                </div>

                {/* Начальный номер */}
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700">
                    Начальный номер:
                  </label>
                  {isEditing ? (
                    <input
                      type="number"
                      min="1"
                      max="999"
                      value={editValues.start_number}
                      onChange={(e) => setEditValues({
                        ...editValues,
                        start_number: e.target.value
                      })}
                      className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                    />
                  ) : (
                    <span className="text-sm font-semibold text-gray-900">
                      {limit.start_number}
                    </span>
                  )}
                </div>
              </div>

              {/* Кнопки действий */}
              <div className="mt-4 pt-4 border-t border-gray-200">
                {isEditing ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveChanges(limit.specialty)}
                      disabled={saving}
                      className="flex-1 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center gap-2 text-sm disabled:opacity-50"
                    >
                      <Save className="h-4 w-4" />
                      {saving ? 'Сохранение...' : 'Сохранить'}
                    </button>
                    <button
                      onClick={cancelEditing}
                      disabled={saving}
                      className="px-3 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors disabled:opacity-50"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button
                      onClick={() => startEditing(limit.specialty, limit)}
                      className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 text-sm"
                    >
                      <Edit className="h-4 w-4" />
                      Изменить
                    </button>
                    <button
                      onClick={() => resetLimits(limit.specialty)}
                      className="px-3 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors text-sm"
                    >
                      Сброс
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Детальная статистика по врачам */}
      {queueStatus.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-blue-500" />
            Статус очередей по врачам
          </h3>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Врач
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Специальность
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Кабинет
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Записи
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Статус
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {queueStatus.map((status) => (
                  <tr key={status.doctor_id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-8 w-8">
                          <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center">
                            <Users className="h-4 w-4 text-blue-600" />
                          </div>
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-gray-900">
                            {status.doctor_name}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 capitalize">
                      {status.specialty}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {status.cabinet || 'Не указан'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="flex items-center gap-2">
                        <span>{status.current_entries} / {status.max_entries}</span>
                        {status.limit_reached && (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        {status.queue_opened ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            <Clock className="h-3 w-3 mr-1" />
                            Прием открыт
                          </span>
                        ) : status.online_available ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            Онлайн доступен
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            Недоступен
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueueLimitsManager;



