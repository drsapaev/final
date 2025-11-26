import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  MapPin,
  Phone,
  Mail,
  Users
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert
} from '../ui/macos';
import { api } from '../../api/client';

const BranchManagement = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [branches, setBranches] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingBranch, setEditingBranch] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [stats, setStats] = useState(null);

  // Форма филиала
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    address: '',
    phone: '',
    email: '',
    status: 'active',
    capacity: 50,
    services_available: ['cardiology', 'dermatology', 'stomatology']
  });

  const statusOptions = [
    { value: 'active', label: 'Активный', color: 'success' },
    { value: 'inactive', label: 'Неактивный', color: 'error' },
    { value: 'maintenance', label: 'Обслуживание', color: 'warning' }
  ];

  const specialtyOptions = [
    { value: 'cardiology', label: 'Кардиология' },
    { value: 'dermatology', label: 'Дерматология' },
    { value: 'stomatology', label: 'Стоматология' },
    { value: 'neurology', label: 'Неврология' },
    { value: 'orthopedics', label: 'Ортопедия' },
    { value: 'pediatrics', label: 'Педиатрия' },
    { value: 'gynecology', label: 'Гинекология' },
    { value: 'urology', label: 'Урология' }
  ];

  useEffect(() => {
    loadBranches();
    loadStats();
  }, []);

  const loadBranches = async () => {
    try {
      setLoading(true);
      const response = await api.get('/branches');
      setBranches(response.data.branches || []);
    } catch (error) {
      console.error('Ошибка загрузки филиалов:', error);
      // Fallback данные
      setBranches([
        {
          id: 1,
          name: 'Центральный филиал',
          code: 'CEN001',
          address: 'ул. Навои, 1',
          phone: '+998 71 123-45-67',
          email: 'central@clinic.uz',
          status: 'active',
          capacity: 100,
          services_available: ['cardiology', 'dermatology', 'stomatology']
        },
        {
          id: 2,
          name: 'Филиал Чиланзар',
          code: 'CHI002',
          address: 'ул. Чиланзар, 15',
          phone: '+998 71 234-56-78',
          email: 'chilanzar@clinic.uz',
          status: 'active',
          capacity: 80,
          services_available: ['cardiology', 'neurology']
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/branches/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      // Fallback данные
      setStats({
        total_branches: 2,
        active_branches: 2,
        inactive_branches: 0,
        maintenance_branches: 0
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      
      if (editingBranch) {
        await api.put(`/branches/${editingBranch.id}`, formData);
        setMessage({ type: 'success', text: 'Филиал обновлен' });
      } else {
        await api.post('/branches', formData);
        setMessage({ type: 'success', text: 'Филиал создан' });
      }
      
      setShowAddForm(false);
      setEditingBranch(null);
      resetForm();
      loadBranches();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка сохранения филиала' });
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (branch) => {
    setFormData({
      ...branch,
      services_available: branch.services_available || []
    });
    setEditingBranch(branch);
    setShowAddForm(true);
  };

  const handleDelete = async (branchId) => {
    try {
      await api.delete(`/branches/${branchId}`);
      setMessage({ type: 'success', text: 'Филиал удален' });
      loadBranches();
      loadStats();
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка удаления филиала' });
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      code: '',
      address: '',
      phone: '',
      email: '',
      status: 'active',
      capacity: 50,
      services_available: ['cardiology', 'dermatology', 'stomatology']
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

  const filteredBranches = branches.filter(branch => {
    const matchesSearch = branch.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         branch.address?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         branch.code.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || branch.status === statusFilter;
    return matchesSearch && matchesStatus;
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
            Управление филиалами
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Создание и управление филиалами клиники
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
                {stats.total_branches}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Всего филиалов
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-success)',
                marginBottom: '4px'
              }}>
                {stats.active_branches}
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
              placeholder="Поиск по названию, адресу или коду..."
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
              <span>Добавить филиал</span>
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
              {editingBranch ? 'Редактировать филиал' : 'Добавить филиал'}
            </h3>
            <MacOSButton
              variant="outline"
              onClick={() => {
                setShowAddForm(false);
                setEditingBranch(null);
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
                  Название филиала *
                </label>
                <MacOSInput
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Введите название филиала"
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
                  Код филиала *
                </label>
                <MacOSInput
                  type="text"
                  required
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  placeholder="Введите код филиала"
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
                  Адрес
                </label>
                <MacOSInput
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  placeholder="Введите адрес филиала"
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
                  Телефон
                </label>
                <MacOSInput
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="Введите номер телефона"
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
                  Email
                </label>
                <MacOSInput
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="Введите email филиала"
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
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
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
                  Вместимость
                </label>
                <MacOSInput
                  type="number"
                  value={formData.capacity}
                  onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) })}
                  placeholder="Введите вместимость"
                />
              </div>
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Доступные услуги
              </label>
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                gap: '8px' 
              }}>
                {specialtyOptions.map(specialty => (
                  <label key={specialty.value} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    <MacOSCheckbox
                      checked={formData.services_available.includes(specialty.value)}
                      onChange={(checked) => {
                        if (checked) {
                          setFormData({
                            ...formData,
                            services_available: [...formData.services_available, specialty.value]
                          });
                        } else {
                          setFormData({
                            ...formData,
                            services_available: formData.services_available.filter(s => s !== specialty.value)
                          });
                        }
                      }}
                    />
                    <span>{specialty.label}</span>
                  </label>
                ))}
              </div>
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
                  setEditingBranch(null);
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
                    {editingBranch ? 'Обновить' : 'Создать'}
                  </>
                )}
              </MacOSButton>
            </div>
          </form>
        </MacOSCard>
      )}

      {/* Список филиалов */}
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
      ) : filteredBranches.length === 0 ? (
        <MacOSEmptyState
          icon={Building2}
          title="Филиалы не найдены"
          description="Создайте первый филиал или измените фильтры поиска"
          action={
            <MacOSButton onClick={() => setShowAddForm(true)} variant="primary">
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить филиал
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
          {filteredBranches.map(branch => (
            <MacOSCard key={branch.id} style={{ padding: '24px' }}>
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
                    {branch.name}
                  </h3>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    {branch.code}
                  </p>
                </div>
                <MacOSBadge
                  variant={getStatusColor(branch.status)}
                  text={getStatusLabel(branch.status)}
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                {branch.address && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <MapPin style={{ width: '16px', height: '16px' }} />
                    <span>{branch.address}</span>
                  </div>
                )}
                {branch.phone && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <Phone style={{ width: '16px', height: '16px' }} />
                    <span>{branch.phone}</span>
                  </div>
                )}
                {branch.email && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    <Mail style={{ width: '16px', height: '16px' }} />
                    <span>{branch.email}</span>
                  </div>
                )}
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  <Users style={{ width: '16px', height: '16px' }} />
                  <span>Вместимость: {branch.capacity}</span>
                </div>
              </div>

              {branch.services_available && branch.services_available.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Услуги:
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {branch.services_available.map(service => {
                      const specialty = specialtyOptions.find(s => s.value === service);
                      return specialty ? (
                        <MacOSBadge
                          key={service}
                          variant="outline"
                          text={specialty.label}
                          style={{ fontSize: 'var(--mac-font-size-xs)' }}
                        />
                      ) : null;
                    })}
                  </div>
                </div>
              )}

              <div style={{ 
                display: 'flex', 
                justifyContent: 'flex-end', 
                gap: '8px' 
              }}>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleEdit(branch)}
                  style={{ padding: '6px 12px' }}
                >
                  <Edit style={{ width: '16px', height: '16px' }} />
                </MacOSButton>
                <MacOSButton
                  variant="outline"
                  onClick={() => handleDelete(branch.id)}
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

export default BranchManagement;
