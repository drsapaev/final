import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Plus, 
  Edit, 
  Trash2, 
  Copy, 
  Save, 
  X, 
  Search, 
  Filter,
  Tag,
  Clock,
  User,
  Scissors,
  Pill,
  Syringe,
  Camera,
  CheckCircle,
  AlertCircle,
  Star,
  BookOpen
} from 'lucide-react';

/**
 * Шаблоны протоколов для стоматологической ЭМК
 * Включает стандартные процедуры, материалы, анестезию
 */
const ProtocolTemplates = ({ 
  onSelectTemplate, 
  onClose 
}) => {
  const [templates, setTemplates] = useState([
    // Шаблоны процедур
    {
      id: 'caries_treatment',
      name: 'Лечение кариеса',
      category: 'procedure',
      description: 'Стандартный протокол лечения кариеса',
      icon: Scissors,
      color: 'blue',
      steps: [
        { type: 'procedure', name: 'Осмотр полости рта', duration: 5, required: true },
        { type: 'procedure', name: 'Анестезия', duration: 10, required: true },
        { type: 'procedure', name: 'Препарирование кариозной полости', duration: 20, required: true },
        { type: 'procedure', name: 'Пломбирование', duration: 15, required: true },
        { type: 'procedure', name: 'Шлифовка и полировка', duration: 10, required: true }
      ],
      materials: [
        { name: 'Композитный материал', quantity: '1 шт', required: true },
        { name: 'Адгезивная система', quantity: '1 набор', required: true },
        { name: 'Стоматологическая вата', quantity: '10 шт', required: false }
      ],
      anesthesia: [
        { drug: 'Лидокаин 2%', dose: '1.8 мл', method: 'инфильтрационная', required: true }
      ],
      photos: [
        { type: 'before', description: 'Фото до лечения', required: true },
        { type: 'after', description: 'Фото после лечения', required: true }
      ],
      prescriptions: [
        { medication: 'Ибупрофен', dosage: '400мг', instructions: 'При болях 3 раза в день', required: false }
      ],
      tags: ['кариес', 'пломбирование', 'терапия'],
      estimatedDuration: 60,
      difficulty: 'medium',
      isDefault: true
    },
    
    {
      id: 'root_canal_treatment',
      name: 'Эндодонтическое лечение',
      category: 'procedure',
      description: 'Протокол лечения корневых каналов',
      icon: Scissors,
      color: 'red',
      steps: [
        { type: 'procedure', name: 'Диагностика', duration: 10, required: true },
        { type: 'procedure', name: 'Анестезия', duration: 10, required: true },
        { type: 'procedure', name: 'Изоляция зуба', duration: 5, required: true },
        { type: 'procedure', name: 'Препарирование полости доступа', duration: 15, required: true },
        { type: 'procedure', name: 'Инструментальная обработка каналов', duration: 30, required: true },
        { type: 'procedure', name: 'Медикаментозная обработка', duration: 10, required: true },
        { type: 'procedure', name: 'Пломбирование каналов', duration: 20, required: true },
        { type: 'procedure', name: 'Восстановление коронки', duration: 25, required: true }
      ],
      materials: [
        { name: 'Эндодонтические файлы', quantity: '1 набор', required: true },
        { name: 'Гуттаперча', quantity: '1 набор', required: true },
        { name: 'Эндодонтический цемент', quantity: '1 шт', required: true },
        { name: 'Антисептик', quantity: '10 мл', required: true }
      ],
      anesthesia: [
        { drug: 'Лидокаин 2%', dose: '2.0 мл', method: 'проводниковая', required: true }
      ],
      photos: [
        { type: 'before', description: 'Фото до лечения', required: true },
        { type: 'during', description: 'Фото во время лечения', required: false },
        { type: 'after', description: 'Фото после лечения', required: true }
      ],
      prescriptions: [
        { medication: 'Амоксициллин', dosage: '500мг', instructions: '3 раза в день 7 дней', required: true },
        { medication: 'Ибупрофен', dosage: '400мг', instructions: 'При болях', required: false }
      ],
      tags: ['эндодонтия', 'корневые каналы', 'пульпит'],
      estimatedDuration: 120,
      difficulty: 'high',
      isDefault: true
    },
    
    {
      id: 'tooth_extraction',
      name: 'Удаление зуба',
      category: 'surgery',
      description: 'Протокол удаления зуба',
      icon: Scissors,
      color: 'red',
      steps: [
        { type: 'procedure', name: 'Осмотр и диагностика', duration: 10, required: true },
        { type: 'procedure', name: 'Анестезия', duration: 10, required: true },
        { type: 'procedure', name: 'Отслоение десны', duration: 5, required: true },
        { type: 'procedure', name: 'Удаление зуба', duration: 20, required: true },
        { type: 'procedure', name: 'Кюретаж лунки', duration: 10, required: true },
        { type: 'procedure', name: 'Наложение швов', duration: 10, required: false },
        { type: 'procedure', name: 'Наложение тампона', duration: 5, required: true }
      ],
      materials: [
        { name: 'Стоматологические щипцы', quantity: '1 набор', required: true },
        { name: 'Элеваторы', quantity: '1 набор', required: true },
        { name: 'Шовный материал', quantity: '1 м', required: false },
        { name: 'Стоматологическая вата', quantity: '20 шт', required: true }
      ],
      anesthesia: [
        { drug: 'Лидокаин 2%', dose: '2.0 мл', method: 'проводниковая', required: true }
      ],
      photos: [
        { type: 'before', description: 'Фото до удаления', required: true },
        { type: 'after', description: 'Фото после удаления', required: true }
      ],
      prescriptions: [
        { medication: 'Амоксициллин', dosage: '500мг', instructions: '3 раза в день 5 дней', required: true },
        { medication: 'Ибупрофен', dosage: '400мг', instructions: 'При болях', required: true }
      ],
      tags: ['удаление', 'хирургия', 'зуб'],
      estimatedDuration: 60,
      difficulty: 'medium',
      isDefault: true
    },
    
    {
      id: 'professional_hygiene',
      name: 'Профессиональная гигиена',
      category: 'hygiene',
      description: 'Протокол профессиональной гигиены полости рта',
      icon: Scissors,
      color: 'green',
      steps: [
        { type: 'procedure', name: 'Осмотр полости рта', duration: 10, required: true },
        { type: 'procedure', name: 'Удаление зубного камня', duration: 30, required: true },
        { type: 'procedure', name: 'Полировка зубов', duration: 20, required: true },
        { type: 'procedure', name: 'Фторирование', duration: 10, required: false },
        { type: 'procedure', name: 'Обучение гигиене', duration: 15, required: true }
      ],
      materials: [
        { name: 'Ультразвуковой скалер', quantity: '1 шт', required: true },
        { name: 'Полировочные пасты', quantity: '1 набор', required: true },
        { name: 'Фторсодержащий гель', quantity: '1 шт', required: false }
      ],
      anesthesia: [],
      photos: [
        { type: 'before', description: 'Фото до чистки', required: true },
        { type: 'after', description: 'Фото после чистки', required: true }
      ],
      prescriptions: [],
      tags: ['гигиена', 'чистка', 'профилактика'],
      estimatedDuration: 75,
      difficulty: 'low',
      isDefault: true
    },
    
    {
      id: 'crown_preparation',
      name: 'Подготовка под коронку',
      category: 'prosthetics',
      description: 'Протокол подготовки зуба под коронку',
      icon: Scissors,
      color: 'purple',
      steps: [
        { type: 'procedure', name: 'Осмотр и планирование', duration: 10, required: true },
        { type: 'procedure', name: 'Анестезия', duration: 10, required: true },
        { type: 'procedure', name: 'Препарирование зуба', duration: 30, required: true },
        { type: 'procedure', name: 'Снятие оттисков', duration: 15, required: true },
        { type: 'procedure', name: 'Изготовление временной коронки', duration: 20, required: true },
        { type: 'procedure', name: 'Фиксация временной коронки', duration: 10, required: true }
      ],
      materials: [
        { name: 'Оттискная масса', quantity: '1 набор', required: true },
        { name: 'Временный цемент', quantity: '1 шт', required: true },
        { name: 'Пластмасса для временной коронки', quantity: '1 набор', required: true }
      ],
      anesthesia: [
        { drug: 'Лидокаин 2%', dose: '1.8 мл', method: 'инфильтрационная', required: true }
      ],
      photos: [
        { type: 'before', description: 'Фото до препарирования', required: true },
        { type: 'after', description: 'Фото после препарирования', required: true }
      ],
      prescriptions: [
        { medication: 'Ибупрофен', dosage: '400мг', instructions: 'При болях', required: false }
      ],
      tags: ['протезирование', 'коронка', 'препарирование'],
      estimatedDuration: 95,
      difficulty: 'high',
      isDefault: true
    }
  ]);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterDifficulty, setFilterDifficulty] = useState('all');
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);

  // Фильтрация шаблонов
  const filteredTemplates = templates.filter(template => {
    const matchesSearch = !searchQuery || 
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesCategory = filterCategory === 'all' || template.category === filterCategory;
    const matchesDifficulty = filterDifficulty === 'all' || template.difficulty === filterDifficulty;
    
    return matchesSearch && matchesCategory && matchesDifficulty;
  });

  // Категории шаблонов
  const categories = [
    { id: 'all', label: 'Все', icon: FileText },
    { id: 'procedure', label: 'Процедуры', icon: Scissors },
    { id: 'surgery', label: 'Хирургия', icon: Scissors },
    { id: 'hygiene', label: 'Гигиена', icon: Scissors },
    { id: 'prosthetics', label: 'Протезирование', icon: Scissors }
  ];

  // Уровни сложности
  const difficulties = [
    { id: 'all', label: 'Все', color: 'gray' },
    { id: 'low', label: 'Низкая', color: 'green' },
    { id: 'medium', label: 'Средняя', color: 'yellow' },
    { id: 'high', label: 'Высокая', color: 'red' }
  ];

  // Обработчики
  const handleSelectTemplate = (template) => {
    if (onSelectTemplate) {
      onSelectTemplate(template);
    }
    onClose();
  };

  const handleEditTemplate = (template) => {
    setEditingTemplate(template);
    setIsEditing(true);
  };

  const handleDeleteTemplate = (templateId) => {
    setTemplates(prev => prev.filter(t => t.id !== templateId));
  };

  const handleSaveTemplate = (template) => {
    if (editingTemplate) {
      setTemplates(prev => prev.map(t => t.id === template.id ? template : t));
    } else {
      setTemplates(prev => [...prev, { ...template, id: Date.now().toString() }]);
    }
    setIsEditing(false);
    setEditingTemplate(null);
  };

  const handleDuplicateTemplate = (template) => {
    const newTemplate = {
      ...template,
      id: Date.now().toString(),
      name: `${template.name} (копия)`,
      isDefault: false
    };
    setTemplates(prev => [...prev, newTemplate]);
  };

  // Рендер карточки шаблона
  const renderTemplateCard = (template) => (
    <div key={template.id} className="border rounded-lg p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            template.color === 'blue' ? 'bg-blue-100 text-blue-600' :
            template.color === 'red' ? 'bg-red-100 text-red-600' :
            template.color === 'green' ? 'bg-green-100 text-green-600' :
            template.color === 'purple' ? 'bg-purple-100 text-purple-600' :
            'bg-gray-100 text-gray-600'
          }`}>
            <template.icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-semibold text-lg">{template.name}</h3>
            <p className="text-sm text-gray-600">{template.description}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          {template.isDefault && (
            <Star className="h-4 w-4 text-yellow-500" />
          )}
          <div className={`w-3 h-3 rounded-full ${
            template.difficulty === 'low' ? 'bg-green-500' :
            template.difficulty === 'medium' ? 'bg-yellow-500' :
            template.difficulty === 'high' ? 'bg-red-500' :
            'bg-gray-500'
          }`} title={difficulties.find(d => d.id === template.difficulty)?.label} />
        </div>
      </div>
      
      <div className="space-y-2 mb-4">
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {template.estimatedDuration} мин
          </div>
          <div className="flex items-center gap-1">
            <Scissors className="h-4 w-4" />
            {template.steps.length} шагов
          </div>
          <div className="flex items-center gap-1">
            <Pill className="h-4 w-4" />
            {template.materials.length} материалов
          </div>
        </div>
        
        <div className="flex items-center gap-1 flex-wrap">
          {template.tags.map(tag => (
            <span key={tag} className="text-xs bg-gray-100 px-2 py-1 rounded">
              {tag}
            </span>
          ))}
        </div>
      </div>
      
      <div className="flex gap-2">
        <button
          onClick={() => handleSelectTemplate(template)}
          className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
        >
          Использовать
        </button>
        <button
          onClick={() => handleEditTemplate(template)}
          className="px-3 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
          title="Редактировать"
        >
          <Edit className="h-4 w-4" />
        </button>
        <button
          onClick={() => handleDuplicateTemplate(template)}
          className="px-3 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
          title="Дублировать"
        >
          <Copy className="h-4 w-4" />
        </button>
        {!template.isDefault && (
          <button
            onClick={() => handleDeleteTemplate(template.id)}
            className="px-3 py-2 border border-gray-300 text-red-700 rounded-md hover:bg-red-50"
            title="Удалить"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );

  // Рендер детального просмотра шаблона
  const renderTemplateDetails = (template) => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{template.name}</h2>
        <button
          onClick={() => setSelectedTemplate(null)}
          className="p-2 text-gray-500 hover:text-gray-700"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Шаги процедуры */}
        <div>
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Scissors className="h-4 w-4" />
            Шаги процедуры
          </h3>
          <div className="space-y-2">
            {template.steps.map((step, index) => (
              <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                <div className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{step.name}</div>
                  <div className="text-sm text-gray-600">
                    {step.duration} мин {step.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Материалы */}
        <div>
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Pill className="h-4 w-4" />
            Материалы
          </h3>
          <div className="space-y-2">
            {template.materials.map((material, index) => (
              <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                <div className="w-6 h-6 bg-green-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{material.name}</div>
                  <div className="text-sm text-gray-600">
                    {material.quantity} {material.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Анестезия */}
        {template.anesthesia.length > 0 && (
          <div>
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Syringe className="h-4 w-4" />
              Анестезия
            </h3>
            <div className="space-y-2">
              {template.anesthesia.map((anesthesia, index) => (
                <div key={index} className="p-2 bg-gray-50 rounded">
                  <div className="font-medium">{anesthesia.drug}</div>
                  <div className="text-sm text-gray-600">
                    {anesthesia.dose} - {anesthesia.method}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Фотофиксация */}
        {template.photos.length > 0 && (
          <div>
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Camera className="h-4 w-4" />
              Фотофиксация
            </h3>
            <div className="space-y-2">
              {template.photos.map((photo, index) => (
                <div key={index} className="p-2 bg-gray-50 rounded">
                  <div className="font-medium">{photo.description}</div>
                  <div className="text-sm text-gray-600">
                    {photo.type} {photo.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      
      <div className="flex gap-2">
        <button
          onClick={() => handleSelectTemplate(template)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Использовать шаблон
        </button>
        <button
          onClick={() => handleEditTemplate(template)}
          className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
        >
          Редактировать
        </button>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">Шаблоны протоколов</h2>
            <p className="text-gray-600 text-sm">
              {filteredTemplates.length} шаблонов | Выберите шаблон для использования
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              <Plus className="h-4 w-4" />
              Создать шаблон
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Панель поиска и фильтров */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Поиск */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Поиск шаблонов..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            
            {/* Фильтры */}
            <div className="flex gap-2">
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {categories.map(category => (
                  <option key={category.id} value={category.id}>
                    {category.label}
                  </option>
                ))}
              </select>
              
              <select
                value={filterDifficulty}
                onChange={(e) => setFilterDifficulty(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {difficulties.map(difficulty => (
                  <option key={difficulty.id} value={difficulty.id}>
                    {difficulty.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {selectedTemplate ? (
            renderTemplateDetails(selectedTemplate)
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {filteredTemplates.map(template => (
                <div key={template.id} onClick={() => setSelectedTemplate(template)}>
                  {renderTemplateCard(template)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProtocolTemplates;