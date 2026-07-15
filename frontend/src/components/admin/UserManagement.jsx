import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  MacOSCard,
  Button,
  Input,
  Select,
  Table,
  Badge,
  Modal,
  Alert,
  Box,
  Typography,
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
  Ban } from


'lucide-react';
import UserModal from './UserModal';
import { useRoles } from '../../hooks/useRoles';
import { getProfile } from '../../stores/auth';

const UserManagement = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  // PR-22: pagination state (was hardcoded per_page=100, no pagination UI)
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const perPage = 50;
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
    loadUsers(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // PR-22: reload when filters or search change
  useEffect(() => {
    setCurrentPage(1);
    loadUsers(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, roleFilter, statusFilter]);

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

  const loadUsers = async (page = currentPage) => {
    try {
      setLoading(true);
      // PR-22: use pagination — was per_page=100 with no pagination UI
      const params = { page, per_page: perPage };
      if (roleFilter) params.role = roleFilter;
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      const response = await api.get('/users/users', { params });
      setUsers(response.data.users || response.data || []);
      setTotalPages(response.data.total_pages || 1);
      setTotalUsers(response.data.total || 0);
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
      loadUsers(currentPage);
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
      loadUsers(currentPage);
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
      loadUsers(currentPage);
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
      loadUsers(currentPage);
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
    fontSize: 'var(--mac-font-size-sm)',
    textAlign: 'left',
    cursor: 'pointer'
  };

  // Table Columns Configuration
  const columns = [
  {
    key: 'user',
    title: t('admin2.col_user'),
    render: (_, user) =>
    <Box display="flex" alignItems="center" gap="12px">
          {/* Placeholder Avatar - can be replaced with MacOSAvatar if available */}
          <div className="admin-w-32-h-32-radius-50pct-bg-007AFF-d-flex-ai-center-jc-center-white">
            <User size={16} />
          </div>
          <Box>
            <Typography className="admin-fw-500-fs-13">
              {user.full_name || user.username}
            </Typography>
            <Typography className="admin-fs-12-secondary">
              {user.username}
            </Typography>
          </Box>
        </Box>

  },
  {
    key: 'role',
    title: t('admin2.col_role'),
    render: (role) =>
    <Badge variant={getRoleBadgeVariant(role)}>
          {getRoleLabel(role)}
        </Badge>

  },
  {
    key: 'email',
    title: 'Email',
    render: (email) => <span className="admin-fs-13-1">{email || '-'}</span>
  },
  {
    key: 'phone',
    title: t('admin2.col_phone'),
    render: (phone) => <span className="admin-fs-13">{phone || '-'}</span>
  },
  {
    key: 'status',
    title: t('admin2.col_active'),
    render: (_, user) =>
    <Badge variant={user.is_active ? 'success' : 'default'} outline>
          {user.is_active ? 'Активен' : 'Неактивен'}
        </Badge>

  },
  {
    key: 'last_login',
    title: t('admin2.col_last_login'),
    render: (last_login) =>
    <span className="admin-fs-13-secondary">
          {last_login ? new Date(last_login).toLocaleDateString() : '-'}
        </span>

  },
  {
    key: 'actions',
    title: '',
    render: (_, user) =>
    <div className="admin-d-flex-jc-end">
          <Button
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
        className="admin-w-32-h-32-p-0">
        
            <MoreVertical size={16} />
          </Button>
        </div>

  }];


  return (
    <Box className="admin-p-24">
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" className="admin-mb-24">
        <Typography variant="h1" className="admin-fs-24-fw-600">
          Управление пользователями
        </Typography>
        <Button
          variant="primary"
          onClick={() => openUserDialog()}
          startIcon={<Plus size={16} />}>
          
          Добавить пользователя
        </Button>
      </Box>

      {/* Alerts */}
      {error &&
      <Alert variant="error" title="Ошибка" onClose={() => setError('')} className="admin-mb-16">
          {error}
        </Alert>
      }
      {success &&
      <Alert variant="success" title="Успешно" onClose={() => setSuccess('')} className="admin-mb-16">
          {success}
        </Alert>
      }

      {/* Filters */}
      <MacOSCard className="admin-mb-24-p-16">
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-ai-end">

          {/* Search */}
          <div className="admin-flex-1">
            <label className="admin-d-block-mb-6-fs-13-fw-500">Поиск</label>
            <div className="admin-pos-relative">
              <Search size={16} className="admin-pos-absolute-left-10-top-50pct-tf-translateY-50-888" />
              <Input
                placeholder="Поиск пользователей..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="admin-pl-32-w-100pct" />
              
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
              className="admin-w-full" />

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
              className="admin-w-full" />

          </div>

          {/* Refresh Button */}
          <div>
            <label className="admin-d-block-mb-6-fs-13-fw-500-vis-hidden">Действие</label>
            <Button
              variant="secondary"
              onClick={() => loadUsers(currentPage)}
              startIcon={<RefreshCw size={16} />}
              className="admin-w-100pct-jc-center"
              disabled={loading}>
              Обновить
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Table */}
      <MacOSCard>
        <Table
          columns={columns}
          data={filteredUsers}
          loading={loading}
          hoverable />

        {/* PR-22: Pagination controls */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderTop: '1px solid var(--mac-border)' }}>
            <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
              Всего: {totalUsers} · Страница {currentPage} из {totalPages}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage <= 1 || loading}
                onClick={() => { setCurrentPage(p => p - 1); loadUsers(currentPage - 1); }}>
                ← Назад
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage >= totalPages || loading}
                onClick={() => { setCurrentPage(p => p + 1); loadUsers(currentPage + 1); }}>
                Вперёд →
              </Button>
            </div>
          </div>
        )}

      </MacOSCard>

      {/* Actions Menu */}
      {actionsMenuUser && actionsMenuPosition &&
      <div
        ref={actionsMenuRef}
        role="menu"
        aria-label="Действия пользователя"
        className="admin-pos-fixed-z-2000-w-208-p-6-radius-var-mac-radius-md-bd-1px-solid-var-mac-bo-bg-bg-primary-bsh-var-mac-shadow-lg-d-grid-gap-2-top-dyn-left-dyn" style={{ '--admin-top0': actionsMenuPosition.top, '--admin-left1': actionsMenuPosition.left }}>

        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          style={actionMenuItemStyle}
          startIcon={<Edit size={16} />}
          onClick={handleEditFromActionsMenu}>
          Редактировать
        </Button>
        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          style={actionMenuItemStyle}
          startIcon={actionsMenuUser.is_active ? <Ban size={16} /> : <CheckCircle size={16} />}
          onClick={handleToggleStatusFromActionsMenu}>
          {actionsMenuUser.is_active ? 'Деактивировать' : 'Активировать'}
        </Button>
        <div role="separator" className="admin-h-1-bg-var-mac-border-m-4px-0" />
        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="sm"
          startIcon={<Trash2 size={16} />}
          className="admin-w-100pct-d-flex-ai-center-gap-10-p-9px-10px-bd-none-radius-var-mac-radius-sm-bg-transparent-primary-font-inherit-fs-13-ta-left-cur-pointer-error"
          onClick={handleDeleteFromActionsMenu}>
          Удалить
        </Button>
      </div>
      }

      {/* User Modal (New MacOS Styled) */}
      <UserModal
        isOpen={showUserModal}
        onClose={() => setShowUserModal(false)}
        user={selectedUser}
        onSave={handleSaveUser}
        loading={loading && showUserModal} />
      

      {/* Delete Confirmation Dialog (Using Modal) */}
      <Modal
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
        
        <div className="admin-p-0-0-24px-0">
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
        <div className="admin-d-flex-jc-end-gap-8">
          {deleteDialogMode === 'confirm' ? (
            <>
              <Button variant="secondary" onClick={closeDeleteDialog}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleDeleteUser}>
                Удалить
              </Button>
            </>
          ) : deleteDialogMode === 'deactivate' ? (
            <>
              <Button variant="secondary" onClick={closeDeleteDialog}>
                Отмена
              </Button>
              <Button variant="primary" onClick={handleDeactivateInstead}>
                Деактивировать
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={closeDeleteDialog}>
              Понятно
            </Button>
          )}
        </div>
      </Modal>

    </Box>);

};

export default UserManagement;
