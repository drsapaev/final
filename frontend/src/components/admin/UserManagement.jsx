import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTable,
  MacOSBadge,
  MacOSModal,
  MacOSAlert,
  Avatar,
  Box,
  Typography
} from '../ui/macos';
import {
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  Search,
  RefreshCw,
  User,
  CheckCircle,
  Ban,
  Shield,
  Mail
} from 'lucide-react';
import { Menu, MenuItem, ListItemIcon, ListItemText, Divider, IconButton } from '@mui/material'; // Legacy for Actions menu
import UserModal from './UserModal';
import { useRoles } from '../../hooks/useRoles';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);

  // Load roles from API (Phase 4: DB-driven roles)
  const { roleOptions: apiRoleOptions, loading: rolesLoading } = useRoles({ includeAll: true });

  // Fallback roles if API fails
  const roles = apiRoleOptions.filter(r => r.value !== '') || [
    { value: 'Admin', label: 'Администратор' },
    { value: 'Doctor', label: 'Врач' },
    { value: 'Nurse', label: 'Медсестра' },
    { value: 'Receptionist', label: 'Регистратор' },
    { value: 'Cashier', label: 'Кассир' },
    { value: 'Lab', label: 'Лаборант' },
    { value: 'Patient', label: 'Пациент' }
  ];

  const roleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
    { value: '', label: 'Все роли' },
    ...roles
  ];

  const statusOptions = [
    { value: '', label: 'Все статусы' },
    { value: 'active', label: 'Активные' },
    { value: 'inactive', label: 'Неактивные' }
  ];

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      // Request up to 100 users per page to show all users
      const response = await api.get('/users/users', { params: { per_page: 100 } });
      setUsers(response.data.users || response.data || []);
      setError('');
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка подключения к серверу';
      setError(errorMessage);
      logger.error('Ошибка загрузки пользователей:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveUser = async (userData) => {
    try {
      if (selectedUser) {
        await api.put(`/users/users/${selectedUser.id}`, userData);
        setSuccess('Пользователь успешно обновлен');
      } else {
        await api.post('/users/users', userData);
        setSuccess('Пользователь успешно создан');
      }
      setError('');
      loadUsers();
      setShowUserModal(false);
      setSelectedUser(null);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка сохранения пользователя';
      setError(errorMessage);
      logger.error('Ошибка сохранения пользователя:', err);
      throw err; // UserModal catch block will handle specific errors if needed
    }
  };

  const handleDeleteUser = async () => {
    try {
      await api.delete(`/users/users/${selectedUser.id}`);
      setSuccess('Пользователь успешно удален');
      setError('');
      loadUsers();
      setShowDeleteDialog(false);
      setSelectedUser(null);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка удаления пользователя';

      // Check if it's an IntegrityError (related data exists)
      if (errorMessage.includes('связанные данные') || errorMessage.includes('деактивировать')) {
        // Offer to deactivate instead
        const shouldDeactivate = window.confirm(
          `${errorMessage}\n\nХотите деактивировать пользователя вместо удаления?`
        );

        if (shouldDeactivate) {
          try {
            await api.put(`/users/users/${selectedUser.id}`, { is_active: false });
            setSuccess('Пользователь деактивирован');
            setError('');
            loadUsers();
            setShowDeleteDialog(false);
            setSelectedUser(null);
            return;
          } catch (deactivateErr) {
            setError('Ошибка деактивации пользователя: ' + (deactivateErr.response?.data?.detail || deactivateErr.message));
          }
        } else {
          setShowDeleteDialog(false);
          setSelectedUser(null);
        }
      } else {
        setError(errorMessage);
      }
      logger.error('Ошибка удаления пользователя:', err);
    }
  };

  const handleToggleUserStatus = async (userId, isActive) => {
    try {
      await api.put(`/users/users/${userId}`, { is_active: !isActive });
      setSuccess(`Пользователь ${!isActive ? 'активирован' : 'деактивирован'}`);
      setError('');
      loadUsers();
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка изменения статуса пользователя';
      setError(errorMessage);
      logger.error('Ошибка изменения статуса пользователя:', err);
    }
  };

  const openUserDialog = (user = null) => {
    setSelectedUser(user);
    setShowUserModal(true);
  };

  const getRoleBadgeVariant = (role) => {
    const variants = {
      'Admin': 'error',
      'Doctor': 'primary',
      'Nurse': 'info',
      'Receptionist': 'warning',
      'Lab': 'secondary',
      'Cashier': 'success',
      'Patient': 'default'
    };
    return variants[role] || 'default';
  };

  const getRoleLabel = (role) => {
    const roleData = roles.find(r => r.value === role);
    return roleData?.label || role;
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === '' || user.role === roleFilter;
    const matchesStatus = statusFilter === '' ||
      (statusFilter === 'active' && user.is_active) ||
      (statusFilter === 'inactive' && !user.is_active);

    return matchesSearch && matchesRole && matchesStatus;
  });

  // Table Columns Configuration
  const columns = [
    {
      key: 'user',
      title: 'Пользователь',
      render: (_, user) => (
        <Box display="flex" alignItems="center" gap="12px">
          {/* Placeholder Avatar - can be replaced with MacOSAvatar if available */}
          <div style={{
            width: '32px', height: '32px', borderRadius: '50%', background: '#007AFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white'
          }}>
            <User size={16} />
          </div>
          <Box>
            <Typography style={{ fontWeight: 500, fontSize: '13px' }}>
              {user.full_name || user.username}
            </Typography>
            <Typography style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>
              {user.username}
            </Typography>
          </Box>
        </Box>
      )
    },
    {
      key: 'role',
      title: 'Роль',
      render: (role) => (
        <MacOSBadge variant={getRoleBadgeVariant(role)}>
          {getRoleLabel(role)}
        </MacOSBadge>
      )
    },
    {
      key: 'email',
      title: 'Email',
      render: (email) => <span style={{ fontSize: '13px' }}>{email || '-'}</span>
    },
    {
      key: 'phone',
      title: 'Телефон',
      render: (phone) => <span style={{ fontSize: '13px' }}>{phone || '-'}</span>
    },
    {
      key: 'status',
      title: 'Статус',
      render: (_, user) => (
        <MacOSBadge variant={user.is_active ? 'success' : 'default'} outline>
          {user.is_active ? 'Активен' : 'Неактивен'}
        </MacOSBadge>
      )
    },
    {
      key: 'last_login',
      title: 'Последний вход',
      render: (last_login) => (
        <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
          {last_login ? new Date(last_login).toLocaleDateString() : '-'}
        </span>
      )
    },
    {
      key: 'actions',
      title: '',
      render: (_, user) => (
        <div onClick={(e) => e.stopPropagation()}>
          <IconButton
            onClick={(e) => {
              setAnchorEl(e.currentTarget);
              setSelectedUser(user);
            }}
            size="small"
          >
            <MoreVertical size={16} />
          </IconButton>
        </div>
      )
    }
  ];

  return (
    <Box style={{ padding: '24px' }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" style={{ marginBottom: '24px' }}>
        <Typography variant="h1" style={{ fontSize: '24px', fontWeight: 600 }}>
          Управление пользователями
        </Typography>
        <MacOSButton
          variant="primary"
          onClick={() => openUserDialog()}
          startIcon={<Plus size={16} />}
        >
          Добавить пользователя
        </MacOSButton>
      </Box>

      {/* Alerts */}
      {error && (
        <MacOSAlert variant="error" title="Ошибка" onClose={() => setError('')} style={{ marginBottom: '16px' }}>
          {error}
        </MacOSAlert>
      )}
      {success && (
        <MacOSAlert variant="success" title="Успешно" onClose={() => setSuccess('')} style={{ marginBottom: '16px' }}>
          {success}
        </MacOSAlert>
      )}

      {/* Filters */}
      <MacOSCard style={{ marginBottom: '24px', padding: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', alignItems: 'end' }}>

          {/* Search */}
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500 }}>Поиск</label>
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#888' }} />
              <MacOSInput
                placeholder="Поиск пользователей..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '32px', width: '100%' }}
              />
            </div>
          </div>

          {/* Role Filter */}
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500 }}>Роль</label>
            <MacOSSelect
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              options={roleOptions}
              placeholder="Все роли"
            />
          </div>

          {/* Status Filter */}
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500 }}>Статус</label>
            <MacOSSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={statusOptions}
              placeholder="Все статусы"
            />
          </div>

          {/* Refresh Button */}
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500, visibility: 'hidden' }}>Действие</label>
            <MacOSButton
              variant="secondary"
              onClick={loadUsers}
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={loading}
            >
              <RefreshCw size={16} style={{ marginRight: '8px' }} />
              Обновить
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Table */}
      <MacOSCard>
        <MacOSTable
          columns={columns}
          data={filteredUsers}
          loading={loading}
          hoverable
        />
      </MacOSCard>

      {/* Actions Menu (MUI Legacy for now) */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        PaperProps={{
          style: {
            borderRadius: '10px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            border: '1px solid #e5e7eb'
          }
        }}
      >
        <MenuItem onClick={() => { openUserDialog(selectedUser); setAnchorEl(null); }}>
          <ListItemIcon><Edit size={16} /></ListItemIcon>
          <ListItemText primary="Редактировать" primaryTypographyProps={{ fontSize: '13px' }} />
        </MenuItem>
        <MenuItem onClick={() => {
          handleToggleUserStatus(selectedUser.id, selectedUser.is_active);
          setAnchorEl(null);
        }}>
          <ListItemIcon>
            {selectedUser?.is_active ? <Ban size={16} /> : <CheckCircle size={16} />}
          </ListItemIcon>
          <ListItemText
            primary={selectedUser?.is_active ? 'Деактивировать' : 'Активировать'}
            primaryTypographyProps={{ fontSize: '13px' }}
          />
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => {
          setShowDeleteDialog(true);
          setAnchorEl(null);
        }}>
          <ListItemIcon><Trash2 size={16} color="#ef4444" /></ListItemIcon>
          <ListItemText primary="Удалить" primaryTypographyProps={{ fontSize: '13px', color: '#ef4444' }} />
        </MenuItem>
      </Menu>

      {/* User Modal (New MacOS Styled) */}
      <UserModal
        isOpen={showUserModal}
        onClose={() => setShowUserModal(false)}
        user={selectedUser}
        onSave={handleSaveUser}
        loading={loading && showUserModal}
      />

      {/* Delete Confirmation Dialog (Using MacOSModal) */}
      <MacOSModal
        isOpen={showDeleteDialog}
        onClose={() => setShowDeleteDialog(false)}
        title="Подтверждение удаления"
        size="sm"
      >
        <div style={{ padding: '0 0 24px 0' }}>
          <Typography>
            Вы уверены, что хотите удалить пользователя <b>{selectedUser?.username}</b>?
            <br />
            Это действие нельзя отменить.
          </Typography>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <MacOSButton variant="secondary" onClick={() => setShowDeleteDialog(false)}>
            Отмена
          </MacOSButton>
          <MacOSButton variant="danger" onClick={handleDeleteUser}>
            Удалить
          </MacOSButton>
        </div>
      </MacOSModal>

    </Box>
  );
};

export default UserManagement;
