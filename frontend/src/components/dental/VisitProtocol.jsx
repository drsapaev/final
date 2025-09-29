import React, { useState, useEffect } from 'react';
import { 
  Calendar, 
  Clock, 
  User, 
  Camera, 
  FileText, 
  Pill, 
  Syringe,
  Scissors,
  Save,
  X,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  AlertCircle,
  Upload,
  Download,
  Printer
} from 'lucide-react';

/**
 * Протокол лечения по визитам для стоматологической ЭМК
 * Включает процедуры, материалы, анестезию, фото до/после
 */
const VisitProtocol = ({ 
  patientId, 
  patientName,
  visitId,
  initialData = null, 
  onSave, 
  onClose 
}) => {
  const [formData, setFormData] = useState({
    // Основные данные визита
    visitDate: new Date().toISOString().split('T')[0],
    visitTime: new Date().toTimeString().slice(0, 5),
    doctor: '',
    assistant: '',
    
    // Жалобы и анамнез
    chiefComplaint: '',
    historyOfPresentIllness: '',
    
    // Выполненные процедуры
    procedures: [],
    
    // Использованные материалы
    materials: [],
    
    // Анестезия
    anesthesia: [],
    
    // Фотофиксация
    photos: {
      before: [],
      during: [],
      after: []
    },
    
    // Рентгенологические данные
    radiographs: [],
    
    // Назначения
    prescriptions: [],
    recommendations: '',
    
    // Следующий визит
    nextVisit: {
      date: '',
      time: '',
      purpose: ''
    },
    
    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [isEditing, setIsEditing] = useState(true);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('procedures');

  // Инициализация данных
  useEffect(() => {
    if (initialData) {
      setFormData({
        ...formData,
        ...initialData
      });
      setIsEditing(false);
    }
  }, [initialData]);

  // Обработчики
  const handleInputChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setFormData(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const handleArrayAdd = (field, item) => {
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], item]
    }));
  };

  const handleArrayRemove = (field, index) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const handleArrayUpdate = (field, index, updates) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].map((item, i) => 
        i === index ? { ...item, ...updates } : item
      )
    }));
  };

  const handlePhotoUpload = (category, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const photoData = {
        id: Date.now(),
        url: e.target.result,
        filename: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date().toISOString(),
        description: ''
      };
      
      handleArrayAdd(`photos.${category}`, photoData);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const updatedData = {
        ...formData,
        updatedAt: new Date().toISOString()
      };
      
      if (onSave) {
        await onSave(updatedData);
      }
      
      setIsEditing(false);
    } catch (error) {
      console.error('Ошибка сохранения:', error);
    } finally {
      setLoading(false);
    }
  };

  // Вкладки
  const tabs = [
    { id: 'procedures', label: 'Процедуры', icon: Scissors },
    { id: 'materials', label: 'Материалы', icon: Pill },
    { id: 'anesthesia', label: 'Анестезия', icon: Syringe },
    { id: 'photos', label: 'Фотофиксация', icon: Camera },
    { id: 'radiographs', label: 'Рентген', icon: FileText },
    { id: 'prescriptions', label: 'Назначения', icon: Pill }
  ];

  // Стандартные процедуры
  const standardProcedures = [
    'Осмотр полости рта',
    'Профессиональная гигиена',
    'Лечение кариеса',
    'Эндодонтическое лечение',
    'Пломбирование',
    'Восстановление коронки',
    'Удаление зуба',
    'Имплантация',
    'Протезирование',
    'Ортодонтическое лечение',
    'Пародонтологическое лечение',
    'Хирургическое вмешательство',
    'Консультация',
    'Контрольный осмотр'
  ];

  // Рендер процедур
  const renderProcedures = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Выполненные процедуры</h3>
        <p className="text-sm text-gray-600">
          Детальное описание всех выполненных стоматологических процедур
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.procedures.map((procedure, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название процедуры
                </label>
                <select
                  value={procedure.name || ''}
                  onChange={(e) => handleArrayUpdate('procedures', index, { name: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                >
                  <option value="">Выберите процедуру</option>
                  {standardProcedures.map(proc => (
                    <option key={proc} value={proc}>{proc}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Зубы
                </label>
                <input
                  type="text"
                  value={procedure.teeth || ''}
                  onChange={(e) => handleArrayUpdate('procedures', index, { teeth: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 11, 12, 13"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Время начала
                </label>
                <input
                  type="time"
                  value={procedure.startTime || ''}
                  onChange={(e) => handleArrayUpdate('procedures', index, { startTime: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Время окончания
                </label>
                <input
                  type="time"
                  value={procedure.endTime || ''}
                  onChange={(e) => handleArrayUpdate('procedures', index, { endTime: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                />
              </div>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Описание процедуры
              </label>
              <textarea
                value={procedure.description || ''}
                onChange={(e) => handleArrayUpdate('procedures', index, { description: e.target.value })}
                disabled={!isEditing}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Детальное описание выполненных манипуляций"
              />
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={procedure.completed || false}
                    onChange={(e) => handleArrayUpdate('procedures', index, { completed: e.target.checked })}
                    disabled={!isEditing}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">Завершено</span>
                </label>
                
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={procedure.complications || false}
                    onChange={(e) => handleArrayUpdate('procedures', index, { complications: e.target.checked })}
                    disabled={!isEditing}
                    className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                  />
                  <span className="text-sm text-gray-700">Осложнения</span>
                </label>
              </div>
              
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('procedures', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('procedures', {
              name: '',
              teeth: '',
              startTime: '',
              endTime: '',
              description: '',
              completed: false,
              complications: false
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить процедуру
          </button>
        )}
      </div>
    </div>
  );

  // Рендер материалов
  const renderMaterials = () => (
    <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Использованные материалы</h3>
        <p className="text-sm text-gray-600">
          Учет всех материалов, использованных во время визита
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.materials.map((material, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название материала
                </label>
                <input
                  type="text"
                  value={material.name || ''}
                  onChange={(e) => handleArrayUpdate('materials', index, { name: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: Композит Filtek"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Количество
                </label>
                <input
                  type="text"
                  value={material.quantity || ''}
                  onChange={(e) => handleArrayUpdate('materials', index, { quantity: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 1 шт, 2 мл"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Партия/Срок годности
                </label>
                <input
                  type="text"
                  value={material.batch || ''}
                  onChange={(e) => handleArrayUpdate('materials', index, { batch: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 12345, 12.2025"
                />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
                value={material.notes || ''}
                onChange={(e) => handleArrayUpdate('materials', index, { notes: e.target.value })}
                disabled={!isEditing}
                rows={2}
                className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Дополнительные заметки"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('materials', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('materials', {
              name: '',
              quantity: '',
              batch: '',
              notes: ''
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить материал
          </button>
        )}
      </div>
    </div>
  );

  // Рендер анестезии
  const renderAnesthesia = () => (
    <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Анестезия</h3>
        <p className="text-sm text-gray-600">
          Детали анестезии, примененной во время визита
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.anesthesia.map((anesthesia, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Препарат
                </label>
                <input
                  type="text"
                  value={anesthesia.drug || ''}
                  onChange={(e) => handleArrayUpdate('anesthesia', index, { drug: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: Лидокаин 2%"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Доза
                </label>
                <input
                  type="text"
                  value={anesthesia.dose || ''}
                  onChange={(e) => handleArrayUpdate('anesthesia', index, { dose: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 1.8 мл"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Метод введения
                </label>
                <select
                  value={anesthesia.method || ''}
                  onChange={(e) => handleArrayUpdate('anesthesia', index, { method: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                >
                  <option value="">Выберите метод</option>
                  <option value="infiltration">Инфильтрационная</option>
                  <option value="conduction">Проводниковая</option>
                  <option value="intraligamentary">Внутрисвязочная</option>
                  <option value="intraosseous">Внутрикостная</option>
                  <option value="topical">Поверхностная</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Область
                </label>
                <input
                  type="text"
                  value={anesthesia.area || ''}
                  onChange={(e) => handleArrayUpdate('anesthesia', index, { area: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 11-13, верхняя челюсть"
                />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={anesthesia.effective || false}
                    onChange={(e) => handleArrayUpdate('anesthesia', index, { effective: e.target.checked })}
                    disabled={!isEditing}
                    className="rounded border-gray-300 text-green-600 focus:ring-green-500"
                  />
                  <span className="text-sm text-gray-700">Эффективна</span>
                </label>
                
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={anesthesia.complications || false}
                    onChange={(e) => handleArrayUpdate('anesthesia', index, { complications: e.target.checked })}
                    disabled={!isEditing}
                    className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                  />
                  <span className="text-sm text-gray-700">Осложнения</span>
                </label>
              </div>
              
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('anesthesia', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('anesthesia', {
              drug: '',
              dose: '',
              method: '',
              area: '',
              effective: false,
              complications: false
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить анестезию
          </button>
        )}
      </div>
    </div>
  );

  // Рендер фотофиксации
  const renderPhotos = () => (
    <div className="space-y-6">
      <div className="bg-orange-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Фотофиксация</h3>
        <p className="text-sm text-gray-600">
          Фотографии до, во время и после лечения
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['before', 'during', 'after'].map(category => (
          <div key={category}>
            <h4 className="font-semibold mb-3 capitalize">
              {category === 'before' ? 'До лечения' : 
               category === 'during' ? 'Во время лечения' : 'После лечения'}
            </h4>
            <div className="space-y-2">
              {formData.photos[category].map((photo, index) => (
                <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                  <Camera className="h-4 w-4 text-blue-500" />
                  <span className="text-sm flex-1">{photo.filename}</span>
                  {isEditing && (
                    <button
                      onClick={() => handleArrayRemove(`photos.${category}`, index)}
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
              {isEditing && (
                <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                  <Upload className="h-4 w-4" />
                  <span className="text-sm">Загрузить фото</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => {
                      if (e.target.files[0]) {
                        handlePhotoUpload(category, e.target.files[0]);
                      }
                    }}
                    className="hidden"
                  />
                </label>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // Рендер рентгенов
  const renderRadiographs = () => (
    <div className="space-y-6">
      <div className="bg-cyan-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Рентгенологические данные</h3>
        <p className="text-sm text-gray-600">
          Рентгеновские снимки, выполненные во время визита
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.radiographs.map((radiograph, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип снимка
                </label>
                <select
                  value={radiograph.type || ''}
                  onChange={(e) => handleArrayUpdate('radiographs', index, { type: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                >
                  <option value="">Выберите тип</option>
                  <option value="periapical">Периапикальный</option>
                  <option value="bitewing">Прикусной</option>
                  <option value="panoramic">Панорамный</option>
                  <option value="cbct">КЛКТ</option>
                  <option value="lateral">Боковой</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Область
                </label>
                <input
                  type="text"
                  value={radiograph.area || ''}
                  onChange={(e) => handleArrayUpdate('radiographs', index, { area: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 11-13, верхняя челюсть"
                />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
                value={radiograph.findings || ''}
                onChange={(e) => handleArrayUpdate('radiographs', index, { findings: e.target.value })}
                disabled={!isEditing}
                rows={2}
                className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Описание находок"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('radiographs', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('radiographs', {
              type: '',
              area: '',
              findings: ''
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить рентген
          </button>
        )}
      </div>
    </div>
  );

  // Рендер назначений
  const renderPrescriptions = () => (
    <div className="space-y-6">
      <div className="bg-red-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Назначения</h3>
        <p className="text-sm text-gray-600">
          Лекарственные препараты и рекомендации пациенту
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.prescriptions.map((prescription, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Препарат
                </label>
                <input
                  type="text"
                  value={prescription.medication || ''}
                  onChange={(e) => handleArrayUpdate('prescriptions', index, { medication: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Название лекарства"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дозировка
                </label>
                <input
                  type="text"
                  value={prescription.dosage || ''}
                  onChange={(e) => handleArrayUpdate('prescriptions', index, { dosage: e.target.value })}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 500мг"
                />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
                value={prescription.instructions || ''}
                onChange={(e) => handleArrayUpdate('prescriptions', index, { instructions: e.target.value })}
                disabled={!isEditing}
                rows={2}
                className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Инструкции по применению"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('prescriptions', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('prescriptions', {
              medication: '',
              dosage: '',
              instructions: ''
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить назначение
          </button>
        )}
      </div>
      
      {/* Рекомендации */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Общие рекомендации
        </label>
        <textarea
          value={formData.recommendations || ''}
          onChange={(e) => handleInputChange('recommendations', e.target.value)}
          disabled={!isEditing}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder="Рекомендации по уходу, питанию, следующему визиту"
        />
      </div>
      
      {/* Следующий визит */}
      <div className="border-t pt-4">
        <h4 className="font-semibold mb-3">Следующий визит</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Дата
            </label>
            <input
              type="date"
              value={formData.nextVisit.date || ''}
              onChange={(e) => handleInputChange('nextVisit.date', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Время
            </label>
            <input
              type="time"
              value={formData.nextVisit.time || ''}
              onChange={(e) => handleInputChange('nextVisit.time', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Цель визита
            </label>
            <input
              type="text"
              value={formData.nextVisit.purpose || ''}
              onChange={(e) => handleInputChange('nextVisit.purpose', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Например: Контрольный осмотр"
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'procedures':
        return renderProcedures();
      case 'materials':
        return renderMaterials();
      case 'anesthesia':
        return renderAnesthesia();
      case 'photos':
        return renderPhotos();
      case 'radiographs':
        return renderRadiographs();
      case 'prescriptions':
        return renderPrescriptions();
      default:
        return renderProcedures();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              Протокол визита: {patientName}
            </h2>
            <p className="text-gray-600 text-sm">
              {formData.visitDate} в {formData.visitTime} | {isEditing ? 'Режим редактирования' : 'Просмотр данных'}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <Edit className="h-4 w-4" />
                Редактировать
              </button>
            ) : (
              <>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
                >
                  <X className="h-4 w-4" />
                  Отмена
                </button>
                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  <Save className="h-4 w-4" />
                  {loading ? 'Сохранение...' : 'Сохранить'}
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Вкладки */}
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

export default VisitProtocol;

