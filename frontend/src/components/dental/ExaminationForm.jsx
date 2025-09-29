import React, { useState, useEffect } from 'react';
import { 
  Camera, 
  Upload, 
  Save, 
  X, 
  Plus, 
  Trash2,
  Eye,
  Activity,
  Heart,
  AlertCircle,
  CheckCircle,
  FileImage,
  Video
} from 'lucide-react';

/**
 * Форма объективного осмотра для стоматологической ЭМК
 * Включает индексы гигиены, пародонт, фотофиксацию
 */
const ExaminationForm = ({ 
  patientId, 
  initialData = null, 
  onSave, 
  onClose 
}) => {
  const [formData, setFormData] = useState({
    // Основные данные осмотра
    examinationDate: new Date().toISOString().split('T')[0],
    doctor: '',
    complaints: '',
    
    // Общий осмотр
    generalCondition: {
      face: '',
      lips: '',
      tongue: '',
      mucosa: '',
      gums: ''
    },
    
    // Индексы гигиены
    hygieneIndices: {
      ohis: '', // Oral Hygiene Index Simplified
      pli: '',  // Plaque Index
      cpi: '',  // Community Periodontal Index
      bleeding: '' // Bleeding Index
    },
    
    // Пародонтальные карманы (по зубам)
    periodontalPockets: {},
    
    // Дополнительные измерения
    measurements: {
      overjet: '', // Горизонтальное перекрытие
      overbite: '', // Вертикальное перекрытие
      midline: '', // Срединная линия
      crossbite: '', // Перекрестный прикус
      openBite: '' // Открытый прикус
    },
    
    // Фото и рентген
    photos: {
      before: [],
      after: [],
      intraoral: [],
      extraoral: []
    },
    
    // Рентгенологические данные
    radiographs: {
      panoramic: '',
      periapical: [],
      bitewing: [],
      cbct: ''
    },
    
    // Заключение
    conclusion: '',
    recommendations: '',
    
    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [activeTab, setActiveTab] = useState('general');
  const [isEditing, setIsEditing] = useState(true);
  const [loading, setLoading] = useState(false);

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

  const handlePhotoUpload = (category, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const photoData = {
        id: Date.now(),
        url: e.target.result,
        filename: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date().toISOString()
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
    { id: 'general', label: 'Общий осмотр', icon: Eye },
    { id: 'hygiene', label: 'Индексы гигиены', icon: Activity },
    { id: 'periodontal', label: 'Пародонт', icon: Heart },
    { id: 'measurements', label: 'Измерения', icon: AlertCircle },
    { id: 'photos', label: 'Фото/Рентген', icon: Camera },
    { id: 'conclusion', label: 'Заключение', icon: CheckCircle }
  ];

  // Рендер общего осмотра
  const renderGeneralExamination = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Лицо
          </label>
          <textarea
            value={formData.generalCondition.face || ''}
            onChange={(e) => handleInputChange('generalCondition.face', e.target.value)}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="Симметрия, цвет кожи, отеки, высыпания"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Губы
          </label>
          <textarea
            value={formData.generalCondition.lips || ''}
            onChange={(e) => handleInputChange('generalCondition.lips', e.target.value)}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="Цвет, влажность, трещины, герпес"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Язык
          </label>
          <textarea
            value={formData.generalCondition.tongue || ''}
            onChange={(e) => handleInputChange('generalCondition.tongue', e.target.value)}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="Цвет, налет, сосочки, движения"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Слизистая оболочка
          </label>
          <textarea
            value={formData.generalCondition.mucosa || ''}
            onChange={(e) => handleInputChange('generalCondition.mucosa', e.target.value)}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="Цвет, целостность, эрозии, язвы"
          />
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Десны
          </label>
          <textarea
            value={formData.generalCondition.gums || ''}
            onChange={(e) => handleInputChange('generalCondition.gums', e.target.value)}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="Цвет, консистенция, кровоточивость, отечность"
          />
        </div>
      </div>
    </div>
  );

  // Рендер индексов гигиены
  const renderHygieneIndices = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Индексы гигиены полости рта</h3>
        <p className="text-sm text-gray-600">
          Оценка состояния гигиены полости рта пациента
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            OHI-S (Упрощенный индекс гигиены)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              min="0"
              max="6"
              value={formData.hygieneIndices.ohis || ''}
              onChange={(e) => handleInputChange('hygieneIndices.ohis', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.ohis ? 
                (parseFloat(formData.hygieneIndices.ohis) < 1.2 ? 'Хорошая' :
                 parseFloat(formData.hygieneIndices.ohis) < 3.0 ? 'Удовлетворительная' : 'Плохая') : ''
              }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            PLI (Индекс зубного налета)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              min="0"
              max="3"
              value={formData.hygieneIndices.pli || ''}
              onChange={(e) => handleInputChange('hygieneIndices.pli', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.pli ? 
                (parseFloat(formData.hygieneIndices.pli) < 0.5 ? 'Отличная' :
                 parseFloat(formData.hygieneIndices.pli) < 1.0 ? 'Хорошая' :
                 parseFloat(formData.hygieneIndices.pli) < 2.0 ? 'Удовлетворительная' : 'Плохая') : ''
              }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            CPI (Коммунальный пародонтальный индекс)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              min="0"
              max="4"
              value={formData.hygieneIndices.cpi || ''}
              onChange={(e) => handleInputChange('hygieneIndices.cpi', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.cpi ? 
                (parseFloat(formData.hygieneIndices.cpi) === 0 ? 'Здоровый' :
                 parseFloat(formData.hygieneIndices.cpi) === 1 ? 'Кровоточивость' :
                 parseFloat(formData.hygieneIndices.cpi) === 2 ? 'Зубной камень' :
                 parseFloat(formData.hygieneIndices.cpi) === 3 ? 'Карман 4-5мм' : 'Карман 6+мм') : ''
              }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Индекс кровоточивости
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              min="0"
              max="100"
              value={formData.hygieneIndices.bleeding || ''}
              onChange={(e) => handleInputChange('hygieneIndices.bleeding', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">%</span>
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер пародонтальных карманов
  const renderPeriodontalPockets = () => (
    <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Пародонтальные карманы</h3>
        <p className="text-sm text-gray-600">
          Измерение глубины пародонтальных карманов по каждому зубу
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Верхняя челюсть */}
        <div>
          <h4 className="font-semibold mb-3">Верхняя челюсть</h4>
          <div className="space-y-2">
            {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map(toothId => (
              <div key={toothId} className="flex items-center gap-2">
                <span className="w-8 text-sm font-medium">{toothId}</span>
                <div className="flex gap-1">
                  {['M', 'B', 'L', 'D'].map(position => (
                    <input
                      key={position}
                      type="number"
                      step="0.5"
                      min="0"
                      max="10"
                      value={formData.periodontalPockets[`${toothId}_${position}`] || ''}
                      onChange={(e) => handleInputChange(`periodontalPockets.${toothId}_${position}`, e.target.value)}
                      disabled={!isEditing}
                      className="w-12 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                      placeholder="0"
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Нижняя челюсть */}
        <div>
          <h4 className="font-semibold mb-3">Нижняя челюсть</h4>
          <div className="space-y-2">
            {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map(toothId => (
              <div key={toothId} className="flex items-center gap-2">
                <span className="w-8 text-sm font-medium">{toothId}</span>
                <div className="flex gap-1">
                  {['M', 'B', 'L', 'D'].map(position => (
                    <input
                      key={position}
                      type="number"
                      step="0.5"
                      min="0"
                      max="10"
                      value={formData.periodontalPockets[`${toothId}_${position}`] || ''}
                      onChange={(e) => handleInputChange(`periodontalPockets.${toothId}_${position}`, e.target.value)}
                      disabled={!isEditing}
                      className="w-12 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                      placeholder="0"
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="text-xs text-gray-600">
        <p><strong>M</strong> - Мезиальная, <strong>B</strong> - Буккальная, <strong>L</strong> - Лингвальная, <strong>D</strong> - Дистальная</p>
        <p>Измерения в миллиметрах (0-10 мм)</p>
      </div>
    </div>
  );

  // Рендер измерений
  const renderMeasurements = () => (
    <div className="space-y-6">
      <div className="bg-yellow-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Ортодонтические измерения</h3>
        <p className="text-sm text-gray-600">
          Измерения прикуса и окклюзии
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Overjet (Горизонтальное перекрытие)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              value={formData.measurements.overjet || ''}
              onChange={(e) => handleInputChange('measurements.overjet', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">мм</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Overbite (Вертикальное перекрытие)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              value={formData.measurements.overbite || ''}
              onChange={(e) => handleInputChange('measurements.overbite', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">мм</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Срединная линия
          </label>
          <select
            value={formData.measurements.midline || ''}
            onChange={(e) => handleInputChange('measurements.midline', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">Выберите</option>
            <option value="coincident">Совпадает</option>
            <option value="deviated_right">Смещена вправо</option>
            <option value="deviated_left">Смещена влево</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Перекрестный прикус
          </label>
          <select
            value={formData.measurements.crossbite || ''}
            onChange={(e) => handleInputChange('measurements.crossbite', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">Выберите</option>
            <option value="none">Отсутствует</option>
            <option value="anterior">Передний</option>
            <option value="posterior">Задний</option>
            <option value="both">Передний и задний</option>
          </select>
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Открытый прикус
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              step="0.1"
              value={formData.measurements.openBite || ''}
              onChange={(e) => handleInputChange('measurements.openBite', e.target.value)}
              disabled={!isEditing}
              className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
            <span className="text-sm text-gray-600">мм (0 = отсутствует)</span>
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер фото и рентгена
  const renderPhotosAndRadiographs = () => (
    <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Фото и рентгенологические данные</h3>
        <p className="text-sm text-gray-600">
          Загрузка фотографий и рентгеновских снимков
        </p>
      </div>
      
      {/* Фотографии */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="font-semibold mb-3">Фотографии "До"</h4>
          <div className="space-y-2">
            {formData.photos.before.map((photo, index) => (
              <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-blue-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing && (
                  <button
                    onClick={() => handleArrayRemove('photos.before', index)}
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
                      handlePhotoUpload('before', e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">Фотографии "После"</h4>
          <div className="space-y-2">
            {formData.photos.after.map((photo, index) => (
              <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-green-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing && (
                  <button
                    onClick={() => handleArrayRemove('photos.after', index)}
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
                      handlePhotoUpload('after', e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">Внутриротовые фото</h4>
          <div className="space-y-2">
            {formData.photos.intraoral.map((photo, index) => (
              <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-purple-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing && (
                  <button
                    onClick={() => handleArrayRemove('photos.intraoral', index)}
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
                      handlePhotoUpload('intraoral', e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">Внеротовые фото</h4>
          <div className="space-y-2">
            {formData.photos.extraoral.map((photo, index) => (
              <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-orange-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing && (
                  <button
                    onClick={() => handleArrayRemove('photos.extraoral', index)}
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
                      handlePhotoUpload('extraoral', e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />
              </label>
            )}
          </div>
        </div>
      </div>
      
      {/* Рентгенологические данные */}
      <div className="border-t pt-6">
        <h4 className="font-semibold mb-3">Рентгенологические данные</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Ортопантомограмма
            </label>
            <input
              type="text"
              value={formData.radiographs.panoramic || ''}
              onChange={(e) => handleInputChange('radiographs.panoramic', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Номер снимка или описание"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              КЛКТ
            </label>
            <input
              type="text"
              value={formData.radiographs.cbct || ''}
              onChange={(e) => handleInputChange('radiographs.cbct', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Номер снимка или описание"
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер заключения
  const renderConclusion = () => (
    <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Заключение и рекомендации</h3>
        <p className="text-sm text-gray-600">
          Итоговое заключение по результатам осмотра
        </p>
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Заключение
        </label>
        <textarea
          value={formData.conclusion || ''}
          onChange={(e) => handleInputChange('conclusion', e.target.value)}
          disabled={!isEditing}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder="Основные находки и диагнозы"
        />
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Рекомендации
        </label>
        <textarea
          value={formData.recommendations || ''}
          onChange={(e) => handleInputChange('recommendations', e.target.value)}
          disabled={!isEditing}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder="Рекомендации по лечению и профилактике"
        />
      </div>
    </div>
  );

  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'general':
        return renderGeneralExamination();
      case 'hygiene':
        return renderHygieneIndices();
      case 'periodontal':
        return renderPeriodontalPockets();
      case 'measurements':
        return renderMeasurements();
      case 'photos':
        return renderPhotosAndRadiographs();
      case 'conclusion':
        return renderConclusion();
      default:
        return renderGeneralExamination();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              Объективный осмотр
            </h2>
            <p className="text-gray-600 text-sm">
              {formData.examinationDate} | {isEditing ? 'Режим редактирования' : 'Просмотр данных'}
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

export default ExaminationForm;

