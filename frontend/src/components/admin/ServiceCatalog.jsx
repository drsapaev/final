import React, { useState, useEffect } from 'react';
import { 
  Package, 
  Plus, 
  Search, 
  Filter, 
  Edit, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  Download,
  Upload,
  AlertCircle,
  CheckCircle,
  Heart,
  Scissors,
  Stethoscope,
  TestTube
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge,
  MacOSInput, 
  MacOSSelect,
  MacOSTable,
  MacOSEmptyState,
  MacOSLoadingSkeleton,
  MacOSAlert,
  MacOSModal,
  MacOSCheckbox
} from '../ui/macos';

const ServiceCatalog = () => {
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState([]);
  const [categories, setCategories] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSpecialty, setSelectedSpecialty] = useState('all');
  const [editingService, setEditingService] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Иконки специальностей
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    stomatology: Scissors,
    laboratory: TestTube,
    physiotherapy: Package // Можно заменить на более подходящую иконку
  };

  const specialtyColors = {
    cardiology: 'var(--mac-error)',
    dermatology: 'var(--mac-warning)',
    stomatology: 'var(--mac-info)',
    laboratory: 'var(--mac-success)',
    physiotherapy: 'var(--mac-accent)'
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Загружаем услуги, категории и врачей параллельно
      const [servicesRes, categoriesRes, doctorsRes] = await Promise.all([
        fetch('http://localhost:8000/api/v1/services', {
          // headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch('http://localhost:8000/api/v1/services/categories', {
          // headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch('http://localhost:8000/api/v1/services/admin/doctors', {
          // headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        })
      ]);

      if (servicesRes.ok) {
        const servicesData = await servicesRes.json();
        setServices(servicesData);
      }

      if (categoriesRes.ok) {
        const categoriesData = await categoriesRes.json();
        setCategories(categoriesData);
      }

      if (doctorsRes.ok) {
        const doctorsData = await doctorsRes.json();
        setDoctors(doctorsData);
      }

    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки данных' });
    } finally {
      setLoading(false);
    }
  };

  const filteredServices = services.filter(service => {
    const matchesSearch = service.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || service.category_id === parseInt(selectedCategory);
    const matchesSpecialty = selectedSpecialty === 'all' || 
      categories.find(cat => cat.id === service.category_id)?.specialty === selectedSpecialty;
    
    return matchesSearch && matchesCategory && matchesSpecialty;
  });

  const handleSaveService = async (serviceData) => {
    try {
      console.log('🔄 Отправляем данные услуги:', serviceData);
      
      const method = editingService ? 'PUT' : 'POST';
      const url = editingService 
        ? `http://localhost:8000/api/v1/services/${editingService.id}`
        : 'http://localhost:8000/api/v1/services';

      const response = await fetch(url, {
        method,
        headers: {
          // 'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(serviceData)
      });

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: editingService ? 'Услуга обновлена' : 'Услуга создана' 
        });
        setEditingService(null);
        setShowAddForm(false);
        await loadData();
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('❌ Ошибка API:', response.status, errorData);
        throw new Error(`Ошибка сохранения услуги: ${response.status}`);
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения услуги' });
    }
  };

  const handleDeleteService = async (serviceId) => {
    if (!confirm('Удалить услугу?')) return;

    try {
      const response = await fetch(`http://localhost:8000/api/v1/services/${serviceId}`, {
        method: 'DELETE',
        headers: {
          // 'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Услуга удалена' });
        await loadData();
      } else {
        throw new Error('Ошибка удаления услуги');
      }
    } catch (error) {
      console.error('Ошибка удаления:', error);
      setMessage({ type: 'error', text: 'Ошибка удаления услуги' });
    }
  };

  const getCategoryName = (categoryId) => {
    const category = categories.find(cat => cat.id === categoryId);
    return category?.name_ru || 'Без категории';
  };

  const getCategorySpecialty = (categoryId) => {
    const category = categories.find(cat => cat.id === categoryId);
    return category?.specialty;
  };

  const getSpecialtyIcon = (specialty) => {
    const IconComponent = specialtyIcons[specialty] || Package;
    return IconComponent;
  };

  if (loading) {
    return (
      <MacOSCard 
        variant="default"
        style={{ padding: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <RefreshCw style={{ animation: 'spin 1s linear infinite', marginRight: '8px' }} size={20} />
          <span style={{ color: 'var(--mac-text-primary)' }}>Загрузка справочника услуг...</span>
        </div>
      </MacOSCard>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Справочник услуг
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            margin: '4px 0 0 0',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление услугами и ценами по специальностям
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <MacOSButton variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} style={{ marginRight: '8px' }} />
            Обновить
          </MacOSButton>
          <MacOSButton onClick={() => setShowAddForm(true)}>
            <Plus size={16} style={{ marginRight: '8px' }} />
            Добавить услугу
          </MacOSButton>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <MacOSAlert
          type={message.type === 'success' ? 'success' : 'error'}
          title={message.text}
          onClose={() => setMessage({ type: '', text: '' })}
        />
      )}

      {/* Фильтры */}
      <MacOSCard 
        variant="default"
        style={{ padding: '24px' }}
      >
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Поиск по названию
            </label>
            <MacOSInput
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Введите название услуги..."
              icon={Search}
              iconPosition="left"
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Специальность
            </label>
            <MacOSSelect
              value={selectedSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value)}
              options={[
                { value: 'all', label: 'Все специальности' },
                { value: 'cardiology', label: 'Кардиология' },
                { value: 'dermatology', label: 'Дерматология' },
                { value: 'stomatology', label: 'Стоматология' },
                { value: 'laboratory', label: 'Лаборатория' },
                { value: 'physiotherapy', label: 'Физиотерапия' }
              ]}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Категория
            </label>
            <MacOSSelect
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              options={[
                { value: 'all', label: 'Все категории' },
                ...categories.map(category => ({
                  value: category.id,
                  label: category.name_ru
                }))
              ]}
            />
          </div>
        </div>
      </MacOSCard>

      {/* Статистика */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px' 
      }}>
        <MacOSCard 
          variant="default"
          style={{ padding: '24px' }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-info)',
              margin: 0
            }}>
              {services.length}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)',
              margin: '4px 0 0 0'
            }}>
              Всего услуг
            </div>
          </div>
        </MacOSCard>
        <MacOSCard 
          variant="default"
          style={{ padding: '24px' }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-success)',
              margin: 0
            }}>
              {services.filter(s => s.active).length}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)',
              margin: '4px 0 0 0'
            }}>
              Активных
            </div>
          </div>
        </MacOSCard>
        <MacOSCard 
          variant="default"
          style={{ padding: '24px' }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-warning)',
              margin: 0
            }}>
              {categories.length}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)',
              margin: '4px 0 0 0'
            }}>
              Категорий
            </div>
          </div>
        </MacOSCard>
        <MacOSCard 
          variant="default"
          style={{ padding: '24px' }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-accent)',
              margin: 0
            }}>
              {filteredServices.length}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)',
              margin: '4px 0 0 0'
            }}>
              Найдено
            </div>
          </div>
        </MacOSCard>
      </div>

      {/* Таблица услуг */}
      <MacOSCard 
        variant="default"
        style={{ padding: '0' }}
      >
        <MacOSTable
          columns={[
            { key: 'service', title: 'Услуга', width: '25%' },
            { key: 'category', title: 'Категория', width: '15%' },
            { key: 'price', title: 'Цена', width: '15%' },
            { key: 'duration', title: 'Длительность', width: '12%' },
            { key: 'doctor', title: 'Врач', width: '15%' },
            { key: 'status', title: 'Статус', width: '10%' },
            { key: 'actions', title: 'Действия', width: '8%' }
          ]}
          data={filteredServices.map(service => {
            const specialty = getCategorySpecialty(service.category_id);
            const SpecialtyIcon = getSpecialtyIcon(specialty);
            const doctor = doctors.find(d => d.id === service.doctor_id);
            
            return {
              id: service.id,
              service: (
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <SpecialtyIcon 
                    size={20} 
                    style={{ 
                      marginRight: '12px', 
                      color: specialtyColors[specialty] || 'var(--mac-text-tertiary)' 
                    }} 
                  />
                  <div>
                    <div style={{ 
                      fontSize: '14px', 
                      fontWeight: '500', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      {service.name}
                    </div>
                    {service.code && (
                      <div style={{ 
                        fontSize: '14px', 
                        color: 'var(--mac-text-secondary)',
                        margin: '2px 0 0 0'
                      }}>
                        Код: {service.code}
                      </div>
                    )}
                  </div>
                </div>
              ),
              category: (
                <MacOSBadge variant="outline">
                  {getCategoryName(service.category_id)}
                </MacOSBadge>
              ),
              price: (
                <div style={{ 
                  fontSize: '14px', 
                  fontWeight: '500', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  {service.price ? `${service.price.toLocaleString()} ${service.currency || 'UZS'}` : 'Не указана'}
                </div>
              ),
              duration: (
                <div style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  {service.duration_minutes ? `${service.duration_minutes} мин` : '—'}
                </div>
              ),
              doctor: (
                <div style={{ 
                  fontSize: '14px', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  {doctor ? doctor.user?.full_name || `Врач #${doctor.id}` : '—'}
                </div>
              ),
              status: (
                <MacOSBadge variant={service.active ? 'success' : 'error'}>
                  {service.active ? 'Активна' : 'Неактивна'}
                </MacOSBadge>
              ),
              actions: (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <MacOSButton
                    size="sm"
                    variant="outline"
                    onClick={() => setEditingService(service)}
                    style={{ 
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Редактировать"
                  >
                    <Edit size={14} />
                  </MacOSButton>
                  <MacOSButton
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeleteService(service.id)}
                    style={{ 
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--mac-error)',
                      borderColor: 'var(--mac-error)'
                    }}
                    title="Удалить"
                  >
                    <Trash2 size={14} />
                  </MacOSButton>
                </div>
              )
            };
          })}
          emptyState={{
            type: 'package',
            title: 'Услуги не найдены',
            description: searchTerm || selectedCategory !== 'all' || selectedSpecialty !== 'all'
              ? 'Попробуйте изменить критерии поиска'
              : 'Добавьте первую услугу в справочник',
            action: (
              <MacOSButton onClick={() => setShowAddForm(true)}>
                <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Добавить услугу
              </MacOSButton>
            )
          }}
        />
      </MacOSCard>

      {/* Форма добавления/редактирования */}
      {(showAddForm || editingService) && (
        <ServiceForm
          service={editingService}
          categories={categories}
          doctors={doctors}
          onSave={handleSaveService}
          onCancel={() => {
            setShowAddForm(false);
            setEditingService(null);
          }}
        />
      )}
    </div>
  );
};

// Компонент формы услуги
const ServiceForm = ({ service, categories, doctors, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: service?.name || '',
    code: service?.code || '',
    category_id: service?.category_id || '',
    price: service?.price || '',
    currency: service?.currency || 'UZS',
    duration_minutes: service?.duration_minutes || 30,
    doctor_id: service?.doctor_id || '',
    active: service?.active !== undefined ? service.active : true,
    // ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    category_code: service?.category_code || '',
    service_code: service?.service_code || '',
    requires_doctor: service?.requires_doctor || false,
    queue_tag: service?.queue_tag || '',
    is_consultation: service?.is_consultation || false,
    allow_doctor_price_override: service?.allow_doctor_price_override || false
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Валидация
    if (!formData.name.trim()) {
      alert('Введите название услуги');
      return;
    }

    // Подготавливаем данные для API
    const apiData = {
      ...formData,
      price: formData.price ? parseFloat(formData.price) : null,
      category_id: formData.category_id ? parseInt(formData.category_id) : null,
      doctor_id: formData.doctor_id ? parseInt(formData.doctor_id) : null,
      duration_minutes: parseInt(formData.duration_minutes) || 30
    };
    
    // Убираем пустые строки
    Object.keys(apiData).forEach(key => {
      if (apiData[key] === '' || apiData[key] === 'null') {
        apiData[key] = null;
      }
    });
    
    console.log('📝 Подготовленные данные для API:', apiData);
    onSave(apiData);
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <MacOSCard 
      variant="default"
      style={{ padding: '24px' }}
    >
      <h3 style={{ 
        fontSize: '18px', 
        fontWeight: '500', 
        color: 'var(--mac-text-primary)',
        marginBottom: '16px',
        margin: '0 0 16px 0'
      }}>
        {service ? 'Редактирование услуги' : 'Добавление услуги'}
      </h3>
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Название услуги *
            </label>
            <MacOSInput
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              required
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Код услуги
            </label>
            <MacOSInput
              type="text"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Категория *
            </label>
            <MacOSSelect
              value={formData.category_id}
              onChange={(e) => handleChange('category_id', e.target.value)}
              options={[
                { value: '', label: 'Выберите категорию' },
                ...categories.map(category => ({
                  value: category.id,
                  label: `${category.name_ru} (${category.specialty})`
                }))
              ]}
              required
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Цена
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <MacOSInput
                type="number"
                value={formData.price}
                onChange={(e) => handleChange('price', parseFloat(e.target.value) || '')}
                min="0"
                step="0.01"
                style={{ flex: 1 }}
              />
              <MacOSSelect
                value={formData.currency}
                onChange={(e) => handleChange('currency', e.target.value)}
                options={[
                  { value: 'UZS', label: 'UZS' },
                  { value: 'USD', label: 'USD' },
                  { value: 'RUB', label: 'RUB' }
                ]}
                style={{ minWidth: '80px' }}
              />
            </div>
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Длительность (мин)
            </label>
            <MacOSInput
              type="number"
              value={formData.duration_minutes}
              onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value) || 30)}
              min="5"
              step="5"
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: '14px', 
              fontWeight: '500', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Врач (опционально)
            </label>
            <MacOSSelect
              value={formData.doctor_id}
              onChange={(e) => handleChange('doctor_id', e.target.value)}
              options={[
                { value: '', label: 'Все врачи' },
                ...doctors.map(doctor => ({
                  value: doctor.id,
                  label: `${doctor.user?.full_name || `Врач #${doctor.id}`} (${doctor.specialty})`
                }))
              ]}
            />
          </div>
        </div>

        {/* ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ */}
        <div style={{ 
          borderTop: '1px solid var(--mac-border)', 
          paddingTop: '16px' 
        }}>
          <h4 style={{ 
            fontSize: '16px', 
            fontWeight: '500', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '16px',
            margin: '0 0 16px 0'
          }}>
            Настройки для мастера регистрации
          </h4>
          
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
            gap: '16px' 
          }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: '14px', 
                fontWeight: '500', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Код категории (K/D/C/L/S/O)
              </label>
              <MacOSSelect
                value={formData.category_code}
                onChange={(e) => handleChange('category_code', e.target.value)}
                options={[
                  { value: '', label: 'Выберите категорию' },
                  { value: 'K', label: 'K - Кардиология' },
                  { value: 'D', label: 'D - Дерматология' },
                  { value: 'C', label: 'C - Косметология' },
                  { value: 'L', label: 'L - Лабораторные анализы' },
                  { value: 'S', label: 'S - Стоматология' },
                  { value: 'P', label: 'P - Физиотерапия' },
                  { value: 'O', label: 'O - Другие услуги' }
                ]}
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: '14px', 
                fontWeight: '500', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Код услуги (например: K01, L002)
              </label>
              <MacOSInput
                type="text"
                value={formData.service_code}
                onChange={(e) => handleChange('service_code', e.target.value)}
                placeholder="K01"
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: '14px', 
                fontWeight: '500', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Тег очереди
              </label>
              <MacOSSelect
                value={formData.queue_tag}
                onChange={(e) => handleChange('queue_tag', e.target.value)}
                options={[
                  { value: '', label: 'Без очереди' },
                  { value: 'ecg', label: 'ECG (отдельная очередь)' },
                  { value: 'cardiology_common', label: 'Кардиология (общая)' },
                  { value: 'stomatology', label: 'Стоматология' },
                  { value: 'dermatology', label: 'Дерматология' },
                  { value: 'cosmetology', label: 'Косметология' },
                  { value: 'lab', label: 'Лаборатория' },
                  { value: 'physiotherapy', label: 'Физиотерапия' }
                ]}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <MacOSCheckbox
                id="requires_doctor"
                checked={formData.requires_doctor}
                onChange={(e) => handleChange('requires_doctor', e.target.checked)}
                label="Требует врача"
              />

              <MacOSCheckbox
                id="is_consultation"
                checked={formData.is_consultation}
                onChange={(e) => handleChange('is_consultation', e.target.checked)}
                label="Это консультация"
              />

              <MacOSCheckbox
                id="allow_doctor_price_override"
                checked={formData.allow_doctor_price_override}
                onChange={(e) => handleChange('allow_doctor_price_override', e.target.checked)}
                label="Врач может изменить цену"
              />
            </div>
          </div>

          <div style={{ 
            backgroundColor: 'var(--mac-info-bg)', 
            padding: '12px', 
            borderRadius: 'var(--mac-radius-md)', 
            marginTop: '16px' 
          }}>
            <p style={{ 
              fontSize: '14px', 
              color: 'var(--mac-info)',
              margin: 0
            }}>
              <strong>Подсказка:</strong> Только ЭхоКГ (кардиолог), Рентгенография зуб (стоматолог) и сложные дерматологические процедуры требуют врача.
              Консультации участвуют в расчёте льгот и повторных визитов.
              Физиотерапевтические процедуры могут выполняться медицинским персоналом среднего звена.
            </p>
          </div>
        </div>

        <MacOSCheckbox
          id="active"
          checked={formData.active}
          onChange={(e) => handleChange('active', e.target.checked)}
          label="Услуга активна"
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <MacOSButton type="button" variant="outline" onClick={onCancel}>
            <X size={16} style={{ marginRight: '8px' }} />
            Отменить
          </MacOSButton>
          <MacOSButton type="submit">
            <Save size={16} style={{ marginRight: '8px' }} />
            Сохранить
          </MacOSButton>
        </div>
      </form>
    </MacOSCard>
  );
};

export default ServiceCatalog;

