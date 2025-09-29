import React, { useState, useEffect } from 'react';
import { 
  Camera, 
  Upload, 
  Download, 
  Trash2, 
  Eye, 
  Edit, 
  Search, 
  Filter,
  Calendar,
  MapPin,
  Tag,
  Plus,
  X,
  Save,
  FileImage,
  FileText,
  Video,
  Image as ImageIcon,
  ZoomIn,
  ZoomOut,
  RotateCw,
  RotateCcw,
  Maximize,
  Minimize
} from 'lucide-react';

/**
 * Архив фото и рентгенов для стоматологической ЭМК
 * Включает привязку к зубам, датам, категориям и поиск
 */
const PhotoArchive = ({ 
  patientId, 
  patientName,
  initialData = null, 
  onSave, 
  onClose 
}) => {
  const [formData, setFormData] = useState({
    // Основные данные
    patientId,
    patientName,
    
    // Медиа файлы
    mediaFiles: [],
    
    // Фильтры
    filters: {
      category: 'all',
      tooth: 'all',
      dateFrom: '',
      dateTo: '',
      tags: []
    },
    
    // Поиск
    searchQuery: '',
    
    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showImageViewer, setShowImageViewer] = useState(false);
  const [viewMode, setViewMode] = useState('grid'); // grid, list, timeline
  const [sortBy, setSortBy] = useState('date'); // date, tooth, category, name

  // Инициализация данных
  useEffect(() => {
    if (initialData) {
      setFormData(prev => ({
        ...prev,
        ...initialData
      }));
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

  const handleFileUpload = (files) => {
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const mediaFile = {
          id: Date.now() + Math.random(),
          name: file.name,
          type: file.type,
          size: file.size,
          url: e.target.result,
          category: 'photo',
          tooth: '',
          date: new Date().toISOString().split('T')[0],
          description: '',
          tags: [],
          uploadedAt: new Date().toISOString(),
          isRadiograph: file.type.includes('image') && (
            file.name.toLowerCase().includes('xray') ||
            file.name.toLowerCase().includes('panoramic') ||
            file.name.toLowerCase().includes('cbct') ||
            file.name.toLowerCase().includes('periapical')
          )
        };
        
        setFormData(prev => ({
          ...prev,
          mediaFiles: [...prev.mediaFiles, mediaFile]
        }));
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFileUpdate = (fileId, updates) => {
    setFormData(prev => ({
      ...prev,
      mediaFiles: prev.mediaFiles.map(file => 
        file.id === fileId ? { ...file, ...updates } : file
      )
    }));
  };

  const handleFileDelete = (fileId) => {
    setFormData(prev => ({
      ...prev,
      mediaFiles: prev.mediaFiles.filter(file => file.id !== fileId)
    }));
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

  // Фильтрация файлов
  const filteredFiles = formData.mediaFiles.filter(file => {
    const matchesSearch = !formData.searchQuery || 
      file.name.toLowerCase().includes(formData.searchQuery.toLowerCase()) ||
      file.description.toLowerCase().includes(formData.searchQuery.toLowerCase());
    
    const matchesCategory = formData.filters.category === 'all' || 
      file.category === formData.filters.category;
    
    const matchesTooth = formData.filters.tooth === 'all' || 
      file.tooth === formData.filters.tooth;
    
    const matchesDate = (!formData.filters.dateFrom || file.date >= formData.filters.dateFrom) &&
      (!formData.filters.dateTo || file.date <= formData.filters.dateTo);
    
    return matchesSearch && matchesCategory && matchesTooth && matchesDate;
  });

  // Сортировка файлов
  const sortedFiles = [...filteredFiles].sort((a, b) => {
    switch (sortBy) {
      case 'date':
        return new Date(b.date) - new Date(a.date);
      case 'tooth':
        return a.tooth.localeCompare(b.tooth);
      case 'category':
        return a.category.localeCompare(b.category);
      case 'name':
        return a.name.localeCompare(b.name);
      default:
        return 0;
    }
  });

  // Категории медиа файлов
  const categories = [
    { id: 'all', label: 'Все', icon: FileImage },
    { id: 'photo', label: 'Фото', icon: Camera },
    { id: 'radiograph', label: 'Рентген', icon: FileText },
    { id: 'video', label: 'Видео', icon: Video },
    { id: 'document', label: 'Документы', icon: FileText }
  ];

  // Зубы для фильтрации
  const teeth = [
    'all', '11', '12', '13', '14', '15', '16', '17', '18',
    '21', '22', '23', '24', '25', '26', '27', '28',
    '31', '32', '33', '34', '35', '36', '37', '38',
    '41', '42', '43', '44', '45', '46', '47', '48'
  ];

  // Рендер сетки файлов
  const renderGridView = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {sortedFiles.map(file => (
        <div key={file.id} className="border rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
          {/* Превью файла */}
          <div 
            className="aspect-square bg-gray-100 flex items-center justify-center cursor-pointer relative group"
            onClick={() => {
              setSelectedFile(file);
              setShowImageViewer(true);
            }}
          >
            {file.type.startsWith('image/') ? (
              <img 
                src={file.url} 
                alt={file.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center">
                <FileImage className="h-12 w-12 text-gray-400 mx-auto mb-2" />
                <span className="text-sm text-gray-600">{file.name}</span>
              </div>
            )}
            
            {/* Overlay с информацией */}
            <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-opacity flex items-center justify-center">
              <div className="opacity-0 group-hover:opacity-100 transition-opacity text-white text-center">
                <Eye className="h-6 w-6 mx-auto mb-1" />
                <span className="text-sm">Просмотр</span>
              </div>
            </div>
          </div>
          
          {/* Информация о файле */}
          <div className="p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium truncate">{file.name}</span>
              <div className="flex items-center gap-1">
                {file.category === 'photo' && <Camera className="h-3 w-3 text-blue-500" />}
                {file.category === 'radiograph' && <FileText className="h-3 w-3 text-red-500" />}
                {file.category === 'video' && <Video className="h-3 w-3 text-purple-500" />}
                {file.category === 'document' && <FileText className="h-3 w-3 text-gray-500" />}
              </div>
            </div>
            
            <div className="text-xs text-gray-600 space-y-1">
              <div className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {new Date(file.date).toLocaleDateString('ru-RU')}
              </div>
              {file.tooth && (
                <div className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  Зуб {file.tooth}
                </div>
              )}
              {file.tags.length > 0 && (
                <div className="flex items-center gap-1">
                  <Tag className="h-3 w-3" />
                  {file.tags.join(', ')}
                </div>
              )}
            </div>
            
            {isEditing && (
              <div className="mt-2 flex gap-1">
                <button
                  onClick={() => handleFileUpdate(file.id, {})}
                  className="flex-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                >
                  <Edit className="h-3 w-3 mx-auto" />
                </button>
                <button
                  onClick={() => handleFileDelete(file.id)}
                  className="flex-1 px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
                >
                  <Trash2 className="h-3 w-3 mx-auto" />
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );

  // Рендер списка файлов
  const renderListView = () => (
    <div className="space-y-2">
      {sortedFiles.map(file => (
        <div key={file.id} className="border rounded-lg p-4 hover:bg-gray-50">
          <div className="flex items-center gap-4">
            {/* Превью */}
            <div 
              className="w-16 h-16 bg-gray-100 rounded flex items-center justify-center cursor-pointer"
              onClick={() => {
                setSelectedFile(file);
                setShowImageViewer(true);
              }}
            >
              {file.type.startsWith('image/') ? (
                <img 
                  src={file.url} 
                  alt={file.name}
                  className="w-full h-full object-cover rounded"
                />
              ) : (
                <FileImage className="h-6 w-6 text-gray-400" />
              )}
            </div>
            
            {/* Информация */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium truncate">{file.name}</span>
                <div className="flex items-center gap-1">
                  {file.category === 'photo' && <Camera className="h-4 w-4 text-blue-500" />}
                  {file.category === 'radiograph' && <FileText className="h-4 w-4 text-red-500" />}
                  {file.category === 'video' && <Video className="h-4 w-4 text-purple-500" />}
                  {file.category === 'document' && <FileText className="h-4 w-4 text-gray-500" />}
                </div>
              </div>
              
              <div className="text-sm text-gray-600 space-y-1">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {new Date(file.date).toLocaleDateString('ru-RU')}
                  </span>
                  {file.tooth && (
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      Зуб {file.tooth}
                    </span>
                  )}
                  <span className="text-xs text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
                
                {file.description && (
                  <p className="text-sm text-gray-700 truncate">{file.description}</p>
                )}
                
                {file.tags.length > 0 && (
                  <div className="flex items-center gap-1 flex-wrap">
                    <Tag className="h-3 w-3" />
                    {file.tags.map(tag => (
                      <span key={tag} className="text-xs bg-gray-100 px-2 py-1 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {/* Действия */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setSelectedFile(file);
                  setShowImageViewer(true);
                }}
                className="p-2 text-gray-500 hover:text-blue-600"
                title="Просмотр"
              >
                <Eye className="h-4 w-4" />
              </button>
              
              <button
                onClick={() => {
                  const link = document.createElement('a');
                  link.href = file.url;
                  link.download = file.name;
                  link.click();
                }}
                className="p-2 text-gray-500 hover:text-green-600"
                title="Скачать"
              >
                <Download className="h-4 w-4" />
              </button>
              
              {isEditing && (
                <button
                  onClick={() => handleFileDelete(file.id)}
                  className="p-2 text-gray-500 hover:text-red-600"
                  title="Удалить"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  // Рендер временной шкалы
  const renderTimelineView = () => {
    const groupedFiles = sortedFiles.reduce((groups, file) => {
      const date = file.date;
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(file);
      return groups;
    }, {});

    return (
      <div className="space-y-6">
        {Object.entries(groupedFiles).map(([date, files]) => (
          <div key={date}>
            <div className="flex items-center gap-4 mb-4">
              <div className="w-4 h-4 bg-blue-500 rounded-full"></div>
              <h3 className="text-lg font-semibold">
                {new Date(date).toLocaleDateString('ru-RU', { 
                  weekday: 'long', 
                  year: 'numeric', 
                  month: 'long', 
                  day: 'numeric' 
                })}
              </h3>
            </div>
            
            <div className="ml-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {files.map(file => (
                <div key={file.id} className="border rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
                  <div 
                    className="aspect-video bg-gray-100 flex items-center justify-center cursor-pointer"
                    onClick={() => {
                      setSelectedFile(file);
                      setShowImageViewer(true);
                    }}
                  >
                    {file.type.startsWith('image/') ? (
                      <img 
                        src={file.url} 
                        alt={file.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="text-center">
                        <FileImage className="h-8 w-8 text-gray-400 mx-auto mb-1" />
                        <span className="text-xs text-gray-600">{file.name}</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium truncate">{file.name}</span>
                      <div className="flex items-center gap-1">
                        {file.category === 'photo' && <Camera className="h-3 w-3 text-blue-500" />}
                        {file.category === 'radiograph' && <FileText className="h-3 w-3 text-red-500" />}
                        {file.category === 'video' && <Video className="h-3 w-3 text-purple-500" />}
                        {file.category === 'document' && <FileText className="h-3 w-3 text-gray-500" />}
                      </div>
                    </div>
                    
                    {file.tooth && (
                      <div className="text-xs text-gray-600 mb-1">
                        Зуб {file.tooth}
                      </div>
                    )}
                    
                    {file.description && (
                      <p className="text-xs text-gray-700 truncate">{file.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  };

  // Рендер просмотрщика изображений
  const renderImageViewer = () => {
    if (!selectedFile || !showImageViewer) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
        <div className="relative max-w-7xl max-h-full p-4">
          {/* Кнопка закрытия */}
          <button
            onClick={() => setShowImageViewer(false)}
            className="absolute top-4 right-4 z-10 p-2 bg-black bg-opacity-50 text-white rounded-full hover:bg-opacity-75"
          >
            <X className="h-6 w-6" />
          </button>
          
          {/* Изображение */}
          <div className="relative">
            {selectedFile.type.startsWith('image/') ? (
              <img 
                src={selectedFile.url} 
                alt={selectedFile.name}
                className="max-w-full max-h-full object-contain"
              />
            ) : (
              <div className="w-96 h-96 bg-gray-100 flex items-center justify-center rounded">
                <div className="text-center text-white">
                  <FileImage className="h-16 w-16 mx-auto mb-4" />
                  <p className="text-lg">{selectedFile.name}</p>
                  <p className="text-sm text-gray-300">Предпросмотр недоступен</p>
                </div>
              </div>
            )}
          </div>
          
          {/* Информация о файле */}
          <div className="absolute bottom-4 left-4 right-4 bg-black bg-opacity-50 text-white p-4 rounded">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold">{selectedFile.name}</h3>
                <div className="text-sm text-gray-300 space-y-1">
                  <div>Дата: {new Date(selectedFile.date).toLocaleDateString('ru-RU')}</div>
                  {selectedFile.tooth && <div>Зуб: {selectedFile.tooth}</div>}
                  {selectedFile.description && <div>Описание: {selectedFile.description}</div>}
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const link = document.createElement('a');
                    link.href = selectedFile.url;
                    link.download = selectedFile.name;
                    link.click();
                  }}
                  className="p-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  <Download className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-7xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              Фото и рентген архив: {patientName}
            </h2>
            <p className="text-gray-600 text-sm">
              {formData.mediaFiles.length} файлов | {isEditing ? 'Режим редактирования' : 'Просмотр'}
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

        {/* Панель инструментов */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Поиск */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Поиск файлов..."
                  value={formData.searchQuery}
                  onChange={(e) => handleInputChange('searchQuery', e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            
            {/* Фильтры */}
            <div className="flex gap-2">
              <select
                value={formData.filters.category}
                onChange={(e) => handleInputChange('filters.category', e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {categories.map(category => (
                  <option key={category.id} value={category.id}>
                    {category.label}
                  </option>
                ))}
              </select>
              
              <select
                value={formData.filters.tooth}
                onChange={(e) => handleInputChange('filters.tooth', e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">Все зубы</option>
                {teeth.slice(1).map(tooth => (
                  <option key={tooth} value={tooth}>Зуб {tooth}</option>
                ))}
              </select>
              
              <input
                type="date"
                value={formData.filters.dateFrom}
                onChange={(e) => handleInputChange('filters.dateFrom', e.target.value)}
                placeholder="От"
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              
              <input
                type="date"
                value={formData.filters.dateTo}
                onChange={(e) => handleInputChange('filters.dateTo', e.target.value)}
                placeholder="До"
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            
            {/* Сортировка и вид */}
            <div className="flex gap-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="date">По дате</option>
                <option value="tooth">По зубу</option>
                <option value="category">По категории</option>
                <option value="name">По имени</option>
              </select>
              
              <div className="flex border border-gray-300 rounded-md">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`px-3 py-2 ${viewMode === 'grid' ? 'bg-blue-500 text-white' : 'text-gray-700'}`}
                >
                  <ImageIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`px-3 py-2 ${viewMode === 'list' ? 'bg-blue-500 text-white' : 'text-gray-700'}`}
                >
                  <FileText className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setViewMode('timeline')}
                  className={`px-3 py-2 ${viewMode === 'timeline' ? 'bg-blue-500 text-white' : 'text-gray-700'}`}
                >
                  <Calendar className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Загрузка файлов */}
        {isEditing && (
          <div className="p-4 border-b bg-blue-50">
            <label className="flex items-center gap-2 p-4 border-2 border-dashed border-blue-300 rounded-lg cursor-pointer hover:border-blue-500">
              <Upload className="h-5 w-5 text-blue-500" />
              <span className="text-blue-700">Загрузить файлы</span>
              <input
                type="file"
                multiple
                accept="image/*,video/*,.pdf,.doc,.docx"
                onChange={(e) => handleFileUpload(e.target.files)}
                className="hidden"
              />
            </label>
          </div>
        )}

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {sortedFiles.length === 0 ? (
            <div className="text-center py-12">
              <Camera className="h-16 w-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Архив пуст</h3>
              <p className="text-gray-600 mb-4">
                {isEditing ? 'Загрузите файлы для создания архива' : 'Нет файлов для отображения'}
              </p>
              {isEditing && (
                <label className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer">
                  <Upload className="h-4 w-4" />
                  Загрузить файлы
                  <input
                    type="file"
                    multiple
                    accept="image/*,video/*,.pdf,.doc,.docx"
                    onChange={(e) => handleFileUpload(e.target.files)}
                    className="hidden"
                  />
                </label>
              )}
            </div>
          ) : (
            <>
              {viewMode === 'grid' && renderGridView()}
              {viewMode === 'list' && renderListView()}
              {viewMode === 'timeline' && renderTimelineView()}
            </>
          )}
        </div>
      </div>

      {/* Просмотрщик изображений */}
      {renderImageViewer()}
    </div>
  );
};

export default PhotoArchive;

