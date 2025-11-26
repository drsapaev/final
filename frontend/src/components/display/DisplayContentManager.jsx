import React, { useState, useEffect } from 'react';
import { 
  Image, 
  Video, 
  FileText, 
  Plus, 
  Trash2, 
  Edit,
  Eye,
  Upload,
  Play,
  Pause,
  Volume2,
  Monitor
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

/**
 * Управление контентом для табло
 * Основа: passport.md стр. 2571-3324
 */
const DisplayContentManager = ({ 
  boardId,
  onContentUpdate,
  className = ''
}) => {
  const [activeTab, setActiveTab] = useState('banners');
  const [content, setContent] = useState({
    banners: [],
    announcements: [],
    videos: [],
    themes: []
  });
  const [loading, setLoading] = useState(false);
  const [uploadDialog, setUploadDialog] = useState({ open: false, type: '' });

  const contentTabs = [
    { id: 'banners', label: 'Баннеры', icon: Image, color: 'text-blue-600' },
    { id: 'announcements', label: 'Объявления', icon: FileText, color: 'text-green-600' },
    { id: 'videos', label: 'Видео', icon: Video, color: 'text-purple-600' },
    { id: 'themes', label: 'Темы', icon: Monitor, color: 'text-gray-600' }
  ];

  useEffect(() => {
    loadContent();
  }, [boardId]);

  const loadContent = async () => {
    try {
      setLoading(true);
      
      // Загружаем контент для табло
      const response = await fetch(`/api/v1/admin/display-boards/${boardId}/content`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        const data = await response.json();
        setContent(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки контента:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file, contentType) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('content_type', contentType);
      formData.append('board_id', boardId);

      const response = await fetch('/api/v1/admin/display-boards/content/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        body: formData
      });

      if (response.ok) {
        await loadContent();
        setUploadDialog({ open: false, type: '' });
      }
    } catch (error) {
      console.error('Ошибка загрузки файла:', error);
    }
  };

  const handleDeleteContent = async (contentId, contentType) => {
    try {
      const response = await fetch(`/api/v1/admin/display-boards/content/${contentId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        await loadContent();
      }
    } catch (error) {
      console.error('Ошибка удаления контента:', error);
    }
  };

  const renderBannersTab = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Баннеры и изображения</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'banner' })}>
          <Plus size={16} className="mr-2" />
          Добавить баннер
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {content.banners.map(banner => (
          <Card key={banner.id} className="overflow-hidden">
            <div className="aspect-video bg-gray-100 flex items-center justify-center">
              {banner.file_url ? (
                <img 
                  src={banner.file_url} 
                  alt={banner.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Image size={48} className="text-gray-400" />
              )}
            </div>
            <div className="p-3">
              <div className="font-medium text-sm mb-1">{banner.title}</div>
              <div className="text-xs text-gray-500 mb-2">{banner.description}</div>
              <div className="flex justify-between items-center">
                <Badge variant={banner.active ? 'success' : 'secondary'} size="sm">
                  {banner.active ? 'Активен' : 'Неактивен'}
                </Badge>
                <div className="flex space-x-1">
                  <Button size="sm" variant="outline">
                    <Eye size={12} />
                  </Button>
                  <Button size="sm" variant="outline">
                    <Edit size={12} />
                  </Button>
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => handleDeleteContent(banner.id, 'banner')}
                  >
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderAnnouncementsTab = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Текстовые объявления</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'announcement' })}>
          <Plus size={16} className="mr-2" />
          Добавить объявление
        </Button>
      </div>

      <div className="space-y-3">
        {content.announcements.map(announcement => (
          <Card key={announcement.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="font-medium mb-2">{announcement.title}</div>
                <div className="text-gray-600 text-sm mb-3">{announcement.text}</div>
                <div className="flex items-center space-x-3">
                  <Badge 
                    variant={
                      announcement.priority === 'high' ? 'error' :
                      announcement.priority === 'medium' ? 'warning' : 'info'
                    } 
                    size="sm"
                  >
                    {announcement.priority === 'high' ? 'Важное' :
                     announcement.priority === 'medium' ? 'Среднее' : 'Обычное'}
                  </Badge>
                  <span className="text-xs text-gray-500">
                    Создано: {new Date(announcement.created_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              </div>
              <div className="flex space-x-2 ml-4">
                <Button size="sm" variant="outline">
                  <Edit size={14} />
                </Button>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => handleDeleteContent(announcement.id, 'announcement')}
                >
                  <Trash2 size={14} />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderVideosTab = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Видео контент</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'video' })}>
          <Plus size={16} className="mr-2" />
          Добавить видео
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {content.videos.map(video => (
          <Card key={video.id} className="overflow-hidden">
            <div className="aspect-video bg-gray-900 flex items-center justify-center relative">
              {video.thumbnail_url ? (
                <img 
                  src={video.thumbnail_url} 
                  alt={video.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Video size={48} className="text-gray-400" />
              )}
              <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                <Play size={32} className="text-white" />
              </div>
            </div>
            <div className="p-3">
              <div className="font-medium text-sm mb-1">{video.title}</div>
              <div className="text-xs text-gray-500 mb-2">
                Длительность: {video.duration || 'Не указано'}
              </div>
              <div className="flex justify-between items-center">
                <Badge variant={video.active ? 'success' : 'secondary'} size="sm">
                  {video.active ? 'Показывается' : 'Неактивен'}
                </Badge>
                <div className="flex space-x-1">
                  <Button size="sm" variant="outline">
                    <Play size={12} />
                  </Button>
                  <Button size="sm" variant="outline">
                    <Edit size={12} />
                  </Button>
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => handleDeleteContent(video.id, 'video')}
                  >
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderThemesTab = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Темы оформления</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { id: 'light', name: 'Светлая', preview: '#f8fafc' },
          { id: 'dark', name: 'Темная', preview: '#1a202c' },
          { id: 'medical', name: 'Медицинская', preview: '#f0fff4' }
        ].map(theme => (
          <Card key={theme.id} className="cursor-pointer hover:shadow-lg transition-shadow">
            <div 
              className="h-24 rounded-t-lg"
              style={{ background: theme.preview }}
            />
            <div className="p-3">
              <div className="font-medium">{theme.name}</div>
              <div className="text-sm text-gray-500">Тема {theme.id}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Управление контентом табло</h2>
        <Badge variant="info">
          Табло: {boardId}
        </Badge>
      </div>

      {/* Вкладки */}
      <div className="flex space-x-1 border-b border-gray-200">
        {contentTabs.map(tab => {
          const isActive = activeTab === tab.id;
          const TabIcon = tab.icon;
          
          return (
            <button
              key={tab.id}
              className={`flex items-center px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700 border-b-2 border-blue-500'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              <TabIcon size={16} className="mr-2" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент вкладок */}
      <div>
        {activeTab === 'banners' && renderBannersTab()}
        {activeTab === 'announcements' && renderAnnouncementsTab()}
        {activeTab === 'videos' && renderVideosTab()}
        {activeTab === 'themes' && renderThemesTab()}
      </div>

      {/* Диалог загрузки */}
      {uploadDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <div className="p-6">
              <h3 className="text-lg font-medium mb-4">
                Загрузить {uploadDialog.type === 'banner' ? 'баннер' : 
                          uploadDialog.type === 'video' ? 'видео' : 'контент'}
              </h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Название:
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Введите название..."
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Файл:
                  </label>
                  <input
                    type="file"
                    accept={
                      uploadDialog.type === 'banner' ? 'image/*' :
                      uploadDialog.type === 'video' ? 'video/*' : '*/*'
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              
              <div className="flex justify-end space-x-3 mt-6">
                <Button 
                  variant="outline" 
                  onClick={() => setUploadDialog({ open: false, type: '' })}
                >
                  Отменить
                </Button>
                <Button onClick={() => {/* Логика загрузки */}}>
                  <Upload size={16} className="mr-2" />
                  Загрузить
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default DisplayContentManager;


