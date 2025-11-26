import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { 
  Upload, 
  Download, 
  Eye, 
  Edit, 
  Trash2, 
  Share2, 
  Search, 
  Filter, 
  Grid, 
  List, 
  Folder, 
  File, 
  Image, 
  FileText, 
  Video, 
  Music, 
  Archive,
  MoreVertical,
  Plus,
  RefreshCw,
  Settings,
  BarChart3,
  Upload as UploadIcon,
  Download as DownloadIcon,
  X,
  Check,
  AlertCircle,
  Clock,
  Shield,
  Users
} from 'lucide-react';

/**
 * Менеджер файлов
 * Полнофункциональное управление файлами с загрузкой, поиском и организацией
 */
const FileManager = () => {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [viewMode, setViewMode] = useState('grid'); // grid, list
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    fileType: '',
    permission: '',
    dateFrom: '',
    dateTo: '',
    sizeMin: '',
    sizeMax: ''
  });
  const [currentFolder, setCurrentFolder] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [stats, setStats] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  
  const fileInputRef = useRef(null);
  const uploadFormRef = useRef(null);

  useEffect(() => {
    loadFiles();
    loadFolders();
    loadStats();
  }, [currentFolder, searchQuery, filters]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (currentFolder) params.append('folder_id', currentFolder);
      if (filters.fileType) params.append('file_type', filters.fileType);
      if (filters.permission) params.append('permission', filters.permission);
      if (filters.dateFrom) params.append('date_from', filters.dateFrom);
      if (filters.dateTo) params.append('date_to', filters.dateTo);
      if (filters.sizeMin) params.append('size_min', filters.sizeMin);
      if (filters.sizeMax) params.append('size_max', filters.sizeMax);
      
      const response = await fetch(`/api/v1/files?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Ошибка загрузки файлов:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadFolders = async () => {
    try {
      // Здесь будет API для загрузки папок
      setFolders([]);
    } catch (error) {
      console.error('Ошибка загрузки папок:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/files/stats', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('file', file);
      formData.append('file_type', getFileType(file));
      formData.append('permission', 'private');
      
      if (currentFolder) {
        formData.append('folder_id', currentFolder);
      }

      try {
        const response = await fetch('/api/v1/files/upload', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
          body: formData
        });

        if (response.ok) {
          setUploadProgress(((i + 1) / files.length) * 100);
        } else {
          console.error(`Ошибка загрузки файла ${file.name}`);
        }
      } catch (error) {
        console.error(`Ошибка загрузки файла ${file.name}:`, error);
      }
    }

    setUploading(false);
    setUploadProgress(0);
    await loadFiles();
  };

  const getFileType = (file) => {
    const ext = file.name.split('.').pop().toLowerCase();
    const mimeType = file.type;
    
    if (mimeType.startsWith('image/')) return 'image';
    if (mimeType.startsWith('video/')) return 'video';
    if (mimeType.startsWith('audio/')) return 'audio';
    if (['pdf', 'doc', 'docx', 'txt'].includes(ext)) return 'document';
    if (['zip', 'rar', '7z'].includes(ext)) return 'archive';
    if (['dcm', 'dicom'].includes(ext)) return 'xray';
    
    return 'other';
  };

  const getFileIcon = (file) => {
    switch (file.file_type) {
      case 'image': return <Image className="w-6 h-6 text-green-600" />;
      case 'video': return <Video className="w-6 h-6 text-purple-600" />;
      case 'audio': return <Music className="w-6 h-6 text-blue-600" />;
      case 'document': return <FileText className="w-6 h-6 text-orange-600" />;
      case 'archive': return <Archive className="w-6 h-6 text-gray-600" />;
      case 'xray': return <Image className="w-6 h-6 text-red-600" />;
      default: return <File className="w-6 h-6 text-gray-600" />;
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleDownload = async (fileId, filename) => {
    try {
      const response = await fetch(`/api/v1/files/${fileId}/download`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Ошибка скачивания файла:', error);
    }
  };

  const handlePreview = async (fileId) => {
    try {
      const response = await fetch(`/api/v1/files/${fileId}/preview`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
      }
    } catch (error) {
      console.error('Ошибка предварительного просмотра:', error);
    }
  };

  const handleDelete = async (fileId) => {
    if (!confirm('Вы уверены, что хотите удалить этот файл?')) return;

    try {
      const response = await fetch(`/api/v1/files/${fileId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });

      if (response.ok) {
        await loadFiles();
      }
    } catch (error) {
      console.error('Ошибка удаления файла:', error);
    }
  };

  const handleSearch = (query) => {
    setSearchQuery(query);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      fileType: '',
      permission: '',
      dateFrom: '',
      dateTo: '',
      sizeMin: '',
      sizeMax: ''
    });
    setSearchQuery('');
  };

  const renderFileGrid = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {files.map(file => (
        <div
          key={file.id}
          className={`bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer ${
            selectedFiles.includes(file.id) ? 'ring-2 ring-blue-500' : ''
          }`}
          onClick={() => {
            if (selectedFiles.includes(file.id)) {
              setSelectedFiles(prev => prev.filter(id => id !== file.id));
            } else {
              setSelectedFiles(prev => [...prev, file.id]);
            }
          }}
        >
          <div className="flex flex-col items-center text-center">
            <div className="mb-3">
              {getFileIcon(file)}
            </div>
            <h3 className="font-medium text-sm text-gray-900 truncate w-full mb-1">
              {file.title || file.filename}
            </h3>
            <p className="text-xs text-gray-500 mb-2">
              {formatFileSize(file.file_size)}
            </p>
            <p className="text-xs text-gray-400">
              {formatDate(file.created_at)}
            </p>
          </div>
          
          <div className="mt-3 flex justify-center space-x-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                handlePreview(file.id);
              }}
              className="p-1 text-gray-400 hover:text-blue-600"
              title="Предварительный просмотр"
            >
              <Eye className="w-4 h-4" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDownload(file.id, file.filename);
              }}
              className="p-1 text-gray-400 hover:text-green-600"
              title="Скачать"
            >
              <Download className="w-4 h-4" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(file.id);
              }}
              className="p-1 text-gray-400 hover:text-red-600"
              title="Удалить"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderFileList = () => (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              <input
                type="checkbox"
                className="rounded border-gray-300"
                checked={selectedFiles.length === files.length && files.length > 0}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedFiles(files.map(f => f.id));
                  } else {
                    setSelectedFiles([]);
                  }
                }}
              />
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Имя файла
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Тип
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Размер
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Дата создания
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Действия
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {files.map(file => (
            <tr key={file.id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="checkbox"
                  className="rounded border-gray-300"
                  checked={selectedFiles.includes(file.id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedFiles(prev => [...prev, file.id]);
                    } else {
                      setSelectedFiles(prev => prev.filter(id => id !== file.id));
                    }
                  }}
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="flex-shrink-0 mr-3">
                    {getFileIcon(file)}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {file.title || file.filename}
                    </div>
                    <div className="text-sm text-gray-500">
                      {file.original_filename}
                    </div>
                  </div>
                </div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {file.file_type}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {formatFileSize(file.file_size)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {formatDate(file.created_at)}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <div className="flex space-x-2">
                  <button
                    onClick={() => handlePreview(file.id)}
                    className="text-blue-600 hover:text-blue-900"
                    title="Предварительный просмотр"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDownload(file.id, file.filename)}
                    className="text-green-600 hover:text-green-900"
                    title="Скачать"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(file.id)}
                    className="text-red-600 hover:text-red-900"
                    title="Удалить"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Заголовок и действия */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Файловый менеджер</h2>
          <p className="text-gray-600">Управление файлами и документами</p>
        </div>
        
        <div className="mt-4 sm:mt-0 flex space-x-3">
          <button
            onClick={() => setShowStatsModal(true)}
            className="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors flex items-center"
          >
            <BarChart3 className="w-4 h-4 mr-2" />
            Статистика
          </button>
          
          <button
            onClick={() => setShowUploadModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors flex items-center"
          >
            <Upload className="w-4 h-4 mr-2" />
            Загрузить
          </button>
        </div>
      </div>

      {/* Поиск и фильтры */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
          <div className="flex-1 max-w-lg">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Поиск файлов..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <select
              value={filters.fileType}
              onChange={(e) => handleFilterChange('fileType', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Все типы</option>
              <option value="image">Изображения</option>
              <option value="video">Видео</option>
              <option value="audio">Аудио</option>
              <option value="document">Документы</option>
              <option value="archive">Архивы</option>
              <option value="xray">Рентген</option>
            </select>
            
            <select
              value={filters.permission}
              onChange={(e) => handleFilterChange('permission', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Все права</option>
              <option value="public">Публичные</option>
              <option value="private">Приватные</option>
              <option value="restricted">Ограниченные</option>
              <option value="confidential">Конфиденциальные</option>
            </select>
            
            <button
              onClick={clearFilters}
              className="px-3 py-2 text-gray-600 hover:text-gray-800 transition-colors"
            >
              Очистить
            </button>
          </div>
        </div>
      </div>

      {/* Панель инструментов */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg ${viewMode === 'grid' ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}
            >
              <Grid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg ${viewMode === 'list' ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
          
          {selectedFiles.length > 0 && (
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
                Выбрано: {selectedFiles.length}
              </span>
              <button
                onClick={() => setSelectedFiles([])}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Отменить
              </button>
            </div>
          )}
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={loadFiles}
            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
            title="Обновить"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Список файлов */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : files.length === 0 ? (
        <div className="text-center py-12">
          <File className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Файлы не найдены</h3>
          <p className="text-gray-600 mb-4">Загрузите файлы или измените фильтры поиска</p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Загрузить файлы
          </button>
        </div>
      ) : (
        viewMode === 'grid' ? renderFileGrid() : renderFileList()
      )}

      {/* Модальное окно загрузки */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Загрузить файлы</h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <UploadIcon className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600">Нажмите для выбора файлов или перетащите их сюда</p>
                <p className="text-sm text-gray-500 mt-1">Поддерживаются все типы файлов</p>
              </div>
              
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileUpload}
                className="hidden"
              />
              
              {uploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Загрузка файлов...</span>
                    <span>{Math.round(uploadProgress)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setShowUploadModal(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно статистики */}
      {showStatsModal && stats && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Статистика файлов</h3>
              <button
                onClick={() => setShowStatsModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-blue-600">Всего файлов</p>
                      <p className="text-2xl font-bold text-blue-900">{stats.total_files}</p>
                    </div>
                    <File className="w-8 h-8 text-blue-600" />
                  </div>
                </div>
                
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-green-600">Общий размер</p>
                      <p className="text-2xl font-bold text-green-900">{formatFileSize(stats.total_size)}</p>
                    </div>
                    <BarChart3 className="w-8 h-8 text-green-600" />
                  </div>
                </div>
              </div>
              
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">По типам файлов</h4>
                  <div className="space-y-2">
                    {Object.entries(stats.files_by_type || {}).map(([type, count]) => (
                      <div key={type} className="flex justify-between items-center">
                        <span className="text-sm text-gray-600 capitalize">{type}</span>
                        <span className="text-sm font-medium text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Использование хранилища</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Использовано</span>
                      <span className="text-sm font-medium text-gray-900">
                        {formatFileSize(stats.storage_usage?.used_bytes || 0)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-gray-600">Максимум</span>
                      <span className="text-sm font-medium text-gray-900">
                        {formatFileSize(stats.storage_usage?.max_bytes || 0)}
                      </span>
                    </div>
                    {stats.storage_usage?.max_bytes && (
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{
                            width: `${((stats.storage_usage.used_bytes || 0) / stats.storage_usage.max_bytes) * 100}%`
                          }}
                        ></div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex justify-end mt-6">
              <button
                onClick={() => setShowStatsModal(false)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileManager;


