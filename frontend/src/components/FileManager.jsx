import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Avatar,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Breadcrumbs,
  Link,
  InputAdornment,
  Menu,
  MenuItem,
  LinearProgress,
  Tooltip
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Search,
  Refresh,
  Upload,
  Download,
  Folder,
  InsertDriveFile,
  Image,
  VideoFile,
  AudioFile,
  Description,
  PictureAsPdf,
  Archive,
  Code,
  MoreVert,
  Visibility,
  Share,
  Copy,
  Move,
  CreateNewFolder,
  CloudUpload,
  CloudDownload,
  Storage,
  GetApp
} from '@mui/icons-material';

const FileManager = () => {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid, list
  const [currentPath, setCurrentPath] = useState('/');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [showCreateFolderDialog, setShowCreateFolderDialog] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [newFolderName, setNewFolderName] = useState('');
  const [anchorEl, setAnchorEl] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const fileTypes = {
    image: { icon: <Image />, color: 'success' },
    video: { icon: <VideoFile />, color: 'primary' },
    audio: { icon: <AudioFile />, color: 'info' },
    pdf: { icon: <PictureAsPdf />, color: 'error' },
    archive: { icon: <Archive />, color: 'warning' },
    code: { icon: <Code />, color: 'secondary' },
    document: { icon: <Description />, color: 'default' },
    folder: { icon: <Folder />, color: 'warning' },
    default: { icon: <InsertDriveFile />, color: 'default' }
  };

  useEffect(() => {
    loadFiles();
  }, [currentPath]);

  const loadFiles = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/files/?path=${encodeURIComponent(currentPath)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.files || data || []);
      } else {
        setError('Ошибка загрузки файлов');
      }
    } catch (err) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files.length) return;

    try {
      setUploadProgress(0);
      const formData = new FormData();
      
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      formData.append('path', currentPath);

      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      if (response.ok) {
        setSuccess('Файлы успешно загружены');
        loadFiles();
        setShowUploadDialog(false);
      } else {
        setError('Ошибка загрузки файлов');
      }
    } catch (err) {
      setError('Ошибка загрузки файлов');
    }
  };

  const handleCreateFolder = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/files/create-folder', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newFolderName,
          path: currentPath
        })
      });

      if (response.ok) {
        setSuccess('Папка успешно создана');
        loadFiles();
        setShowCreateFolderDialog(false);
        setNewFolderName('');
      } else {
        setError('Ошибка создания папки');
      }
    } catch (err) {
      setError('Ошибка создания папки');
    }
  };

  const handleFileDownload = async (file) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/files/download/${file.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = file.name;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        setError('Ошибка скачивания файла');
      }
    } catch (err) {
      setError('Ошибка скачивания файла');
    }
  };

  const handleFileDelete = async (file) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/files/${file.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setSuccess('Файл успешно удален');
        loadFiles();
      } else {
        setError('Ошибка удаления файла');
      }
    } catch (err) {
      setError('Ошибка удаления файла');
    }
  };

  const handleFolderClick = (folder) => {
    const newPath = currentPath === '/' ? `/${folder.name}` : `${currentPath}/${folder.name}`;
    setCurrentPath(newPath);
  };

  const handleBreadcrumbClick = (index) => {
    const pathParts = currentPath.split('/').filter(part => part);
    const newPath = '/' + pathParts.slice(0, index + 1).join('/');
    setCurrentPath(newPath);
  };

  const getFileType = (fileName) => {
    const extension = fileName.split('.').pop()?.toLowerCase();
    
    if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg'].includes(extension)) {
      return 'image';
    } else if (['mp4', 'avi', 'mov', 'wmv', 'flv'].includes(extension)) {
      return 'video';
    } else if (['mp3', 'wav', 'flac', 'aac'].includes(extension)) {
      return 'audio';
    } else if (extension === 'pdf') {
      return 'pdf';
    } else if (['zip', 'rar', '7z', 'tar', 'gz'].includes(extension)) {
      return 'archive';
    } else if (['js', 'ts', 'py', 'java', 'cpp', 'html', 'css'].includes(extension)) {
      return 'code';
    } else if (['doc', 'docx', 'txt', 'rtf'].includes(extension)) {
      return 'document';
    }
    
    return 'default';
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const filteredFiles = files.filter(file =>
    file.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const pathParts = currentPath.split('/').filter(part => part);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Заголовок */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Файловый менеджер
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<CreateNewFolder />}
            onClick={() => setShowCreateFolderDialog(true)}
            sx={{ mr: 1 }}
          >
            Создать папку
          </Button>
          <Button
            variant="contained"
            startIcon={<Upload />}
            onClick={() => setShowUploadDialog(true)}
          >
            Загрузить файлы
          </Button>
        </Box>
      </Box>

      {/* Алерты */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      {/* Навигация */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Breadcrumbs>
              <Link
                component="button"
                onClick={() => setCurrentPath('/')}
                sx={{ textDecoration: 'none' }}
              >
                Корень
              </Link>
              {pathParts.map((part, index) => (
                <Link
                  key={index}
                  component="button"
                  onClick={() => handleBreadcrumbClick(index)}
                  sx={{ textDecoration: 'none' }}
                >
                  {part}
                </Link>
              ))}
            </Breadcrumbs>
            <Box>
              <TextField
                placeholder="Поиск файлов..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: <Search />
                }}
                sx={{ width: 300, mr: 2 }}
              />
              <Button startIcon={<Refresh />} onClick={loadFiles}>
                Обновить
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Прогресс загрузки */}
      {uploadProgress > 0 && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="body2" gutterBottom>
              Загрузка файлов...
            </Typography>
            <LinearProgress variant="determinate" value={uploadProgress} />
          </CardContent>
        </Card>
      )}

      {/* Список файлов */}
      <Card>
        <CardContent>
          {viewMode === 'grid' ? (
            <Grid container spacing={2}>
              {filteredFiles.map((file) => {
                const fileType = file.is_folder ? 'folder' : getFileType(file.name);
                const typeInfo = fileTypes[fileType];
                
                return (
                  <Grid item xs={12} sm={6} md={4} lg={3} key={file.id}>
                    <Card
                      variant="outlined"
                      sx={{
                        cursor: file.is_folder ? 'pointer' : 'default',
                        '&:hover': { boxShadow: 2 }
                      }}
                      onClick={() => file.is_folder && handleFolderClick(file)}
                    >
                      <CardContent>
                        <Box display="flex" flexDirection="column" alignItems="center" textAlign="center">
                          <Avatar
                            sx={{
                              bgcolor: `${typeInfo.color}.main`,
                              width: 48,
                              height: 48,
                              mb: 1
                            }}
                          >
                            {typeInfo.icon}
                          </Avatar>
                          <Typography variant="subtitle2" noWrap sx={{ width: '100%' }}>
                            {file.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {file.is_folder ? 'Папка' : formatFileSize(file.size)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(file.created_at).toLocaleDateString()}
                          </Typography>
                          <Box mt={1}>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedFile(file);
                                setAnchorEl(e.currentTarget);
                              }}
                            >
                              <MoreVert />
                            </IconButton>
                          </Box>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Имя</TableCell>
                    <TableCell>Тип</TableCell>
                    <TableCell>Размер</TableCell>
                    <TableCell>Дата создания</TableCell>
                    <TableCell align="right">Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredFiles.map((file) => {
                    const fileType = file.is_folder ? 'folder' : getFileType(file.name);
                    const typeInfo = fileTypes[fileType];
                    
                    return (
                      <TableRow key={file.id} hover>
                        <TableCell>
                          <Box display="flex" alignItems="center">
                            <Avatar sx={{ mr: 2, bgcolor: `${typeInfo.color}.main` }}>
                              {typeInfo.icon}
                            </Avatar>
                            <Typography variant="subtitle2">
                              {file.name}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={file.is_folder ? 'Папка' : fileType}
                            color={typeInfo.color}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          {file.is_folder ? '-' : formatFileSize(file.size)}
                        </TableCell>
                        <TableCell>
                          {new Date(file.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell align="right">
                          <IconButton
                            onClick={(e) => {
                              setSelectedFile(file);
                              setAnchorEl(e.currentTarget);
                            }}
                          >
                            <MoreVert />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Меню действий с файлом */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        {selectedFile && !selectedFile.is_folder && (
          <MenuItem onClick={() => { handleFileDownload(selectedFile); setAnchorEl(null); }}>
            <ListItemIcon><Download /></ListItemIcon>
            <ListItemText>Скачать</ListItemText>
          </MenuItem>
        )}
        <MenuItem onClick={() => { setAnchorEl(null); }}>
          <ListItemIcon><Visibility /></ListItemIcon>
          <ListItemText>Просмотр</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { setAnchorEl(null); }}>
          <ListItemIcon><Share /></ListItemIcon>
          <ListItemText>Поделиться</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { setAnchorEl(null); }}>
          <ListItemIcon><Copy /></ListItemIcon>
          <ListItemText>Копировать</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { setAnchorEl(null); }}>
          <ListItemIcon><Move /></ListItemIcon>
          <ListItemText>Переместить</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => { handleFileDelete(selectedFile); setAnchorEl(null); }}>
          <ListItemIcon><Delete color="error" /></ListItemIcon>
          <ListItemText>Удалить</ListItemText>
        </MenuItem>
      </Menu>

      {/* Диалог загрузки файлов */}
      <Dialog open={showUploadDialog} onClose={() => setShowUploadDialog(false)}>
        <DialogTitle>Загрузить файлы</DialogTitle>
        <DialogContent>
          <input
            type="file"
            multiple
            onChange={handleFileUpload}
            style={{ display: 'none' }}
            id="file-upload"
          />
          <label htmlFor="file-upload">
            <Button
              variant="contained"
              component="span"
              startIcon={<CloudUpload />}
              fullWidth
              sx={{ py: 2 }}
            >
              Выбрать файлы
            </Button>
          </label>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
            Выберите файлы для загрузки в папку: {currentPath}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUploadDialog(false)}>Отмена</Button>
        </DialogActions>
      </Dialog>

      {/* Диалог создания папки */}
      <Dialog open={showCreateFolderDialog} onClose={() => setShowCreateFolderDialog(false)}>
        <DialogTitle>Создать папку</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Название папки"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCreateFolderDialog(false)}>Отмена</Button>
          <Button onClick={handleCreateFolder} variant="contained">
            Создать
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default FileManager;
