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
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSModal
} from '../ui/macos';
import { api } from '../../utils/api';

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
    type: '',
    license_key: '',
    vendor: '',
    status: 'active',
    purchase_date: '',
    expiry_date: '',
    cost: 0,
    seats: 1,
    description: ''
  });

  const statusOptions = [
    { value: 'active', label: 'Активная', color: 'success' },
    { value: 'expired', label: 'Истекла', color: 'error' },
    { value: 'expiring', label: 'Истекает', color: 'warning' },
    { value: 'suspended', label: 'Приостановлена', color: 'gray' }
  ];

  const typeOptions = [
    { value: 'software', label: 'Программное обеспечение' },
    { value: 'subscription', label: 'Подписка' },
    { value: 'perpetual', label: 'Бессрочная' },
    { value: 'trial', label: 'Пробная' },
    { value: 'academic', label: 'Академическая' },
    { value: 'enterprise', label: 'Корпоративная' }
  ];

  useEffect(() => {
    loadLicenses();
    loadStats();
  }, []);

  const loadLicenses = async () => {
    try {
      setLoading(true);
      const response = await api.get('/licenses');
      setLicenses(response.data.licenses || []);
    } catch (error) {
      console.error('Ошибка загрузки лицензий:', error);
      // Fallback данные
      setLicenses([
        {
          id: 1,
          name: 'Microsoft Office 365',
          type: 'subscription',
          license_key: 'MS-365-XXXX-XXXX-XXXX',
          vendor: 'Microsoft',
          status: 'active',
          purchase_date: '2023-01-01',
          expiry_date: '2024-12-31',
          cost: 120000,
          seats: 10,
          description: 'Корпоративная подписка Office 365'
        },
        {
          id: 2,
          name: 'Adobe Creative Suite',
          type: 'subscription',
          license_key: 'ADOBE-XXXX-XXXX-XXXX',
          vendor: 'Adobe',
          status: 'active',
          purchase_date: '2023-06-01',
          expiry_date: '2024-05-31',
          cost: 200000,
          seats: 5,
          description: 'Подписка на Adobe Creative Suite'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/licenses/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      setStats({
        total_licenses: 2,
        active_licenses: 2,
        expired_licenses: 0,
        expiring_licenses: 0
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      
      if (editingLicense) {
        await api.put(`/licenses/${editingLicense.id}`, formData);
        setMessage({ type: 'success', text: 'Лицензия обновлена' });
      } else {
        await api.post('/licenses', formData);
        setMessage({ type: 'success', text: 'Лицензия добавлена' });
      }
      
      setShowAddForm(false);
      setEditingLicense(null);
      resetForm();
      loadLicenses();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка сохранения лицензии' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (license) => {
    setFormData(license);
    setEditingLicense(license);
    setShowAddForm(true);
  };

  const handleDelete = async (licenseId) => {
    try {
      await api.delete(`/licenses/${licenseId}`);
      setMessage({ type: 'success', text: 'Лицензия удалена' });
      loadLicenses();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка удаления лицензии' });
    }
  };

  const toggleKeyVisibility = (licenseId) => {
    setShowKeys(prev => ({
      ...prev,
      [licenseId]: !prev[licenseId]
    }));
  };

  const copyKey = (key) => {
    navigator.clipboard.writeText(key);
    setMessage({ type: 'success', text: 'Ключ скопирован в буфер обмена' });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      type: '',
      license_key: '',
      vendor: '',
      status: 'active',
      purchase_date: '',
      expiry_date: '',
      cost: 0,
      seats: 1,
      description: ''
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

  const getTypeLabel = (type) => {
    const typeOption = typeOptions.find(t => t.value === type);
    return typeOption ? typeOption.label : type;
  };

  const isExpiringSoon = (expiryDate) => {
    const expiry = new Date(expiryDate);
    const now = new Date();
    const diffTime = expiry - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays <= 30 && diffDays > 0;
  };

  const filteredLicenses = licenses.filter(license => {
    const matchesSearch = license.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         license.vendor?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         license.license_key?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || license.status === statusFilter;
    const matchesType = typeFilter === 'all' || license.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', overflow: 'hidden' }}>
      {/* Заголовок и статистика */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0'
          }}>
            Управление лицензиями
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Учет и управление программными лицензиями
          </p>
        </div>
        {stats && (
          <div style={{ 
            display: 'flex', 
            gap: '24px',
            flexWrap: 'wrap'
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-accent-blue)',
                marginBottom: '4px'
              }}>
                {stats.total_licenses}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Всего лицензий
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-success)',
                marginBottom: '4px'
              }}>
                {stats.active_licenses}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Активных
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Сообщения */}
      {message.text && (
        <MacOSAlert
          type={message.type === 'success' ? 'success' : 'error'}
          title={message.type === 'success' ? 'Успешно' : 'Ошибка'}
          message={message.text}
        />
      )}

      {/* Фильтры и поиск */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '16px',
          flexWrap: 'wrap'
        }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск по названию, поставщику или ключу..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }}
            />
            <Search style={{ 
              position: 'absolute', 
              left: '12px', 
              top: '50%', 
              transform: 'translateY(-50%)', 
              color: 'var(--mac-text-tertiary)', 
              width: '16px', 
              height: '16px' 
            }} />
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <MacOSSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все статусы</option>
              {statusOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSSelect
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{ minWidth: '150px' }}
            >
              <option value="all">Все типы</option>
              {typeOptions.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </MacOSSelect>
            <MacOSButton
              onClick={() => setShowAddForm(true)}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '8px 16px'
              }}
            >
              <Plus style={{ width: '16px', height: '16px' }} />
              <span>Добавить лицензию</span>
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {showAddForm && (
        <MacOSCard style={{ padding: '24px', overflow: 'hidden' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            marginBottom: '16px' 
          }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              {editingLicense ? 'Редактировать лицензию' : 'Добавить лицензию'}
            </h3>
            <MacOSButton
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingLicense(null);
                resetForm();
              }}
              style={{ padding: '8px' }}
            >
              <X style={{ width: '16px', height: '16px' }} />
            </MacOSButton>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
              gap: '16px' 
            }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Название *
                </label>
                <MacOSInput
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  placeholder="Введите название лицензии"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Тип *
                </label>
                <MacOSSelect
                  required
                  value={formData.type}
                  onChange={(e) => setFormData({...formData, type: e.target.value})}
                >
                  <option value="">Выберите тип</option>
                  {typeOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Лицензионный ключ *
                </label>
                <MacOSInput
                  type="text"
                  required
                  value={formData.license_key}
                  onChange={(e) => setFormData({...formData, license_key: e.target.value})}
                  placeholder="Введите лицензионный ключ"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Поставщик
                </label>
                <MacOSInput
                  type="text"
                  value={formData.vendor}
                  onChange={(e) => setFormData({...formData, vendor: e.target.value})}
                  placeholder="Введите название поставщика"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Статус
                </label>
                <MacOSSelect
                  value={formData.status}
                  onChange={(e) => setFormData({...formData, status: e.target.value})}
                >
                  {statusOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </MacOSSelect>
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Дата покупки
                </label>
                <MacOSInput
                  type="date"
                  value={formData.purchase_date}
                  onChange={(e) => setFormData({...formData, purchase_date: e.target.value})}
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Дата истечения
                </label>
                <MacOSInput
                  type="date"
                  value={formData.expiry_date}
                  onChange={(e) => setFormData({...formData, expiry_date: e.target.value})}
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Стоимость (сум)
                </label>
                <MacOSInput
                  type="number"
                  value={formData.cost}
                  onChange={(e) => setFormData({...formData, cost: parseFloat(e.target.value)})}
                  placeholder="Введите стоимость"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Количество мест
                </label>
                <MacOSInput
                  type="number"
                  min="1"
                  value={formData.seats}
                  onChange={(e) => setFormData({...formData, seats: parseInt(e.target.value)})}
                  placeholder="Введите количество мест"
                />
              </div>
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={formData.description}
                onChange={(e) => setFormData({...formData, description: e.target.value})}
                placeholder="Введите описание лицензии"
                rows={3}
              />
            </div>

            <div style={{ 
              display: 'flex', 
              justifyContent: 'flex-end', 
              gap: '12px' 
            }}>
              <MacOSButton
                type="button"
                variant="outline"
                onClick={() => {
                  setShowAddForm(false);
                  setEditingLicense(null);
                  resetForm();
                }}
                disabled={saving}
              >
                Отмена
              </MacOSButton>
              <MacOSButton
                type="submit"
                disabled={saving}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none'
                }}
              >
                {saving ? (
                  <>
                    <RefreshCw style={{ 
                      width: '16px', 
                      height: '16px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save style={{ width: '16px', height: '16px' }} />
                    {editingLicense ? 'Обновить' : 'Добавить'}
                  </>
                )}
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      )}

      {/* Список лицензий */}
      {loading ? (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {[1, 2, 3].map(i => (
            <MacOSCard key={i} style={{ padding: '24px' }}>
              <MacOSLoadingSkeleton height="200px" />
            </MacOSCard>
          ))}
        </div>
      ) : filteredLicenses.length === 0 ? (
        <MacOSEmptyState
          icon={Key}
          title="Лицензии не найдены"
          description="Добавьте первую лицензию или измените фильтры поиска"
          action={
            <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить лицензию
            </MacOSButton>
          }
        />
      ) : (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px',
          overflow: 'hidden'
        }}>
          {filteredLicenses.map(license => (
            <MacOSCard key={license.id} style={{ padding: '24px' }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start', 
                marginBottom: '16px' 
              }}>
                <div>
                  <h3 style={{ 
                    fontSize: 'var(--mac-font-size-lg)', 
                    fontWeight: 'var(--mac-font-weight-semibold)', 
                    color: 'var(--mac-text-primary)',
                    margin: '0 0 4px 0'
                  }}>
                    {license.name}
                  </h3>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    {license.vendor} • {getTypeLabel(license.type)}
                  </p>
                </div>
                <MacOSBadge
                  variant={getStatusColor(license.status)}
                  text={getStatusLabel(license.status)}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Key style={{ width: '16px', height: '16px' }} />
                  <span style={{ 
                    fontFamily: 'monospace',
                    backgroundColor: 'var(--mac-bg-secondary)',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontSize: 'var(--mac-font-size-xs)'
                  }}>
                    {showKeys[license.id] ? license.license_key : '••••••••••••••••'}
                  </span>
                  <MacOSButton
                    variant="outline"
                    onClick={() => toggleKeyVisibility(license.id)}
                    style={{ padding: '2px 6px', minWidth: 'auto' }}
                  >
                    {showKeys[license.id] ? (
                      <EyeOff style={{ width: '12px', height: '12px' }} />
                    ) : (
                      <Eye style={{ width: '12px', height: '12px' }} />
                    )}
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => copyKey(license.license_key)}
                    style={{ padding: '2px 6px', minWidth: 'auto' }}
                  >
                    <Copy style={{ width: '12px', height: '12px' }} />
                  </MacOSButton>
                </div>
                {license.cost > 0 && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <DollarSign style={{ width: '16px', height: '16px' }} />
                    <span>{license.cost.toLocaleString()} сум</span>
                  </div>
                )}
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Shield style={{ width: '16px', height: '16px' }} />
                  <span>{license.seats} мест</span>
                </div>
                {license.expiry_date && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: isExpiringSoon(license.expiry_date) ? 'var(--mac-warning)' : 'var(--mac-text-secondary)'
                  }}>
                    <Calendar style={{ width: '16px', height: '16px' }} />
                    <span>Истекает: {new Date(license.expiry_date).toLocaleDateString()}</span>
                    {isExpiringSoon(license.expiry_date) && (
                      <AlertTriangle style={{ width: '14px', height: '14px' }} />
                    )}
                  </div>
                )}
              </div>

              {license.description && (
                <div style={{ marginBottom: '16px' }}>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0,
                    lineHeight: '1.4'
                  }}>
                    {license.description}
                  </p>
                </div>
              )}

              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end', 
                gap: '8px' 
              }}>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleEdit(license)}
                  style={{ padding: '6px 12px' }}
                >
                  <Edit style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleDelete(license.id)}
                  style={{ 
                    padding: '6px 12px',
                    color: 'var(--mac-error)',
                    borderColor: 'var(--mac-error)'
                  }}
                >
                  <Trash2 style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
              </div>
            </MacOSCard>
          ))}
        </div>
      )}
    </div>
  );
};

export default LicenseManagement;