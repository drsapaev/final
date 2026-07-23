import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
  { value: 'Admin', label: t('admin2.um_role_admin') },
  { value: 'Doctor', label: t('admin2.um_role_doctor') },
  { value: 'Nurse', label: t('admin2.um_role_nurse') },
  { value: 'Receptionist', label: t('admin2.um_role_receptionist') },
  { value: 'Cashier', label: t('admin2.um_role_cashier') },
  { value: 'Lab', label: t('admin2.um_role_lab') },
  { value: 'Patient', label: t('admin2.um_role_patient') }];


  const roleOptions = apiRoleOptions.length > 0 ? apiRoleOptions : [
  { value: '', label: t('admin2.um_filter_all_roles') },
  ...roles];


  const statusOptions = [
  { value: '', label: t('admin2.um_filter_all_statuses') },
  { value: 'active', label: t('admin2.um_status_active_plural') },
  { value: 'inactive', label: t('admin2.um_status_inactive_plural') }];


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
      const params: Record<string, unknown> = { page, per_page: perPage };
      if (roleFilter) params.role = roleFilter;
      if (statusFilter) params.status = statusFilter;
      if (searchTerm) params.search = searchTerm;
      const response = (await api.get('/users/users', { params })) as import('axios').AxiosResponse<Record<string, unknown>>;
      setUsers((response.data.users as unknown as unknown[]) || (response.data as unknown as unknown[]) || []);
      setTotalPages(Number(response.data.total_pages ?? 1));
      setTotalUsers(Number(response.data.total ?? 0));
      setError('');
    } catch (err) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || t('admin2.um_error_connection');
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
        setSuccess(t('admin2.um_msg_updated'));
      } else {
        await api.post('/users/users', userData);
        setSuccess(t('admin2.um_msg_created'));
      }
      setError('');
      loadUsers(currentPage);
      setShowUserModal(false);
      setSelectedUser(null);
    } catch (err) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || t('admin2.um_error_save');
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
        t('admin2.um_msg_blocked_delete')
      );
      return;
    }

    try {
      await api.delete(`/users/users/${selectedUser.id}`);
      setSuccess(t('admin2.um_msg_deleted'));
      setError('');
      loadUsers(currentPage);
      setShowDeleteDialog(false);
      setSelectedUser(null);
    } catch (err) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || t('admin2.um_error_delete');

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
        t('admin2.um_msg_blocked_deactivate')
      );
      return;
    }

    try {
      await api.put(`/users/users/${selectedUser.id}`, { is_active: false });
      setSuccess(t('admin2.um_msg_deactivated'));
      setError('');
      loadUsers(currentPage);
      setShowDeleteDialog(false);
      setSelectedUser(null);
      setDeleteDialogMode('confirm');
      setDeleteDialogMessage('');
    } catch (deactivateErr) {
      const deactivateMessage = deactivateErr.response?.data?.detail || deactivateErr.message || t('admin2.um_error_deactivate');
      setError(t('admin2.um_error_deactivate_detailed', { message: deactivateMessage }));
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
      setSuccess(!isActive ? t('admin2.um_msg_activated') : t('admin2.um_msg_deactivated'));
      setError('');
      loadUsers(currentPage);
    } catch (err) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (err as Error)?.message || t('admin2.um_error_status_change');
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
          {user.is_active ? t('admin2.um_status_active_singular') : t('admin2.um_status_inactive_singular')}
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
        aria-label={t('admin2.um_actions_aria', { name: user.full_name || user.username })}
        aria-haspopup="menu"
        aria-expanded={actionsMenuUser?.id === user.id}
        title={t('admin2.um_actions_button_title')}
        onClick={(e: React.MouseEvent<HTMLElement>) => {
          openActionsMenu(e, user);
        }}
        variant="ghost"
        size="small"
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
          {t('admin2.um_page_title')}
        </Typography>
        <Button
          variant="primary"
          onClick={() => openUserDialog()}
          startIcon={<Plus size={16} />}>
          
          {t('admin2.um_btn_add')}
        </Button>
      </Box>

      {/* Alerts */}
      {error &&
      <Alert variant="error" title={t('admin2.um_alert_error')} onClose={() => setError('')} className="admin-mb-16">
          {error}
        </Alert>
      }
      {success &&
      <Alert variant="success" title={t('admin2.um_alert_success')} onClose={() => setSuccess('')} className="admin-mb-16">
          {success}
        </Alert>
      }

      {/* Filters */}
      <MacOSCard className="admin-mb-24-p-16">
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-ai-end">

          {/* Search */}
          <div className="admin-flex-1">
            <label className="admin-d-block-mb-6-fs-13-fw-500">{t('admin2.um_search_label')}</label>
            <div className="admin-pos-relative">
              <Search size={16} className="admin-pos-absolute-left-10-top-50pct-tf-translateY-50-888" />
              <Input
                placeholder={t('admin2.um_search_placeholder')}
                value={searchTerm}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSearchTerm(e.target.value)}
                className="admin-pl-32-w-100pct" />
              
            </div>
          </div>

          {/* Role Filter */}
          <div>
            <Select
              label={t('admin2.um_filter_role_label')}
              value={roleFilter}
              onChange={(v: unknown) => setRoleFilter(String(v))}
              options={roleOptions}
              placeholder={t('admin2.um_filter_all_roles')}
              size="large"
              className="admin-w-full" />

          </div>

          {/* Status Filter */}
          <div>
            <Select
              label={t('admin2.um_filter_status_label')}
              value={statusFilter}
              onChange={(v: unknown) => setStatusFilter(String(v))}
              options={statusOptions}
              placeholder={t('admin2.um_filter_all_statuses')}
              size="large"
              className="admin-w-full" />

          </div>

          {/* Refresh Button */}
          <div>
            <label className="admin-d-block-mb-6-fs-13-fw-500-vis-hidden">{t('admin2.um_action_filter_label')}</label>
            <Button
              variant="secondary"
              onClick={() => loadUsers(currentPage)}
              startIcon={<RefreshCw size={16} />}
              className="admin-w-100pct-jc-center"
              disabled={loading}>
              {t('admin2.um_btn_refresh')}
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
              {t('admin2.um_pagination_info', { total: totalUsers, current: currentPage, totalPages })}
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                variant="secondary"
                size="small"
                disabled={currentPage <= 1 || loading}
                onClick={() => { setCurrentPage(p => p - 1); loadUsers(currentPage - 1); }}>
                {t('admin2.um_btn_prev')}
              </Button>
              <Button
                variant="secondary"
                size="small"
                disabled={currentPage >= totalPages || loading}
                onClick={() => { setCurrentPage(p => p + 1); loadUsers(currentPage + 1); }}>
                {t('admin2.um_btn_next')}
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
        aria-label={t('admin2.um_actions_menu_aria')}
        className="admin-pos-fixed-z-2000-w-208-p-6-radius-var-mac-radius-md-bd-1px-solid-var-mac-bo-bg-bg-primary-bsh-var-mac-shadow-lg-d-grid-gap-2-top-dyn-left-dyn" style={{ '--admin-top0': actionsMenuPosition.top, '--admin-left1': actionsMenuPosition.left } as CSSProperties}>

        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="small"
          style={actionMenuItemStyle as CSSProperties}
          startIcon={<Edit size={16} />}
          onClick={handleEditFromActionsMenu}>
          {t('admin2.um_btn_edit')}
        </Button>
        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="small"
          style={actionMenuItemStyle as CSSProperties}
          startIcon={actionsMenuUser.is_active ? <Ban size={16} /> : <CheckCircle size={16} />}
          onClick={handleToggleStatusFromActionsMenu}>
          {actionsMenuUser.is_active ? t('admin2.um_btn_deactivate') : t('admin2.um_btn_activate')}
        </Button>
        <div role="separator" className="admin-h-1-bg-var-mac-border-m-4px-0" />
        <Button
          type="button"
          role="menuitem"
          variant="ghost"
          size="small"
          startIcon={<Trash2 size={16} />}
          className="admin-w-100pct-d-flex-ai-center-gap-10-p-9px-10px-bd-none-radius-var-mac-radius-sm-bg-transparent-primary-font-inherit-fs-13-ta-left-cur-pointer-error"
          onClick={handleDeleteFromActionsMenu}>
          {t('admin2.um_btn_delete')}
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
            ? t('admin2.um_modal_title_delete_unavailable')
            : deleteDialogMode === 'blocked-self'
              ? t('admin2.um_modal_title_action_unavailable')
              : t('admin2.um_modal_title_delete_confirm')
        }
        size="small">
        
        <div className="admin-p-0-0-24px-0">
          {deleteDialogMode === 'confirm' ? (
            <Typography>
              {t('admin2.um_delete_confirm_question', { name: selectedUser?.username })}
              <br />
              {t('admin2.um_delete_confirm_warning')}
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
                {t('admin2.cancel')}
              </Button>
              <Button variant="danger" onClick={handleDeleteUser}>
                {t('admin2.um_btn_delete')}
              </Button>
            </>
          ) : deleteDialogMode === 'deactivate' ? (
            <>
              <Button variant="secondary" onClick={closeDeleteDialog}>
                {t('admin2.cancel')}
              </Button>
              <Button variant="primary" onClick={handleDeactivateInstead}>
                {t('admin2.um_btn_deactivate')}
              </Button>
            </>
          ) : (
            <Button variant="primary" onClick={closeDeleteDialog}>
              {t('admin2.um_btn_understood')}
            </Button>
          )}
        </div>
      </Modal>

    </Box>);

};

export default UserManagement;
