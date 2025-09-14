import React, { useState, useRef, useEffect } from 'react';
import { 
  Camera, 
  Upload, 
  Download, 
  RotateCcw, 
  ZoomIn, 
  ZoomOut,
  Maximize2,
  Minimize2,
  Eye,
  EyeOff,
  Trash2,
  Plus,
  Image as ImageIcon,
  Calendar,
  User,
  MapPin
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

/**
 * Компонент сравнения фото до/после для дерматологии
 * Основа: passport.md стр. 1789-2063
 */
const PhotoComparison = ({ 
  patientId, 
  patientName,
  onPhotosChange,
  className = '' 
}) => {
  // Проверяем демо-режим в самом начале
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('PhotoComparison: Skipping render in demo mode');
    return null;
  }
  
  const [photos, setPhotos] = useState({
    before: [],
    after: [],
    progress: []
  });
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [viewMode, setViewMode] = useState('split'); // split, overlay, slider
  const [zoom, setZoom] = useState(1);
  const [showFullscreen, setShowFullscreen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);

  // Загрузка существующих фото
  useEffect(() => {
    loadPatientPhotos();
  }, [patientId]);

  const loadPatientPhotos = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/dermatology/photos?patient_id=${patientId}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setPhotos(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки фото:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (files, category) => {
    try {
      setLoading(true);
      const formData = new FormData();
      
      Array.from(files).forEach((file, index) => {
        formData.append('files', file);
      });
      
      formData.append('patient_id', patientId);
      formData.append('category', category); // before, after, progress
      formData.append('patient_name', patientName);

      const response = await fetch('/api/v1/dermatology/photos/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        body: formData
      });

      if (response.ok) {
        const result = await response.json();
        setPhotos(prev => ({
          ...prev,
          [category]: [...prev[category], ...result.photos]
        }));
        setMessage({ type: 'success', text: `Загружено ${files.length} фото` });
        onPhotosChange?.(photos);
      } else {
        throw new Error('Ошибка загрузки фото');
      }
    } catch (error) {
      console.error('Ошибка загрузки:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePhoto = async (photoId, category) => {
    try {
      const response = await fetch(`/api/v1/dermatology/photos/${photoId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        setPhotos(prev => ({
          ...prev,
          [category]: prev[category].filter(p => p.id !== photoId)
        }));
        setMessage({ type: 'success', text: 'Фото удалено' });
      }
    } catch (error) {
      console.error('Ошибка удаления:', error);
      setMessage({ type: 'error', text: 'Ошибка удаления фото' });
    }
  };

  const handlePhotoClick = (photo) => {
    setSelectedPhoto(photo);
    setShowFullscreen(true);
  };

  const handleZoom = (direction) => {
    setZoom(prev => {
      const newZoom = direction === 'in' ? prev * 1.2 : prev / 1.2;
      return Math.max(0.5, Math.min(5, newZoom));
    });
  };

  const resetZoom = () => {
    setZoom(1);
  };

  const PhotoCard = ({ photo, category, title }) => (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
      <div className="aspect-square bg-gray-100 relative group">
        <img
          src={photo.thumbnail_url || photo.url}
          alt={title}
          className="w-full h-full object-cover cursor-pointer"
          onClick={() => handlePhotoClick(photo)}
        />
        
        {/* Overlay с информацией */}
        <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all duration-200 flex items-center justify-center">
          <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex space-x-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => handlePhotoClick(photo)}
              className="bg-white text-gray-900 hover:bg-gray-100"
            >
              <Eye size={16} />
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleDeletePhoto(photo.id, category)}
              className="bg-white text-red-600 hover:bg-red-50"
            >
              <Trash2 size={16} />
            </Button>
          </div>
        </div>

        {/* Badge категории */}
        <div className="absolute top-2 left-2">
          <Badge 
            variant={category === 'before' ? 'error' : category === 'after' ? 'success' : 'info'}
            size="sm"
          >
            {category === 'before' ? 'До' : category === 'after' ? 'После' : 'Прогресс'}
          </Badge>
        </div>
      </div>
      
      <div className="p-3">
        <div className="text-sm font-medium text-gray-900 dark:text-white mb-1">
          {title}
        </div>
        <div className="text-xs text-gray-500 flex items-center">
          <Calendar size={12} className="mr-1" />
          {new Date(photo.created_at).toLocaleDateString('ru-RU')}
        </div>
        {photo.notes && (
          <div className="text-xs text-gray-600 mt-1 line-clamp-2">
            {photo.notes}
          </div>
        )}
      </div>
    </Card>
  );

  const ComparisonView = () => {
    if (photos.before.length === 0 && photos.after.length === 0) {
      return (
        <div className="text-center py-12">
          <ImageIcon size={48} className="mx-auto text-gray-300 mb-4" />
          <p className="text-gray-500">Нет фото для сравнения</p>
          <p className="text-sm text-gray-400">Загрузите фото "до" и "после" для сравнения</p>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* Режимы просмотра */}
        <div className="flex justify-center space-x-2">
          <Button
            variant={viewMode === 'split' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewMode('split')}
          >
            Раздельно
          </Button>
          <Button
            variant={viewMode === 'overlay' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewMode('overlay')}
          >
            Наложение
          </Button>
          <Button
            variant={viewMode === 'slider' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewMode('slider')}
          >
            Слайдер
          </Button>
        </div>

        {/* Сравнение фото */}
        {viewMode === 'split' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium mb-4 text-red-600">До лечения</h3>
              <div className="grid grid-cols-2 gap-4">
                {photos.before.map(photo => (
                  <PhotoCard
                    key={photo.id}
                    photo={photo}
                    category="before"
                    title={`Фото ${photos.before.indexOf(photo) + 1}`}
                  />
                ))}
              </div>
            </div>
            
            <div>
              <h3 className="text-lg font-medium mb-4 text-green-600">После лечения</h3>
              <div className="grid grid-cols-2 gap-4">
                {photos.after.map(photo => (
                  <PhotoCard
                    key={photo.id}
                    photo={photo}
                    category="after"
                    title={`Фото ${photos.after.indexOf(photo) + 1}`}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        {viewMode === 'overlay' && (
          <div className="relative">
            <div className="grid grid-cols-2 gap-4">
              {photos.before.slice(0, 1).map(photo => (
                <div key={photo.id} className="relative">
                  <img
                    src={photo.url}
                    alt="До"
                    className="w-full h-64 object-cover rounded-lg"
                  />
                  <div className="absolute top-2 left-2 bg-red-600 text-white px-2 py-1 rounded text-sm">
                    До
                  </div>
                </div>
              ))}
              {photos.after.slice(0, 1).map(photo => (
                <div key={photo.id} className="relative">
                  <img
                    src={photo.url}
                    alt="После"
                    className="w-full h-64 object-cover rounded-lg"
                  />
                  <div className="absolute top-2 left-2 bg-green-600 text-white px-2 py-1 rounded text-sm">
                    После
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {viewMode === 'slider' && (
          <div className="relative">
            <div className="relative h-64 overflow-hidden rounded-lg">
              <div className="absolute inset-0 flex">
                {photos.before.slice(0, 1).map(photo => (
                  <img
                    key={photo.id}
                    src={photo.url}
                    alt="До"
                    className="w-1/2 h-full object-cover"
                  />
                ))}
                {photos.after.slice(0, 1).map(photo => (
                  <img
                    key={photo.id}
                    src={photo.url}
                    alt="После"
                    className="w-1/2 h-full object-cover"
                  />
                ))}
              </div>
              
              {/* Слайдер */}
              <div className="absolute top-0 left-1/2 w-1 bg-white h-full transform -translate-x-1/2">
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center cursor-pointer">
                  <div className="w-4 h-4 border-l-2 border-r-2 border-gray-400"></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center">
            <Camera className="mr-2 text-orange-600" size={24} />
            Фото до/после
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Пациент: {patientName}
          </p>
        </div>
        
        <div className="flex space-x-2">
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
          >
            <Upload size={16} className="mr-2" />
            Загрузить фото
          </Button>
        </div>
      </div>

      {/* Скрытый input для загрузки */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const files = e.target.files;
          if (files.length > 0) {
            // Показываем диалог выбора категории
            const category = prompt('Выберите категорию:\n1 - До лечения\n2 - После лечения\n3 - Прогресс');
            const categoryMap = { '1': 'before', '2': 'after', '3': 'progress' };
            const selectedCategory = categoryMap[category] || 'before';
            handleFileUpload(files, selectedCategory);
          }
        }}
      />

      {/* Сообщения */}
      {message.text && (
        <div className={`p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.text}
        </div>
      )}

      {/* Сравнение фото */}
      <ComparisonView />

      {/* Прогресс лечения */}
      {photos.progress.length > 0 && (
        <div>
          <h3 className="text-lg font-medium mb-4 text-blue-600">Прогресс лечения</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {photos.progress.map(photo => (
              <PhotoCard
                key={photo.id}
                photo={photo}
                category="progress"
                title={`Прогресс ${photos.progress.indexOf(photo) + 1}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Полноэкранный просмотр */}
      {showFullscreen && selectedPhoto && (
        <div className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4">
          <div className="relative max-w-4xl max-h-full">
            <img
              src={selectedPhoto.url}
              alt="Фото"
              className="max-w-full max-h-full object-contain"
              style={{ transform: `scale(${zoom})` }}
            />
            
            {/* Элементы управления */}
            <div className="absolute top-4 right-4 flex space-x-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleZoom('out')}
                className="bg-white text-gray-900"
              >
                <ZoomOut size={16} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleZoom('in')}
                className="bg-white text-gray-900"
              >
                <ZoomIn size={16} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={resetZoom}
                className="bg-white text-gray-900"
              >
                <RotateCcw size={16} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowFullscreen(false)}
                className="bg-white text-gray-900"
              >
                <Minimize2 size={16} />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PhotoComparison;
