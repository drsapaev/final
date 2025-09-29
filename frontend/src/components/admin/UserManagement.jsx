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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Avatar,
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  Grid,
  InputAdornment
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  MoreVert,
  Search,
  FilterList,
  Refresh,
  Person,
  Email,
  Phone,
  Security,
  CheckCircle,
  Error,
  Warning,
  Block,
  CheckCircleOutline,
  AdminPanelSettings,
  PersonAdd
} from '@mui/icons-material';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const [userForm, setUserForm] = useState({
    username: '',
    email: '',
    full_name: '',
    role: 'Patient',
    is_active: true,
    phone: '',
    password: ''
  });

  const roles = [
    { value: 'Admin', label: 'Администратор', color: 'error' },
    { value: 'Doctor', label: 'Врач', color: 'primary' },
    { value: 'Nurse', label: 'Медсестра', color: 'info' },
    { value: 'Receptionist', label: 'Регистратор', color: 'warning' },
    { value: 'Lab', label: 'Лаборант', color: 'secondary' },
    { value: 'Cashier', label: 'Кассир', color: 'success' },
    { value: 'Patient', label: 'Пациент', color: 'default' }
  ];

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/users/users', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || data);
      } else {
        setError('Ошибка загрузки пользователей');
      }
    } catch (err) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/users/users', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(userForm)
      });

      if (response.ok) {
        setSuccess('Пользователь успешно создан');
        loadUsers();
        setShowUserDialog(false);
        resetForm();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка создания пользователя');
      }
    } catch (err) {
      setError('Ошибка создания пользователя');
    }
  };

  const handleUpdateUser = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/users/users/${selectedUser.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(userForm)
      });

      if (response.ok) {
        setSuccess('Пользователь успешно обновлен');
        loadUsers();
        setShowUserDialog(false);
        setSelectedUser(null);
        resetForm();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка обновления пользователя');
      }
    } catch (err) {
      setError('Ошибка обновления пользователя');
    }
  };

  const handleDeleteUser = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/users/users/${selectedUser.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setSuccess('Пользователь успешно удален');
        loadUsers();
        setShowDeleteDialog(false);
        setSelectedUser(null);
      } else {
        setError('Ошибка удаления пользователя');
      }
    } catch (err) {
      setError('Ошибка удаления пользователя');
    }
  };

  const handleToggleUserStatus = async (userId, isActive) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/users/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_active: !isActive })
      });

      if (response.ok) {
        setSuccess(`Пользователь ${!isActive ? 'активирован' : 'деактивирован'}`);
        loadUsers();
      } else {
        setError('Ошибка изменения статуса пользователя');
      }
    } catch (err) {
      setError('Ошибка изменения статуса пользователя');
    }
  };

  const resetForm = () => {
    setUserForm({
      username: '',
      email: '',
      full_name: '',
      role: 'Patient',
      is_active: true,
      phone: '',
      password: ''
    });
  };

  const openUserDialog = (user = null) => {
    if (user) {
      setSelectedUser(user);
      setUserForm({
        username: user.username || '',
        email: user.email || '',
        full_name: user.full_name || '',
        role: user.role || 'Patient',
        is_active: user.is_active !== false,
        phone: user.phone || '',
        password: ''
      });
    } else {
      setSelectedUser(null);
      resetForm();
    }
    setShowUserDialog(true);
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || 
                         (statusFilter === 'active' && user.is_active) ||
                         (statusFilter === 'inactive' && !user.is_active);
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  const getRoleColor = (role) => {
    const roleData = roles.find(r => r.value === role);
    return roleData?.color || 'default';
  };

  const getRoleLabel = (role) => {
    const roleData = roles.find(r => r.value === role);
    return roleData?.label || role;
  };

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
          Управление пользователями
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => openUserDialog()}
        >
          Добавить пользователя
        </Button>
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

      {/* Фильтры и поиск */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="Поиск пользователей"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Search />
                    </InputAdornment>
                  )
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Роль</InputLabel>
                <Select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  label="Роль"
                >
                  <MenuItem value="all">Все роли</MenuItem>
                  {roles.map((role) => (
                    <MenuItem key={role.value} value={role.value}>
                      {role.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>Статус</InputLabel>
                <Select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  label="Статус"
                >
                  <MenuItem value="all">Все статусы</MenuItem>
                  <MenuItem value="active">Активные</MenuItem>
                  <MenuItem value="inactive">Неактивные</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Refresh />}
                onClick={loadUsers}
              >
                Обновить
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Таблица пользователей */}
      <Card>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Пользователь</TableCell>
                <TableCell>Роль</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Телефон</TableCell>
                <TableCell>Статус</TableCell>
                <TableCell>Последний вход</TableCell>
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredUsers.map((user) => (
                <TableRow key={user.id} hover>
                  <TableCell>
                    <Box display="flex" alignItems="center">
                      <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                        <Person />
                      </Avatar>
                      <Box>
                        <Typography variant="subtitle2">
                          {user.full_name || user.username}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          @{user.username}
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={getRoleLabel(user.role)}
                      color={getRoleColor(user.role)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{user.email || '-'}</TableCell>
                  <TableCell>{user.phone || '-'}</TableCell>
                  <TableCell>
                    <Chip
                      label={user.is_active ? 'Активен' : 'Неактивен'}
                      color={user.is_active ? 'success' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : '-'}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      onClick={(e) => {
                        setAnchorEl(e.currentTarget);
                        setSelectedUser(user);
                      }}
                    >
                      <MoreVert />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      {/* Меню действий */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem onClick={() => { openUserDialog(selectedUser); setAnchorEl(null); }}>
          <ListItemIcon><Edit /></ListItemIcon>
          <ListItemText>Редактировать</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => { 
          handleToggleUserStatus(selectedUser.id, selectedUser.is_active);
          setAnchorEl(null);
        }}>
          <ListItemIcon>
            {selectedUser?.is_active ? <Block /> : <CheckCircleOutline />}
          </ListItemIcon>
          <ListItemText>
            {selectedUser?.is_active ? 'Деактивировать' : 'Активировать'}
          </ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => { 
          setShowDeleteDialog(true); 
          setAnchorEl(null);
        }}>
          <ListItemIcon><Delete color="error" /></ListItemIcon>
          <ListItemText>Удалить</ListItemText>
        </MenuItem>
      </Menu>

      {/* Диалог создания/редактирования пользователя */}
      <Dialog open={showUserDialog} onClose={() => setShowUserDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedUser ? 'Редактировать пользователя' : 'Добавить пользователя'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Имя пользователя"
                value={userForm.username}
                onChange={(e) => setUserForm({...userForm, username: e.target.value})}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Полное имя"
                value={userForm.full_name}
                onChange={(e) => setUserForm({...userForm, full_name: e.target.value})}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={userForm.email}
                onChange={(e) => setUserForm({...userForm, email: e.target.value})}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Телефон"
                value={userForm.phone}
                onChange={(e) => setUserForm({...userForm, phone: e.target.value})}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Роль</InputLabel>
                <Select
                  value={userForm.role}
                  onChange={(e) => setUserForm({...userForm, role: e.target.value})}
                  label="Роль"
                >
                  {roles.map((role) => (
                    <MenuItem key={role.value} value={role.value}>
                      {role.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Пароль"
                type="password"
                value={userForm.password}
                onChange={(e) => setUserForm({...userForm, password: e.target.value})}
                required={!selectedUser}
                helperText={selectedUser ? "Оставьте пустым, чтобы не изменять" : "Обязательно для нового пользователя"}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={userForm.is_active}
                    onChange={(e) => setUserForm({...userForm, is_active: e.target.checked})}
                  />
                }
                label="Активный пользователь"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUserDialog(false)}>Отмена</Button>
          <Button
            onClick={selectedUser ? handleUpdateUser : handleCreateUser}
            variant="contained"
          >
            {selectedUser ? 'Обновить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог подтверждения удаления */}
      <Dialog open={showDeleteDialog} onClose={() => setShowDeleteDialog(false)}>
        <DialogTitle>Подтверждение удаления</DialogTitle>
        <DialogContent>
          <Typography>
            Вы уверены, что хотите удалить пользователя "{selectedUser?.username}"?
            Это действие нельзя отменить.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDeleteDialog(false)}>Отмена</Button>
          <Button onClick={handleDeleteUser} color="error" variant="contained">
            Удалить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UserManagement;

