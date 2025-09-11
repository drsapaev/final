import React, { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Badge,
  Tooltip,
  Snackbar,
  Alert
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard,
  People,
  Description,
  Folder,
  Notifications,
  Telegram,
  Email,
  Security,
  Settings,
  Logout,
  AccountCircle,
  Brightness4,
  Brightness7
} from '@mui/icons-material';

// Импорт компонентов
import LoginForm from './components/LoginForm';
import Dashboard as DashboardComponent from './components/Dashboard';
import UserManagement from './components/UserManagement';
import EMRInterface from './components/EMRInterface';
import FileManager from './components/FileManager';
import EmailSMSManager from './components/EmailSMSManager';
import TelegramManager from './components/TelegramManager';
import TwoFactorManager from './components/TwoFactorManager';
import PWAInstallPrompt from './components/mobile/PWAInstallPrompt';

const drawerWidth = 240;

const AppNew = () => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });

  // Создание темы
  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: '#1976d2',
      },
      secondary: {
        main: '#dc004e',
      },
    },
  });

  useEffect(() => {
    // Проверяем аутентификацию при загрузке
    checkAuthentication();
  }, []);

  const checkAuthentication = async () => {
    const token = localStorage.getItem('access_token');
    if (token) {
      try {
        const response = await fetch('/api/v1/auth/profile', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
          setIsAuthenticated(true);
        } else {
          // Токен недействителен
          localStorage.removeItem('access_token');
          localStorage.removeItem('token_type');
        }
      } catch (err) {
        console.error('Ошибка проверки аутентификации:', err);
        localStorage.removeItem('access_token');
        localStorage.removeItem('token_type');
      }
    }
  };

  const handleLogin = (userData) => {
    setUser(userData);
    setIsAuthenticated(true);
    setCurrentPage('dashboard');
    showNotification('Успешный вход в систему!', 'success');
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_type');
    setUser(null);
    setIsAuthenticated(false);
    setCurrentPage('login');
    showNotification('Вы вышли из системы', 'info');
  };

  const showNotification = (message, severity = 'info') => {
    setNotification({ open: true, message, severity });
  };

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const menuItems = [
    { id: 'dashboard', label: 'Главная', icon: <Dashboard /> },
    { id: 'users', label: 'Пользователи', icon: <People /> },
    { id: 'emr', label: 'Мед. карты', icon: <Description /> },
    { id: 'files', label: 'Файлы', icon: <Folder /> },
    { id: 'notifications', label: 'Уведомления', icon: <Email /> },
    { id: 'telegram', label: 'Telegram', icon: <Telegram /> },
    { id: 'security', label: 'Безопасность', icon: <Security /> },
    { id: 'settings', label: 'Настройки', icon: <Settings /> }
  ];

  const renderCurrentPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardComponent user={user} />;
      case 'users':
        return <UserManagement />;
      case 'emr':
        return <EMRInterface />;
      case 'files':
        return <FileManager />;
      case 'notifications':
        return <EmailSMSManager />;
      case 'telegram':
        return <TelegramManager />;
      case 'security':
        return <TwoFactorManager />;
      case 'settings':
        return <div>Настройки (в разработке)</div>;
      default:
        return <DashboardComponent user={user} />;
    }
  };

  const getPageTitle = () => {
    const item = menuItems.find(item => item.id === currentPage);
    return item ? item.label : 'Система управления клиникой';
  };

  // Если пользователь не аутентифицирован, показываем форму входа
  if (!isAuthenticated) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <LoginForm onLogin={handleLogin} />
        <PWAInstallPrompt />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex' }}>
        {/* AppBar */}
        <AppBar
          position="fixed"
          sx={{
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            ml: { sm: `${drawerWidth}px` },
          }}
        >
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={() => setDrawerOpen(!drawerOpen)}
              sx={{ mr: 2, display: { sm: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
              {getPageTitle()}
            </Typography>
            
            {/* Уведомления */}
            <Tooltip title="Уведомления">
              <IconButton color="inherit" sx={{ mr: 1 }}>
                <Badge badgeContent={4} color="error">
                  <Notifications />
                </Badge>
              </IconButton>
            </Tooltip>

            {/* Переключение темы */}
            <Tooltip title={darkMode ? 'Светлая тема' : 'Темная тема'}>
              <IconButton color="inherit" onClick={() => setDarkMode(!darkMode)} sx={{ mr: 1 }}>
                {darkMode ? <Brightness7 /> : <Brightness4 />}
              </IconButton>
            </Tooltip>

            {/* Профиль пользователя */}
            <Tooltip title="Профиль">
              <IconButton
                color="inherit"
                onClick={(e) => setAnchorEl(e.currentTarget)}
              >
                <Avatar sx={{ width: 32, height: 32 }}>
                  {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
                </Avatar>
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        {/* Drawer */}
        <Box
          component="nav"
          sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
        >
          <Drawer
            variant="temporary"
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            ModalProps={{
              keepMounted: true,
            }}
            sx={{
              display: { xs: 'block', sm: 'none' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
          >
            <DrawerContent />
          </Drawer>
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: 'none', sm: 'block' },
              '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
            }}
            open
          >
            <DrawerContent />
          </Drawer>
        </Box>

        {/* Основной контент */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            mt: 8
          }}
        >
          {renderCurrentPage()}
        </Box>

        {/* Меню профиля */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={() => setAnchorEl(null)}
        >
          <MenuItem onClick={() => { setAnchorEl(null); }}>
            <ListItemIcon><AccountCircle /></ListItemIcon>
            <ListItemText>Профиль</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => { setAnchorEl(null); setCurrentPage('settings'); }}>
            <ListItemIcon><Settings /></ListItemIcon>
            <ListItemText>Настройки</ListItemText>
          </MenuItem>
          <Divider />
          <MenuItem onClick={() => { setAnchorEl(null); handleLogout(); }}>
            <ListItemIcon><Logout /></ListItemIcon>
            <ListItemText>Выйти</ListItemText>
          </MenuItem>
        </Menu>

        {/* Уведомления */}
        <Snackbar
          open={notification.open}
          autoHideDuration={6000}
          onClose={handleCloseNotification}
        >
          <Alert
            onClose={handleCloseNotification}
            severity={notification.severity}
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>

        {/* PWA Install Prompt */}
        <PWAInstallPrompt />
      </Box>
    </ThemeProvider>
  );

  function DrawerContent() {
    return (
      <Box>
        <Toolbar>
          <Typography variant="h6" noWrap component="div">
            Клиника
          </Typography>
        </Toolbar>
        <Divider />
        <List>
          {menuItems.map((item) => (
            <ListItem key={item.id} disablePadding>
              <ListItemButton
                selected={currentPage === item.id}
                onClick={() => {
                  setCurrentPage(item.id);
                  setDrawerOpen(false);
                }}
              >
                <ListItemIcon>
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        <Divider />
        <List>
          <ListItem>
            <ListItemText
              primary={`${user?.full_name || user?.username || 'Пользователь'}`}
              secondary={user?.role || 'Пользователь'}
            />
          </ListItem>
        </List>
      </Box>
    );
  }
};

export default AppNew;
