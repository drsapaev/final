import React, { useState, useEffect } from 'react';
import { 
  QrCode, 
  Plus, 
  Download, 
  Trash2, 
  Eye, 
  Copy, 
  Users,
  Calendar,
  Clock,
  AlertCircle,
  CheckCircle
} from 'lucide-react';

const QRTokenManager = () => {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [selectedToken, setSelectedToken] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Форма создания токена
  const [createForm, setCreateForm] = useState({
    specialist_id: '',
    department: '',
    expires_hours: 24
  });

  // Список специалистов и отделений (в реальном приложении загружается с сервера)
  const specialists = [
    { id: 1, name: 'Доктор Иванов И.И.', department: 'cardiology' },
    { id: 2, name: 'Доктор Петров П.П.', department: 'dermatology' },
    { id: 3, name: 'Доктор Сидоров С.С.', department: 'dentistry' },
  ];

  const departments = [
    { value: 'cardiology', label: 'Кардиология' },
    { value: 'dermatology', label: 'Дерматология' },
    { value: 'dentistry', label: 'Стоматология' },
    { value: 'laboratory', label: 'Лаборатория' },
    { value: 'ecg', label: 'ЭКГ' },
  ];

  useEffect(() => {
    loadTokens();
  }, []);

  const loadTokens = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/admin/qr-tokens/active', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки токенов');
      }

      const data = await response.json();
      setTokens(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const createToken = async () => {
    try {
      setError(null);
      const response = await fetch('/api/v1/admin/qr-tokens/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(createForm)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка создания токена');
      }

      const newToken = await response.json();
      setTokens(prev => [newToken, ...prev]);
      setShowCreateModal(false);
      setCreateForm({ specialist_id: '', department: '', expires_hours: 24 });
      setSuccess('QR токен успешно создан');
      
      // Показываем QR код нового токена
      setSelectedToken(newToken);
      setShowQRModal(true);
      
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteToken = async (token) => {
    if (!confirm('Вы уверены, что хотите деактивировать этот QR токен?')) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/admin/qr-tokens/${token}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка деактивации токена');
      }

      setTokens(prev => prev.filter(t => t.token !== token));
      setSuccess('QR токен деактивирован');
    } catch (err) {
      setError(err.message);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess('Ссылка скопирована в буфер обмена');
  };

  const downloadQR = (token) => {
    const link = document.createElement('a');
    link.href = token.qr_code_base64;
    link.download = `qr-token-${token.token.substring(0, 8)}.png`;
    link.click();
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getDepartmentName = (department) => {
    const dept = departments.find(d => d.value === department);
    return dept ? dept.label : department;
  };

  const getSpecialistName = (specialistId) => {
    const specialist = specialists.find(s => s.id === specialistId);
    return specialist ? specialist.name : `ID: ${specialistId}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок и кнопка создания */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">QR Токены для очередей</h2>
          <p className="text-gray-600">Управление QR кодами для присоединения к очередям</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center"
        >
          <Plus className="h-4 w-4 mr-2" />
          Создать QR токен
        </button>
      </div>

      {/* Уведомления */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
          <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
          <span className="text-red-700">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
          <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
          <span className="text-green-700">{success}</span>
          <button onClick={() => setSuccess(null)} className="ml-auto text-green-500 hover:text-green-700">×</button>
        </div>
      )}

      {/* Список токенов */}
      <div className="grid gap-4">
        {tokens.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <QrCode className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Нет активных QR токенов</h3>
            <p className="text-gray-600 mb-4">Создайте первый QR токен для очереди</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Создать токен
            </button>
          </div>
        ) : (
          tokens.map((token) => (
            <div key={token.token} className="bg-white border border-gray-200 rounded-lg p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center mb-2">
                    <QrCode className="h-5 w-5 text-blue-600 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">
                      {getDepartmentName(token.department)}
                    </h3>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-sm text-gray-600">Специалист</p>
                      <p className="font-medium">{getSpecialistName(token.specialist_id)}</p>
                    </div>
                    
                    <div>
                      <p className="text-sm text-gray-600">Создан</p>
                      <p className="font-medium">{formatDate(token.created_at)}</p>
                    </div>
                    
                    <div>
                      <p className="text-sm text-gray-600">Истекает</p>
                      <p className="font-medium">{formatDate(token.expires_at)}</p>
                    </div>
                    
                    <div>
                      <p className="text-sm text-gray-600">Статистика</p>
                      <p className="font-medium">
                        {token.successful_joins} из {token.sessions_count} присоединений
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center text-sm text-gray-600 mb-4">
                    <span className="font-mono bg-gray-100 px-2 py-1 rounded text-xs mr-2">
                      {token.token.substring(0, 16)}...
                    </span>
                  </div>
                </div>

                <div className="flex space-x-2 ml-4">
                  <button
                    onClick={() => {
                      setSelectedToken(token);
                      setShowQRModal(true);
                    }}
                    className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="Показать QR код"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                  
                  <button
                    onClick={() => copyToClipboard(token.qr_url)}
                    className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                    title="Копировать ссылку"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  
                  <button
                    onClick={() => downloadQR(token)}
                    className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="Скачать QR код"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                  
                  <button
                    onClick={() => deleteToken(token.token)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Деактивировать"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Модальное окно создания токена */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Создать QR токен</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Специалист
                </label>
                <select
                  value={createForm.specialist_id}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, specialist_id: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="">Выберите специалиста</option>
                  {specialists.map(specialist => (
                    <option key={specialist.id} value={specialist.id}>
                      {specialist.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Отделение
                </label>
                <select
                  value={createForm.department}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, department: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                >
                  <option value="">Выберите отделение</option>
                  {departments.map(dept => (
                    <option key={dept.value} value={dept.value}>
                      {dept.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Время жизни (часов)
                </label>
                <input
                  type="number"
                  min="1"
                  max="168"
                  value={createForm.expires_hours}
                  onChange={(e) => setCreateForm(prev => ({ ...prev, expires_hours: parseInt(e.target.value) }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="flex space-x-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={createToken}
                disabled={!createForm.specialist_id || !createForm.department}
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Создать
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно QR кода */}
      {showQRModal && selectedToken && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">QR код для очереди</h3>
            
            <div className="text-center mb-4">
              <img
                src={selectedToken.qr_code_base64}
                alt="QR Code"
                className="mx-auto mb-4 border border-gray-200 rounded-lg"
                style={{ maxWidth: '200px' }}
              />
              
              <p className="text-sm text-gray-600 mb-2">
                {getDepartmentName(selectedToken.department)}
              </p>
              <p className="text-xs text-gray-500 font-mono bg-gray-100 px-2 py-1 rounded">
                {selectedToken.qr_url}
              </p>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => setShowQRModal(false)}
                className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Закрыть
              </button>
              <button
                onClick={() => copyToClipboard(selectedToken.qr_url)}
                className="flex-1 bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors"
              >
                Копировать ссылку
              </button>
              <button
                onClick={() => downloadQR(selectedToken)}
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Скачать
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QRTokenManager;

