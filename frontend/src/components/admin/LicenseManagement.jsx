import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Plus, 
  Search, 
  Filter, 
  Edit, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  Calendar,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Clock,
  Shield,
  Copy,
  Eye,
  EyeOff
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

const LicenseManagement = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [licenses, setLicenses] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingLicense, setEditingLicense] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);
  const [showKeys, setShowKeys] = useState({});

  // Форма лицензии
  const [formData, setFormData] = useState({
    name: '',
    license_type: 'software',
    license_key: '',
    status: 'active',
    issued_by: '',
    issued_date: '',
    expires_date: '',
    renewal_date: '',
    cost: '',
    features: [],
    restrictions: [],
    notes: ''
  });

  const statusOptions = [
    { value: 'active', label: 'Активная', color: 'green' },
    { value: 'expired', label: 'Истекла', color: 'red' },
    { value: 'suspended', label: 'Приостановлена', color: 'yellow' },
    { value: 'pending', label: 'Ожидает', color: 'blue' }
  ];

  const typeOptions = [
    { value: 'software', label: 'Программное обеспечение', icon: '💻' },
    { value: 'medical', label: 'Медицинская лицензия', icon: '🏥' },
    { value: 'business', label: 'Бизнес лицензия', icon: '🏢' },
    { value: 'data', label: 'Лицензия на данные', icon: '📊' }
  ];

  const featureOptions = [
    'basic', 'advanced', 'premium', 'enterprise',
    'analytics', 'reporting', 'integration', 'api',
    'support', 'training', 'customization', 'backup'
  ];

  const restrictionOptions = [
    'single_user', 'multi_user', 'concurrent_users',
    'time_limited', 'feature_limited', 'usage_limited',
    'no_commercial', 'no_modification', 'no_distribution'
  ];

  useEffect(() => {
    loadLicenses();
    loadStats();
  }, []);

  const loadLicenses = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (searchTerm) params.append('search', searchTerm);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (typeFilter !== 'all') params.append('license_type', typeFilter);
      
      const response = await fetch(`/api/v1/clinic/licenses?${params}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setLicenses(data);
      } else {
        throw new Error('Ошибка загрузки лицензий');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/clinic/stats', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      const url = editingLicense 
        ? `/api/v1/clinic/licenses/${editingLicense.id}`
        : '/api/v1/clinic/licenses';
      
      const method = editingLicense ? 'PUT' : 'POST';
      
      const submitData = {
        ...formData,
        cost: formData.cost ? parseFloat(formData.cost) : null,
        issued_date: formData.issued_date || null,
        expires_date: formData.expires_date || null,
        renewal_date: formData.renewal_date || null
      };
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(submitData)
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: editingLicense ? 'Лицензия обновлена' : 'Лицензия создана' });
        setShowAddForm(false);
        setEditingLicense(null);
        resetForm();
        loadLicenses();
        loadStats();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка сохранения');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (license) => {
    setEditingLicense(license);
    setFormData({
      name: license.name,
      license_type: license.license_type,
      license_key: license.license_key,
      status: license.status,
      issued_by: license.issued_by || '',
      issued_date: license.issued_date || '',
      expires_date: license.expires_date || '',
      renewal_date: license.renewal_date || '',
      cost: license.cost || '',
      features: license.features || [],
      restrictions: license.restrictions || [],
      notes: license.notes || ''
    });
    setShowAddForm(true);
  };

  const handleDelete = async (licenseId) => {
    if (!window.confirm('Вы уверены, что хотите удалить эту лицензию?')) return;
    
    try {
      const response = await fetch(`/api/v1/clinic/licenses/${licenseId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: 'Лицензия удалена' });
        loadLicenses();
        loadStats();
      } else {
        throw new Error('Ошибка удаления лицензии');
      }
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      license_type: 'software',
      license_key: '',
      status: 'active',
      issued_by: '',
      issued_date: '',
      expires_date: '',
      renewal_date: '',
      cost: '',
      features: [],
      restrictions: [],
      notes: ''
    });
  };

  const getStatusColor = (status) => {
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.color : 'gray';
  };

  const getStatusLabel = (status) => {
    const statusOption = statusOptions.find(s => s.value === status);
    return statusOption ? statusOption.label : status;
  };

  const getTypeIcon = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.icon : '🔑';
  };

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const isExpiringSoon = (license) => {
    if (!license.expires_date) return false;
    const expiresDate = new Date(license.expires_date);
    const now = new Date();
    const daysUntilExpiry = Math.ceil((expiresDate - now) / (1000 * 60 * 60 * 24));
    return daysUntilExpiry <= 30 && daysUntilExpiry >= 0;
  };

  const isExpired = (license) => {
    if (!license.expires_date) return false;
    const expiresDate = new Date(license.expires_date);
    const now = new Date();
    return expiresDate < now;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setMessage({ type: 'success', text: 'Ключ скопирован в буфер обмена' });
  };

  const toggleKeyVisibility = (licenseId) => {
    setShowKeys(prev => ({
      ...prev,
      [licenseId]: !prev[licenseId]
    }));
  };

  const filteredLicenses = licenses.filter(license => {
    const matchesSearch = license.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         license.license_key.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         license.issued_by?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || license.status === statusFilter;
    const matchesType = typeFilter === 'all' || license.license_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div className="space-y-6">
      {/* Заголовок и статистика */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Управление лицензиями</h2>
          <p className="text-gray-600">Управление лицензиями и активациями</p>
        </div>
        {stats && (
          <div className="flex space-x-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.total_licenses}</div>
              <div className="text-sm text-gray-600">Всего лицензий</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.active_licenses}</div>
              <div className="text-sm text-gray-600">Активных</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{stats.expired_licenses}</div>
              <div className="text-sm text-gray-600">Истекших</div>
            </div>
          </div>
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`p-4 rounded-lg flex items-center space-x-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Фильтры и поиск */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Поиск лицензий..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все статусы</option>
            {statusOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все типы</option>
            {typeOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            onClick={() => setShowAddForm(true)}
            className="flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить лицензию</span>
          </Button>
        </div>
      </Card>

      {/* Форма добавления/редактирования */}
      {showAddForm && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">
              {editingLicense ? 'Редактировать лицензию' : 'Добавить лицензию'}
            </h3>
            <Button
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingLicense(null);
                resetForm();
              }}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название лицензии *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип лицензии *
                </label>
                <select
                  required
                  value={formData.license_type}
                  onChange={(e) => setFormData({...formData, license_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Ключ лицензии *
                </label>
                <input
                  type="text"
                  required
                  value={formData.license_key}
                  onChange={(e) => setFormData({...formData, license_key: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Статус
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({...formData, status: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {statusOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Выдано
                </label>
                <input
                  type="text"
                  value={formData.issued_by}
                  onChange={(e) => setFormData({...formData, issued_by: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дата выдачи
                </label>
                <input
                  type="date"
                  value={formData.issued_date}
                  onChange={(e) => setFormData({...formData, issued_date: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дата истечения
                </label>
                <input
                  type="date"
                  value={formData.expires_date}
                  onChange={(e) => setFormData({...formData, expires_date: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дата продления
                </label>
                <input
                  type="date"
                  value={formData.renewal_date}
                  onChange={(e) => setFormData({...formData, renewal_date: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Стоимость
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.cost}
                  onChange={(e) => setFormData({...formData, cost: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Функции
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {featureOptions.map(feature => (
                  <label key={feature} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.features.includes(feature)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            features: [...formData.features, feature]
                          });
                        } else {
                          setFormData({
                            ...formData,
                            features: formData.features.filter(f => f !== feature)
                          });
                        }
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{feature}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Ограничения
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {restrictionOptions.map(restriction => (
                  <label key={restriction} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.restrictions.includes(restriction)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            restrictions: [...formData.restrictions, restriction]
                          });
                        } else {
                          setFormData({
                            ...formData,
                            restrictions: formData.restrictions.filter(r => r !== restriction)
                          });
                        }
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{restriction}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Примечания
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex justify-end space-x-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingLicense(null);
                  resetForm();
                }}
              >
                Отмена
              </Button>
              <Button
                type="submit"
                disabled={saving}
                className="flex items-center space-x-2"
              >
                {saving ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>{saving ? 'Сохранение...' : 'Сохранить'}</span>
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Список лицензий */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="p-6">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
                <div className="h-3 bg-gray-200 rounded w-full mb-2"></div>
                <div className="h-3 bg-gray-200 rounded w-2/3"></div>
              </div>
            </Card>
          ))
        ) : filteredLicenses.length === 0 ? (
          <div className="col-span-full text-center py-12">
            <Key className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Лицензии не найдены</h3>
            <p className="text-gray-600">Добавьте первую лицензию или измените фильтры поиска</p>
          </div>
        ) : (
          filteredLicenses.map(license => (
            <Card key={license.id} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-2">
                  <span className="text-2xl">{getTypeIcon(license.license_type)}</span>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{license.name}</h3>
                    <p className="text-sm text-gray-600">{getTypeLabel(license.license_type)}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end space-y-1">
                  <Badge color={getStatusColor(license.status)}>
                    {getStatusLabel(license.status)}
                  </Badge>
                  {isExpiringSoon(license) && (
                    <Badge color="yellow">Истекает скоро</Badge>
                  )}
                  {isExpired(license) && (
                    <Badge color="red">Истекла</Badge>
                  )}
                </div>
              </div>

              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">Ключ лицензии:</span>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-mono text-gray-600">
                      {showKeys[license.id] ? license.license_key : '••••••••••••••••'}
                    </span>
                    <button
                      onClick={() => toggleKeyVisibility(license.id)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      {showKeys[license.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => copyToClipboard(license.license_key)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                
                {license.issued_by && (
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">Выдано:</span> {license.issued_by}
                  </div>
                )}
                
                {license.issued_date && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Calendar className="w-4 h-4" />
                    <span>Выдана: {new Date(license.issued_date).toLocaleDateString()}</span>
                  </div>
                )}
                
                {license.expires_date && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Clock className="w-4 h-4" />
                    <span>Истекает: {new Date(license.expires_date).toLocaleDateString()}</span>
                  </div>
                )}
                
                {license.cost && (
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <DollarSign className="w-4 h-4" />
                    <span>{parseFloat(license.cost).toLocaleString()} сум</span>
                  </div>
                )}
              </div>

              {license.features && license.features.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Функции:</p>
                  <div className="flex flex-wrap gap-1">
                    {license.features.map(feature => (
                      <Badge key={feature} variant="outline" className="text-xs">
                        {feature}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {license.restrictions && license.restrictions.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Ограничения:</p>
                  <div className="flex flex-wrap gap-1">
                    {license.restrictions.map(restriction => (
                      <Badge key={restriction} variant="outline" className="text-xs text-red-600">
                        {restriction}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {license.notes && (
                <div className="mb-4">
                  <p className="text-sm text-gray-600">{license.notes}</p>
                </div>
              )}

              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEdit(license)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(license.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default LicenseManagement;

