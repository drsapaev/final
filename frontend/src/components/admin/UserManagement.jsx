import { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  Select,
  MacOSTable,
  MacOSBadge,
  MacOSModal,
  MacOSAlert,

  Box,
  Typography } from
'../ui/macos';
import {
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  Search,
  RefreshCw,
  User,
  CheckCircle,
  Ban } from


'lucide-react';
import UserModal from './UserModal';
import { useRoles } from '../../hooks/useRoles';
import { getProfile } from '../../stores/auth';

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
  const [currentProfile, setCurrentProfile] = useState(null);
  const [deleteDialogMode, setDeleteDialogMode] = useState('confirm');
  const [deleteDialogMessage, setDeleteDialogMessage] = useState('');
  const [actionsMenuUser, setActionsMenuUser] = useState(null);
  const [actionsMenuPosition, setActionsMenuPosition] = useState(null);
  const actionsMenuRef = useRef(null);

  // Load roles from API (Phase 4: DB-driven roles)
  const { roleOptions: apiRoleOptions } = useRoles({ includeAll: true });

  // Fallback roles if API fails
  const roles = apiRoleOptions.filter((r) => r.value !== '') || [
  { value: 'Admin', label: 'Администратор' },
  { value: 'Doctor', label: 'Врач' },
  { value: 'Nurse', label: 'Медсестра' },
  { value: 'Receptionist', label: 'Регистратор' },
  { value: 'Cashier', label: 'Кассир' },
  { value: 'Lab', label: 'Лаборант' },
  { value: 'Patient', label: 'Пациент' }];


  const roleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
  { value: '', label: 'Все роли' },
  ...roles];


  const statusOptions = [
  { value: '', label: 'Все статусы' },
  { value: 'active', label: 'Активные' },
  { value: 'inactive', label: 'Неактивные' }];


  useEffect(() => {
    loadUsers();
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadCurrentProfile = async () => {
      try {
        const profile = await getProfile();
        if (isMounted) {
          setCurrentProfile(profile || null);
        }
      } catch (profileError) {
        logger.warn('Не удалось загрузить текущий профиль пользователя для guardrail удаления', profileError);
      }
    };

    loadCurrentProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!actionsMenuUser) {
      return undefined;
    }

    const closeMenu = () => {
      setActionsMenuUser(null);
      setActionsMenuPosition(null);
    };

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeMenu();
      }
    };

    const handlePointerDown = (event) => {
      if (actionsMenuRef.current?.contains(event.target)) {
        return;
      }

      if (event.target.closest?.('[data-user-actions-trigger="true"]')) {
        return;
      }

      closeMenu();
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('mousedown', handlePointerDown);
    window.addEventListener('resize', closeMenu);
    window.addEventListener('scroll', closeMenu, true);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('mousedown', handlePointerDown);
      window.removeEventListener('resize', closeMenu);
      window.removeEventListener('scroll', closeMenu, true);
    };
  }, [actionsMenuUser]);

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
    if (!selectedUser) {
      return;
    }

    if (currentProfile?.id && Number(selectedUser.id) === Number(currentProfile.id)) {
      setDeleteDialogMode('blocked-self');
      setDeleteDialogMessage(
        'Нельзя удалить текущую учётную запись, под которой вы сейчас вошли. Войдите под другим администратором и удалите или деактивируйте этот аккаунт оттуда.'
      );
      return;
    }

    try {
      await api.delete(`/users/users/${selectedUser.id}`);
      setSuccess('Пользователь успешно удален');
      setError('');
      loadUsers();
      setShowDeleteDialog(false);
      setSelectedUser(null);
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка удаления пользователя';

      if (errorMessage.includes('связанные данные') || errorMessage.includes('деактивировать')) {
        setDeleteDialogMode('deactivate');
        setDeleteDialogMessage(errorMessage);
        logger.error('Ошибка удаления пользователя:', err);
        return;
      } else {
        setError(errorMessage);
      }
      logger.error('Ошибка удаления пользователя:', err);
    }
  };

  const handleDeactivateInstead = async () => {
    if (!selectedUser) {
      return;
    }

    if (currentProfile?.id && Number(selectedUser.id) === Number(currentProfile.id)) {
      setDeleteDialogMode('blocked-self');
      setDeleteDialogMessage(
        'Нельзя деактивировать текущую учётную запись из активной сессии. Войдите под другим администратором и выполните это действие оттуда.'
      );
      return;
    }

    try {
      await api.put(`/users/users/${selectedUser.id}`, { is_active: false });
      setSuccess('Пользователь деактивирован');
      setError('');
      loadUsers();
      setShowDeleteDialog(false);
      setSelectedUser(null);
      setDeleteDialogMode('confirm');
      setDeleteDialogMessage('');
    } catch (deactivateErr) {
      const deactivateMessage = deactivateErr.response?.data?.detail || deactivateErr.message || 'Ошибка деактивации пользователя';
      setError(`Ошибка деактивации пользователя: ${deactivateMessage}`);
      logger.error('Ошибка деактивации пользователя:', deactivateErr);
    }
  };

  const openDeleteDialog = (user) => {
    setSelectedUser(user);
    setDeleteDialogMode('confirm');
    setDeleteDialogMessage('');
    setShowDeleteDialog(true);
  };

  const closeDeleteDialog = () => {
    setShowDeleteDialog(false);
    setDeleteDialogMode('confirm');
    setDeleteDialogMessage('');
    setSelectedUser(null);
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

  const closeActionsMenu = () => {
    setActionsMenuUser(null);
    setActionsMenuPosition(null);
  };

  const openActionsMenu = (event, user) => {
    event.stopPropagation();

    const rect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 208;
    const left = Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8));

    setSelectedUser(user);
    setActionsMenuUser(user);
    setActionsMenuPosition({
      top: rect.bottom + 6,
      left
    });
  };

  const handleEditFromActionsMenu = () => {
    if (!actionsMenuUser) {
      return;
    }

    openUserDialog(actionsMenuUser);
    closeActionsMenu();
  };

  const handleToggleStatusFromActionsMenu = () => {
    if (!actionsMenuUser) {
      return;
    }

    handleToggleUserStatus(actionsMenuUser.id, actionsMenuUser.is_active);
    closeActionsMenu();
  };

  const handleDeleteFromActionsMenu = () => {
    if (!actionsMenuUser) {
      return;
    }

    openDeleteDialog(actionsMenuUser);
    closeActionsMenu();
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
    const roleData = roles.find((r) => r.value === role);
    return roleData?.label || role;
  };

  const filteredUsers = users.filter((user) => {
    const matchesSearch = user.username?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === '' || user.role === roleFilter;
    const matchesStatus = statusFilter === '' ||
    statusFilter === 'active' && user.is_active ||
    statusFilter === 'inactive' && !user.is_active;

    return matchesSearch && matchesRole && matchesStatus;
  });

  const actionMenuItemStyle = {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '9px 10px',
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    background: 'transparent',
    color: 'var(--mac-text-primary)',
    font: 'inherit',
    fontSize: '13px',
    textAlign: 'left',
    cursor: 'pointer'
  };

  // Table Columns Configuration
  const columns = [
  {
    key: 'user',
    title: 'Пользователь',
    render: (_, user) =>
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

  },
  {
    key: 'role',
    title: 'Роль',
    render: (role) =>
    <MacOSBadge variant={getRoleBadgeVariant(role)}>
          {getRoleLabel(role)}
        </MacOSBadge>

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
    render: (_, user) =>
    <MacOSBadge variant={user.is_active ? 'success' : 'default'} outline>
          {user.is_active ? 'Активен' : 'Неактивен'}
        </MacOSBadge>

  },
  {
    key: 'last_login',
    title: 'Последний вход',
    render: (last_login) =>
    <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
          {last_login ? new Date(last_login).toLocaleDateString() : '-'}
        </span>

  },
  {
    key: 'actions',
    title: '',
    render: (_, user) =>
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <MacOSButton
        data-user-actions-trigger="true"
        aria-label={`Действия: ${user.full_name || user.username}`}
        aria-haspopup="menu"
        aria-expanded={actionsMenuUser?.id === user.id}
        title="Действия"
        onClick={(e) => {
          openActionsMenu(e, user);
        }}
        variant="ghost"
        size="sm"
        style={{ width: '32px', height: '32px', padding: 0 }}>
        
            <MoreVertical size={16} />
          </MacOSButton>
        </div>

  }];


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
          startIcon={<Plus size={16} />}>
          
          Добавить пользователя
        </MacOSButton>
      </Box>

      {/* Alerts */}
      {error &&
      <MacOSAlert variant="error" title="Ошибка" onClose={() => setError('')} style={{ marginBottom: '16px' }}>
          {error}
        </MacOSAlert>
      }
      {success &&
      <MacOSAlert variant="success" title="Успешно" onClose={() => setSuccess('')} style={{ marginBottom: '16px' }}>
          {success}
        </MacOSAlert>
      }

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
                style={{ paddingLeft: '32px', width: '100%' }} />
              
            </div>
          </div>

          {/* Role Filter */}
          <div>
            <Select
              label="Роль"
              value={roleFilter}
              onChange={setRoleFilter}
              options={roleOptions}
              placeholder="Все роли"
              size="large"
              style={{ width: '100%' }} />

          </div>

          {/* Status Filter */}
          <div>
            <Select
              label="Статус"
              value={statusFilter}
              onChange={setStatusFilter}
              options={statusOptions}
              placeholder="Все статусы"
              size="large"
              style={{ width: '100%' }} />

          </div>

          {/* Refresh Button */}
          <div>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500, visibility: 'hidden' }}>Действие</label>
            <MacOSButton
              variant="secondary"
              onClick={loadUsers}
              startIcon={<RefreshCw size={16} />}
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={loading}>
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
          hoverable />
        
      </MacOSCard>

      {/* Actions Menu */}
      {actionsMenuUser && actionsMenuPosition &&
      <div
        ref={actionsMenuRef}
        role="menu"
        aria-label="Действия пользователя"
        style={{
          position: 'fixed',
          top: actionsMenuPosition.top,
          left: actionsMenuPosition.left,
          zIndex: 2000,
          width: '208px',
          padding: '6px',
          borderRadius: 'var(--mac-radius-md)',
          border: '1px solid var(--mac-border)',
          background: 'var(--mac-bg-primary)',
          boxShadow: 'var(--mac-shadow-lg)',
          display: 'grid',
          gap: '2px'
        }}>

        <MacOSButton
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          style={actionMenuItemStyle}
          startIcon={<Edit size={16} />}
          onClick={handleEditFromActionsMenu}>
          Редактировать
        </MacOSButton>
        <MacOSButton
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          style={actionMenuItemStyle}
          startIcon={actionsMenuUser.is_active ? <Ban size={16} /> : <CheckCircle size={16} />}
          onClick={handleToggleStatusFromActionsMenu}>
          {actionsMenuUser.is_active ? 'Деактивировать' : 'Активировать'}
        </MacOSButton>
        <div role="separator" style={{ height: '1px', background: 'var(--mac-border)', margin: '4px 0' }} />
        <MacOSButton
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          startIcon={<Trash2 size={16} />}
          style={{ ...actionMenuItemStyle, color: 'var(--mac-error)' }}
          onClick={handleDeleteFromActionsMenu}>
          Удалить
        </MacOSButton>
      </div>
      }

      {/* User Modal (New MacOS Styled) */}
      <UserModal
        isOpen={showUserModal}
        onClose={() => setShowUserModal(false)}
        user={selectedUser}
        onSave={handleSaveUser}
        loading={loading && showUserModal} />
      

      {/* Delete Confirmation Dialog (Using MacOSModal) */}
      <MacOSModal
        isOpen={showDeleteDialog}
        onClose={closeDeleteDialog}
        title={
          deleteDialogMode === 'deactivate'
            ? 'Удаление недоступно'
            : deleteDialogMode === 'blocked-self'
              ? 'Действие недоступно'
              : 'Подтверждение удаления'
        }
        size="sm">
        
        <div style={{ padding: '0 0 24px 0' }}>
          {deleteDialogMode === 'confirm' ? (
            <Typography>
              Вы уверены, что хотите удалить пользователя <b>{selectedUser?.username}</b>?
              <br />
              Это действие нельзя отменить.
            </Typography>
          ) : (
            <Typography>
              <b>{selectedUser?.username}</b>
              <br />
              <br />
              {deleteDialogMessage}
            </Typography>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          {deleteDialogMode === 'confirm' ? (
            <>
              <MacOSButton variant="secondary" onClick={closeDeleteDialog}>
                Отмена
              </MacOSButton>
              <MacOSButton variant="danger" onClick={handleDeleteUser}>
                Удалить
              </MacOSButton>
            </>
          ) : deleteDialogMode === 'deactivate' ? (
            <>
              <MacOSButton variant="secondary" onClick={closeDeleteDialog}>
                Отмена
              </MacOSButton>
              <MacOSButton variant="primary" onClick={handleDeactivateInstead}>
                Деактивировать
              </MacOSButton>
            </>
          ) : (
            <MacOSButton variant="primary" onClick={closeDeleteDialog}>
              Понятно
            </MacOSButton>
          )}
        </div>
      </MacOSModal>

    </Box>);

};

export default UserManagement;
