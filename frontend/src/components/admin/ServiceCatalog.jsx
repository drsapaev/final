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
import { Card, Button, Badge } from '../ui/native';

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
    laboratory: TestTube
  };

  const specialtyColors = {
    cardiology: 'text-red-600',
    dermatology: 'text-orange-600',
    stomatology: 'text-blue-600', 
    laboratory: 'text-green-600'
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
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка справочника услуг...</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Справочник услуг
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Управление услугами и ценами по специальностям
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} className="mr-2" />
            Добавить услугу
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Фильтры */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Search size={16} className="inline mr-1" />
              Поиск по названию
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="Введите название услуги..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Filter size={16} className="inline mr-1" />
              Специальность
            </label>
            <select
              value={selectedSpecialty}
              onChange={(e) => setSelectedSpecialty(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">Все специальности</option>
              <option value="cardiology">Кардиология</option>
              <option value="dermatology">Дерматология</option>
              <option value="stomatology">Стоматология</option>
              <option value="laboratory">Лаборатория</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Категория
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">Все категории</option>
              {categories.map(category => (
                <option key={category.id} value={category.id}>
                  {category.name_ru}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Статистика */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{services.length}</div>
          <div className="text-sm text-gray-600">Всего услуг</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{services.filter(s => s.active).length}</div>
          <div className="text-sm text-gray-600">Активных</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{categories.length}</div>
          <div className="text-sm text-gray-600">Категорий</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">{filteredServices.length}</div>
          <div className="text-sm text-gray-600">Найдено</div>
        </Card>
      </div>

      {/* Таблица услуг */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Услуга
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Категория
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Цена
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Длительность
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Врач
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Статус
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Действия
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredServices.map(service => {
                const specialty = getCategorySpecialty(service.category_id);
                const SpecialtyIcon = getSpecialtyIcon(specialty);
                const doctor = doctors.find(d => d.id === service.doctor_id);
                
                return (
                  <tr key={service.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <SpecialtyIcon size={20} className={`mr-3 ${specialtyColors[specialty] || 'text-gray-400'}`} />
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {service.name}
                          </div>
                          {service.code && (
                            <div className="text-sm text-gray-500">
                              Код: {service.code}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant="outline">
                        {getCategoryName(service.category_id)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {service.price ? `${service.price.toLocaleString()} ${service.currency || 'UZS'}` : 'Не указана'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {service.duration_minutes ? `${service.duration_minutes} мин` : '—'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {doctor ? doctor.user?.full_name || `Врач #${doctor.id}` : '—'}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={service.active ? 'success' : 'error'}>
                        {service.active ? 'Активна' : 'Неактивна'}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setEditingService(service)}
                        >
                          <Edit size={14} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteService(service.id)}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredServices.length === 0 && (
          <div className="text-center py-12">
            <Package size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Услуги не найдены
            </h3>
            <p className="text-gray-500">
              {searchTerm || selectedCategory !== 'all' || selectedSpecialty !== 'all'
                ? 'Попробуйте изменить критерии поиска'
                : 'Добавьте первую услугу в справочник'
              }
            </p>
          </div>
        )}
      </Card>

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
    <Card className="p-6">
      <h3 className="text-lg font-medium mb-4">
        {service ? 'Редактирование услуги' : 'Добавление услуги'}
      </h3>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Название услуги *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Код услуги
            </label>
            <input
              type="text"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Категория *
            </label>
            <select
              value={formData.category_id}
              onChange={(e) => handleChange('category_id', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              required
            >
              <option value="">Выберите категорию</option>
              {categories.map(category => (
                <option key={category.id} value={category.id}>
                  {category.name_ru} ({category.specialty})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Цена
            </label>
            <div className="flex">
              <input
                type="number"
                value={formData.price}
                onChange={(e) => handleChange('price', parseFloat(e.target.value) || '')}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                min="0"
                step="0.01"
              />
              <select
                value={formData.currency}
                onChange={(e) => handleChange('currency', e.target.value)}
                className="px-3 py-2 border-l-0 border border-gray-300 rounded-r-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="UZS">UZS</option>
                <option value="USD">USD</option>
                <option value="RUB">RUB</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Длительность (мин)
            </label>
            <input
              type="number"
              value={formData.duration_minutes}
              onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value) || 30)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              min="5"
              step="5"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Врач (опционально)
            </label>
            <select
              value={formData.doctor_id}
              onChange={(e) => handleChange('doctor_id', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="">Все врачи</option>
              {doctors.map(doctor => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.user?.full_name || `Врач #${doctor.id}`} ({doctor.specialty})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* ✅ НОВЫЕ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ */}
        <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
          <h4 className="text-md font-medium text-gray-900 dark:text-white mb-4">
            Настройки для мастера регистрации
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Код категории (K/D/C/L/S/O)
              </label>
              <select
                value={formData.category_code}
                onChange={(e) => handleChange('category_code', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="">Выберите категорию</option>
                <option value="K">K - Кардиология</option>
                <option value="D">D - Дерматология</option>
                <option value="C">C - Косметология</option>
                <option value="L">L - Лабораторные анализы</option>
                <option value="S">S - Стоматология</option>
                <option value="O">O - Другие услуги</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Код услуги (например: K01, L002)
              </label>
              <input
                type="text"
                value={formData.service_code}
                onChange={(e) => handleChange('service_code', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="K01"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Тег очереди
              </label>
              <select
                value={formData.queue_tag}
                onChange={(e) => handleChange('queue_tag', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="">Без очереди</option>
                <option value="ecg">ECG (отдельная очередь)</option>
                <option value="cardiology_common">Кардиология (общая)</option>
                <option value="stomatology">Стоматология</option>
                <option value="dermatology">Дерматология</option>
                <option value="cosmetology">Косметология</option>
                <option value="lab">Лаборатория</option>
              </select>
            </div>

            <div className="space-y-3">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="requires_doctor"
                  checked={formData.requires_doctor}
                  onChange={(e) => handleChange('requires_doctor', e.target.checked)}
                  className="mr-2"
                />
                <label htmlFor="requires_doctor" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Требует врача
                </label>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_consultation"
                  checked={formData.is_consultation}
                  onChange={(e) => handleChange('is_consultation', e.target.checked)}
                  className="mr-2"
                />
                <label htmlFor="is_consultation" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Это консультация
                </label>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="allow_doctor_price_override"
                  checked={formData.allow_doctor_price_override}
                  onChange={(e) => handleChange('allow_doctor_price_override', e.target.checked)}
                  className="mr-2"
                />
                <label htmlFor="allow_doctor_price_override" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Врач может изменить цену
                </label>
              </div>
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg mt-4">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Подсказка:</strong> Только ЭхоКГ (кардиолог) и Рентгенография зуб (стоматолог) требуют врача. 
              Консультации участвуют в расчёте льгот и повторных визитов.
            </p>
          </div>
        </div>

        <div className="flex items-center">
          <input
            type="checkbox"
            id="active"
            checked={formData.active}
            onChange={(e) => handleChange('active', e.target.checked)}
            className="mr-2"
          />
          <label htmlFor="active" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Услуга активна
          </label>
        </div>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            <X size={16} className="mr-2" />
            Отменить
          </Button>
          <Button type="submit">
            <Save size={16} className="mr-2" />
            Сохранить
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default ServiceCatalog;

