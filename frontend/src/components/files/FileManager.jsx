import { api } from '../../api/client';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Archive,
  BarChart3,
  Download,
  Eye,
  File,
  FileText,
  Grid,
  Image,
  List as ListIcon,
  Music,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  Upload as UploadIcon,
  Video,
  X
} from 'lucide-react';

import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';
import { tokenManager } from '../../utils/tokenManager';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import {
  AppEmpty,
  AppLoading,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Table,
  Progress,
  SegmentedControl,
  Select,
} from '../ui/macos';

const pageStyles = {
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
  width: '100%',
  minWidth: 0,
  padding: 'clamp(12px, 2vw, 20px)'
};

const headerStyles = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: '12px',
  flexWrap: 'wrap'
};

const toolbarStyles = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '12px',
  flexWrap: 'wrap'
};

const filterGridStyles = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))',
  gap: '10px',
  alignItems: 'end'
};

const fileGridStyles = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: '12px'
};

const iconButtonStyle = {
  width: '32px',
  height: '32px',
  padding: 0
};

const fileTypeOptions = [
  { value: '', label: 'Все типы' },
  { value: 'image', label: 'Изображения' },
  { value: 'video', label: 'Видео' },
  { value: 'audio', label: 'Аудио' },
  { value: 'document', label: 'Документы' },
  { value: 'archive', label: 'Архивы' },
  { value: 'xray', label: 'Рентген' }
];

const permissionOptions = [
  { value: '', label: 'Все права' },
  { value: 'public', label: 'Публичные' },
  { value: 'private', label: 'Приватные' },
  { value: 'restricted', label: 'Ограниченные' },
  { value: 'confidential', label: 'Конфиденциальные' }
];

const fileTypeLabels = {
  image: 'Изображение',
  video: 'Видео',
  audio: 'Аудио',
  document: 'Документ',
  archive: 'Архив',
  xray: 'Рентген',
  other: 'Файл'
};

const fileTypeColors = {
  image: 'var(--mac-success)',
  video: 'var(--mac-accent-purple)',
  audio: 'var(--mac-accent-blue)',
  document: '#ff9500',
  archive: 'var(--mac-text-tertiary)',
  xray: '#ff3b30',
  other: 'var(--mac-text-tertiary)'
};

const FileManager = () => {
  useTheme();
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [, setFolders] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [viewMode, setViewMode] = useState('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    fileType: '',
    permission: '',
    dateFrom: '',
    dateTo: '',
    sizeMin: '',
    sizeMax: ''
  });
  const [currentFolder] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [stats, setStats] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef(null);

  const loadFolders = useCallback(async () => {
    try {
      setFolders([]);
    } catch (error) {
      logger.error('Ошибка загрузки папок:', error);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/files/statistics', {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      setStats(data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    }
  }, []);

  const loadFiles = useCallback(async () => {
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
      if (searchQuery) params.append('search', searchQuery);

      const query = params.toString();
      const response = await fetch(`/api/v1/files/${query ? `?${query}` : ''}`, {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      logger.error('Ошибка загрузки файлов:', error);
    } finally {
      setLoading(false);
    }
  }, [currentFolder, filters, searchQuery]);

  useEffect(() => {
    loadFiles();
    loadFolders();
    loadStats();
  }, [loadFiles, loadFolders, loadStats]);

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

  const getFileIcon = (file, size = 24) => {
    const color = fileTypeColors[file.file_type] || fileTypeColors.other;
    const iconProps = { size, style: { color } };

    switch (file.file_type) {
      case 'image':
      case 'xray':
        return <Image {...iconProps} />;
      case 'video':
        return <Video {...iconProps} />;
      case 'audio':
        return <Music {...iconProps} />;
      case 'document':
        return <FileText {...iconProps} />;
      case 'archive':
        return <Archive {...iconProps} />;
      default:
        return <File {...iconProps} />;
    }
  };

  const getFileDisplayName = (file) => file.title || file.filename || file.original_filename || 'Файл';

  const formatFileSize = (bytes) => {
    const size = Number(bytes) || 0;
    if (size === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(size) / Math.log(k)), sizes.length - 1);
    return `${parseFloat((size / Math.pow(k, index)).toFixed(2))} ${sizes[index]}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Не указано';
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return 'Не указано';

    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleFileUpload = async (event) => {
    const uploadFiles = Array.from(event.target.files || []);
    if (uploadFiles.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    for (let index = 0; index < uploadFiles.length; index += 1) {
      const file = uploadFiles[index];
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
          headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` },
          body: formData
        });

        if (response.ok) {
          setUploadProgress(((index + 1) / uploadFiles.length) * 100);
        } else {
          logger.error(`Ошибка загрузки файла ${file.name}`);
        }
      } catch (error) {
        logger.error(`Ошибка загрузки файла ${file.name}:`, error);
      }
    }

    event.target.value = '';
    setUploading(false);
    setUploadProgress(0);
    await loadFiles();
    await loadStats();
  };

  const handleDownload = async (fileId, filename) => {
    try {
      const response = await fetch(`/api/v1/files/${fileId}/download`, {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename || 'file';
        document.body.appendChild(link);
        link.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(link);
      }
    } catch (error) {
      logger.error('Ошибка скачивания файла:', error);
    }
  };

  const handlePreview = async (fileId) => {
    try {
      const response = await fetch(`/api/v1/files/${fileId}/preview`, {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
      }
    } catch (error) {
      logger.error('Ошибка предварительного просмотра:', error);
    }
  };

  const handleDelete = async (fileId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление файла',
      message: 'Удалить этот файл?',
      description: 'Это действие необратимо.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) return;

    try {
      const response = await fetch(`/api/v1/files/${fileId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        setSelectedFiles((prev) => prev.filter((id) => id !== fileId));
        await loadFiles();
        await loadStats();
      }
    } catch (error) {
      logger.error('Ошибка удаления файла:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
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

  const toggleFileSelection = (fileId) => {
    setSelectedFiles((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    );
  };

  const handleActivationKeyDown = (event, action) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  const selectedCount = selectedFiles.length;

  const renderFileActions = (file) => (
    <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
      <Button
        variant="ghost"
        size="small"
        onClick={(event) => {
          event.stopPropagation();
          handlePreview(file.id);
        }}
        aria-label={`Предварительный просмотр файла ${getFileDisplayName(file)}`}
        title="Предварительный просмотр"
        style={iconButtonStyle}
      >
        <Eye size={16} />
      </Button>
      <Button
        variant="ghost"
        size="small"
        onClick={(event) => {
          event.stopPropagation();
          handleDownload(file.id, file.filename);
        }}
        aria-label={`Скачать файл ${getFileDisplayName(file)}`}
        title="Скачать"
        style={iconButtonStyle}
      >
        <Download size={16} />
      </Button>
      <Button
        variant="ghost"
        size="small"
        onClick={(event) => {
          event.stopPropagation();
          handleDelete(file.id);
        }}
        aria-label={`Удалить файл ${getFileDisplayName(file)}`}
        title="Удалить"
        style={{ ...iconButtonStyle, color: 'var(--mac-danger)' }}
      >
        <Trash2 size={16} />
      </Button>
    </div>
  );

  const renderFileGrid = () => (
    <div style={fileGridStyles}>
      {files.map((file) => {
        const isSelected = selectedFiles.includes(file.id);
        return (
          <Card
            key={file.id}
            padding="small"
            role="button"
            tabIndex={0}
            onClick={() => toggleFileSelection(file.id)}
            onKeyDown={(event) => handleActivationKeyDown(event, () => toggleFileSelection(file.id))}
            style={{
              minHeight: '184px',
              borderColor: isSelected ? 'var(--mac-accent-blue)' : 'var(--mac-card-border, var(--mac-border))',
              boxShadow: isSelected ? '0 0 0 3px rgba(0, 122, 255, 0.18)' : 'var(--mac-shadow-sm)'
            }}
          >
            <CardContent
              style={{
                display: 'flex',
                height: '100%',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <div
                  style={{
                    display: 'flex',
                    width: '38px',
                    height: '38px',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '8px',
                    background: 'var(--mac-bg-secondary)'
                  }}
                >
                  {getFileIcon(file, 24)}
                </div>
                <div style={{ minWidth: 0 }}>
                  <h3
                    style={{
                      margin: 0,
                      fontSize: '14px',
                      color: 'var(--mac-text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                    title={getFileDisplayName(file)}
                  >
                    {getFileDisplayName(file)}
                  </h3>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
                    {formatFileSize(file.file_size)}
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                <Badge size="small" variant="outline">
                  {fileTypeLabels[file.file_type] || file.file_type || 'Файл'}
                </Badge>
                <span style={{ fontSize: '11px', color: 'var(--mac-text-tertiary)' }}>
                  {formatDate(file.created_at)}
                </span>
              </div>

              {renderFileActions(file)}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );

  const tableColumns = [
    {
      key: 'selected',
      title: (
        <Checkbox
          checked={files.length > 0 && selectedFiles.length === files.length}
          onChange={(checked) => setSelectedFiles(checked ? files.map((file) => file.id) : [])}
          aria-label={files.length > 0 && selectedFiles.length === files.length ? 'Снять выбор со всех файлов' : 'Выбрать все файлы'}
        />
      ),
      render: (_value, file) => (
        <Checkbox
          checked={selectedFiles.includes(file.id)}
          onChange={(checked) =>
            setSelectedFiles((prev) => (checked ? [...prev, file.id] : prev.filter((id) => id !== file.id)))
          }
          aria-label={selectedFiles.includes(file.id) ? `Снять выбор файла ${getFileDisplayName(file)}` : `Выбрать файл ${getFileDisplayName(file)}`}
        />
      )
    },
    {
      key: 'filename',
      title: 'Имя файла',
      render: (_value, file) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: '220px' }}>
          {getFileIcon(file, 22)}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, color: 'var(--mac-text-primary)' }}>{getFileDisplayName(file)}</div>
            {file.original_filename && (
              <div style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>{file.original_filename}</div>
            )}
          </div>
        </div>
      )
    },
    {
      key: 'file_type',
      title: 'Тип',
      render: (value) => <Badge size="small" variant="outline">{fileTypeLabels[value] || value || 'Файл'}</Badge>
    },
    {
      key: 'file_size',
      title: 'Размер',
      render: (value) => formatFileSize(value)
    },
    {
      key: 'created_at',
      title: 'Дата создания',
      render: (value) => formatDate(value)
    },
    {
      key: 'actions',
      title: 'Действия',
      render: (_value, file) => renderFileActions(file)
    }
  ];

  const renderFileList = () => (
    <Table
      columns={tableColumns}
      data={files}
      sortable={false}
      emptyState="Файлы не найдены"
    />
  );

  return (
    <div style={pageStyles}>
      <div style={headerStyles}>
        <div>
          <h1 style={{ margin: 0, fontSize: '28px', lineHeight: 1.15, color: 'var(--mac-text-primary)' }}>
            Файловый менеджер
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--mac-text-secondary)', fontSize: '14px' }}>
            Управление файлами и документами
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Button variant="secondary" onClick={() => setShowStatsModal(true)}>
            <BarChart3 size={16} />
            Статистика
          </Button>
          <Button variant="primary" onClick={() => setShowUploadModal(true)}>
            <Upload size={16} />
            Загрузить
          </Button>
        </div>
      </div>

      <Card padding="small" shadow="small">
        <CardContent>
          <div style={filterGridStyles}>
            <div style={{ position: 'relative', minWidth: 0 }}>
              <Search
                aria-hidden="true"
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)',
                  zIndex: 2
                }}
              />
              <Input
                aria-label="Поиск файлов"
                placeholder="Поиск файлов..."
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                style={{ width: '100%', paddingLeft: '36px', boxSizing: 'border-box' }}
              />
            </div>
            <Select
              aria-label="Фильтр файлов по типу"
              value={filters.fileType}
              onChange={(value) => handleFilterChange('fileType', value)}
              options={fileTypeOptions}
            />
            <Select
              aria-label="Фильтр файлов по правам доступа"
              value={filters.permission}
              onChange={(value) => handleFilterChange('permission', value)}
              options={permissionOptions}
            />
            <Button variant="secondary" onClick={clearFilters}>
              Очистить
            </Button>
          </div>
        </CardContent>
      </Card>

      <div style={toolbarStyles}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <SegmentedControl
            value={viewMode}
            onChange={setViewMode}
            options={[
              { value: 'grid', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}><Grid size={14} />Плитка</span> },
              { value: 'list', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}><ListIcon size={14} />Список</span> }
            ]}
          />

          {selectedCount > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--mac-text-secondary)' }}>
              <span style={{ fontSize: '13px' }}>Выбрано: {selectedCount}</span>
              <Button size="small" variant="ghost" onClick={() => setSelectedFiles([])}>
                Отменить
              </Button>
            </div>
          )}
        </div>

        <Button
          variant="ghost"
          size="small"
          onClick={loadFiles}
          aria-label="Обновить список файлов"
          title="Обновить"
          style={iconButtonStyle}
        >
          <RefreshCw size={16} />
        </Button>
      </div>

      {loading ? (
        <Card padding="small">
          <AppLoading title="Загрузка файлов..." />
        </Card>
      ) : files.length === 0 ? (
        <Card padding="small">
          <AppEmpty
            icon={File}
            title="Файлы не найдены"
            description="Загрузите файлы или измените фильтры поиска"
            action={<Button variant="primary" onClick={() => setShowUploadModal(true)}>Загрузить файлы</Button>}
          />
        </Card>
      ) : viewMode === 'grid' ? (
        renderFileGrid()
      ) : (
        renderFileList()
      )}

      <Dialog open={showUploadModal} onClose={() => setShowUploadModal(false)} maxWidth="sm">
        <DialogTitle style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <span>Загрузить файлы</span>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setShowUploadModal(false)}
            aria-label="Закрыть окно загрузки файлов"
            style={iconButtonStyle}
          >
            <X size={16} />
          </Button>
        </DialogTitle>
        <DialogContent>
          <div
            role="button"
            tabIndex={0}
            aria-label="Выбрать файлы для загрузки"
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => handleActivationKeyDown(event, () => fileInputRef.current?.click())}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              padding: '28px 18px',
              border: '1px dashed var(--mac-border)',
              borderRadius: '10px',
              background: 'var(--mac-bg-secondary)',
              textAlign: 'center',
              cursor: 'pointer'
            }}
          >
            <UploadIcon size={32} style={{ color: 'var(--mac-text-tertiary)' }} />
            <strong style={{ color: 'var(--mac-text-primary)' }}>Нажмите для выбора файлов</strong>
            <span style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
              Поддерживаются все типы файлов
            </span>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            aria-label="Файлы для загрузки"
            multiple
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />

          {uploading && (
            <div style={{ marginTop: '16px', display: 'grid', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                <span>Загрузка файлов...</span>
                <span>{Math.round(uploadProgress)}%</span>
              </div>
              <Progress value={uploadProgress} variant="primary" />
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="secondary" onClick={() => setShowUploadModal(false)}>
            Отмена
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={showStatsModal} onClose={() => setShowStatsModal(false)} maxWidth="md">
        <DialogTitle style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <span>Статистика файлов</span>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setShowStatsModal(false)}
            aria-label="Закрыть статистику файлов"
            style={iconButtonStyle}
          >
            <X size={16} />
          </Button>
        </DialogTitle>
        <DialogContent>
          {!stats ? (
            <AppLoading title="Загрузка статистики..." />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <Card padding="small" shadow="small">
                <CardHeader>
                  <CardTitle>Всего файлов</CardTitle>
                  <CardDescription>Количество загруженных документов</CardDescription>
                </CardHeader>
                <CardContent style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '26px' }}>{stats.total_files || 0}</strong>
                  <File size={30} style={{ color: 'var(--mac-accent-blue)' }} />
                </CardContent>
              </Card>

              <Card padding="small" shadow="small">
                <CardHeader>
                  <CardTitle>Общий размер</CardTitle>
                  <CardDescription>Использовано в хранилище</CardDescription>
                </CardHeader>
                <CardContent style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '26px' }}>{formatFileSize(stats.total_size)}</strong>
                  <BarChart3 size={30} style={{ color: 'var(--mac-success)' }} />
                </CardContent>
              </Card>

              <Card padding="small" shadow="small">
                <CardHeader>
                  <CardTitle>По типам файлов</CardTitle>
                </CardHeader>
                <CardContent style={{ display: 'grid', gap: '8px' }}>
                  {Object.entries(stats.files_by_type || {}).length === 0 ? (
                    <span style={{ color: 'var(--mac-text-secondary)' }}>Нет данных</span>
                  ) : (
                    Object.entries(stats.files_by_type || {}).map(([type, count]) => (
                      <div key={type} style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>{fileTypeLabels[type] || type}</span>
                        <strong>{count}</strong>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <Card padding="small" shadow="small">
                <CardHeader>
                  <CardTitle>Использование хранилища</CardTitle>
                </CardHeader>
                <CardContent style={{ display: 'grid', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                    <span style={{ color: 'var(--mac-text-secondary)' }}>Использовано</span>
                    <strong>{formatFileSize(stats.storage_usage?.used_bytes || 0)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                    <span style={{ color: 'var(--mac-text-secondary)' }}>Максимум</span>
                    <strong>{formatFileSize(stats.storage_usage?.max_bytes || 0)}</strong>
                  </div>
                  {stats.storage_usage?.max_bytes && (
                    <Progress
                      value={(stats.storage_usage.used_bytes || 0) / stats.storage_usage.max_bytes * 100}
                      variant="primary"
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="primary" onClick={() => setShowStatsModal(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>
  );
};

export default FileManager;
