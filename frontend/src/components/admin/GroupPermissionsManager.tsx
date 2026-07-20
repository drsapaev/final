import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import {
  Users,
  Shield,
  Settings,

  Trash2,





  Key,


  RefreshCw,


  CheckCircle,
  Clock,
  User } from
'lucide-react';
import {
  MacOSCard, Button as RawButton, Badge as RawBadge, Input as RawInput, Select as RawSelect, SegmentedControl as RawSegmentedControl, Skeleton as RawSkeleton,
} from '../ui/macos';
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const Input = RawInput as unknown as React.ComponentType<Record<string, unknown>>;
const Select = RawSelect as unknown as React.ComponentType<Record<string, unknown>>;
const SegmentedControl = RawSegmentedControl as unknown as React.ComponentType<Record<string, unknown>>;
const Skeleton = RawSkeleton as unknown as React.ComponentType<Record<string, unknown>>;
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const toArray = (value, fallbackKeys = []) => {
  if (Array.isArray(value)) return value;

  for (const key of fallbackKeys) {
    if (Array.isArray(value?.[key])) {
      return value[key];
    }
  }

  return [];
};

const normalizeCacheStats = (payload) => ({
  cache_ttl: 0,
  cache_size: 0,
  ...(payload || {}),
  cached_users: toArray(payload?.cached_users)
});

const normalizeUserPermissions = (payload) => ({
  ...(payload || {}),
  roles: toArray(payload?.roles),
  groups: toArray(payload?.groups),
  permissions: toArray(payload?.permissions),
  permissions_count: payload?.permissions_count ?? toArray(payload?.permissions).length
});

const normalizeGroupSummary = (payload) => ({
  ...(payload || {}),
  roles: toArray(payload?.roles),
  permissions_by_category: payload?.permissions_by_category && typeof payload.permissions_by_category === 'object' ?
    Object.fromEntries(
      Object.entries(payload.permissions_by_category).map(([category, permissions]) => [category, toArray(permissions)])
    ) :
    {},
  users_count: payload?.users_count ?? 0,
  permissions_count: payload?.permissions_count ?? 0
});

const GroupPermissionsManager = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // Состояние
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [permissionToCheck, setPermissionToCheck] = useState('');
  const [roleToAssign, setRoleToAssign] = useState('');

  // Данные
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [userPermissions, setUserPermissions] = useState(null);
  const [groupSummary, setGroupSummary] = useState(null);
  const [cacheStats, setCacheStats] = useState({
    cache_ttl: 0,
    cache_size: 0,
    cached_users: []
  });

  // Загрузка данных
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [usersRes, groupsRes, rolesRes, permissionsRes, cacheRes] = await Promise.all([
      api.get('/users/users', { params: { per_page: 100 } }),
      api.get('/admin/permissions/groups'),
      api.get('/admin/permissions/roles'),
      api.get('/admin/permissions/permissions'),
      api.get('/admin/permissions/cache/stats')]
      );

      setUsers(toArray(usersRes.data, ['users', 'items', 'results']));
      setGroups(toArray(groupsRes.data, ['groups', 'items', 'results']));
      setRoles(toArray(rolesRes.data, ['roles', 'items', 'results']));
      setPermissions(toArray(permissionsRes.data, ['permissions', 'items', 'results']));
      setCacheStats(normalizeCacheStats(cacheRes.data?.cache_stats || cacheRes.data));
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error(t('admin2.gpm_load_data_error'));
    } finally {
      setLoading(false);
    }
  };

  const loadUserPermissions = async (userId) => {
    if (!userId) return;

    setLoading(true);
    try {
      const response = await api.get(`/admin/permissions/users/${userId}/permissions`) as any;
      setUserPermissions(normalizeUserPermissions(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки разрешений пользователя:', error);
      toast.error(t('admin2.gpm_load_user_perms_error'));
    } finally {
      setLoading(false);
    }
  };

  const loadGroupSummary = async (groupId) => {
    if (!groupId) return;

    setLoading(true);
    try {
      const response = await api.get(`/admin/permissions/groups/${groupId}/permissions`) as any;
      setGroupSummary(normalizeGroupSummary(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки сводки группы:', error);
      toast.error(t('admin2.gpm_load_group_summary_error'));
    } finally {
      setLoading(false);
    }
  };
  const handleActivationKeyDown = (event, action) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  const checkUserPermission = async (userId, permission) => {
    try {
      const response = await api.get(`/admin/permissions/users/${userId}/permissions/check`, {
        params: { permission }
      }) as any;

      const hasPermission = Boolean(response.data?.has_permission);
      toast.success(
        hasPermission ?
        t('admin2.gpm_user_has_permission', { permission }) :
        t('admin2.gpm_user_no_permission', { permission })
      );
    } catch (error) {
      logger.error('Ошибка проверки разрешения:', error);
      toast.error(t('admin2.gpm_check_permission_error'));
    }
  };

  const assignRoleToGroup = async (groupId, roleId) => {
    try {
      const response = await api.post(`/admin/permissions/groups/${groupId}/roles`, {
        role_id: roleId
      }) as any;

      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка назначения роли:', error);
      toast.error(error.response?.data?.detail || t('admin2.gpm_assign_role_error'));
    }
  };

  const revokeRoleFromGroup = async (groupId, roleId) => {
    try {
      const response = await api.delete(`/admin/permissions/groups/${groupId}/roles/${roleId}`) as any;

      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка отзыва роли:', error);
      toast.error(error.response?.data?.detail || t('admin2.gpm_revoke_role_error'));
    }
  };













































  const clearCache = async () => {
    try {
      const response = await api.post('/admin/permissions/cache/clear') as any;
      toast.success(response.data.message);

      // Обновляем статистику кэша
      const cacheRes = await api.get('/admin/permissions/cache/stats') as any;
      setCacheStats(normalizeCacheStats(cacheRes.data?.cache_stats || cacheRes.data));
    } catch (error) {
      logger.error('Ошибка очистки кэша:', error);
      toast.error(t('admin2.gpm_clear_cache_error'));
    }
  };

  // Фильтрация данных
  const normalizedSearchTerm = searchTerm.toLowerCase();

  const filteredGroups = groups.filter((group) =>
  String(group.name || '').toLowerCase().includes(normalizedSearchTerm) ||
  String(group.display_name || '').toLowerCase().includes(normalizedSearchTerm)
  );

  const filteredUsers = users.filter((user) =>
  user.username?.toLowerCase().includes(normalizedSearchTerm) ||
  user.full_name?.toLowerCase().includes(normalizedSearchTerm) ||
  user.email?.toLowerCase().includes(normalizedSearchTerm) ||
  user.role?.toLowerCase().includes(normalizedSearchTerm)
  );

  // Стили
  const containerStyle = {
    padding: 'var(--mac-spacing-6)',
    minHeight: '100vh',
    backgroundColor: 'var(--mac-bg-primary)'
  };
















  const renderUsersTab = () =>
  <div className="admin-flex admin-gap-24">
      {/* Левая панель - список пользователей */}
      <MacOSCard className="admin-card-sidebar-300">
        <h3 className="admin-list-h3">
          <Users className="w-5 h-5" />
          {t('admin2.gpm_users')}
        </h3>
        
        <Input
        placeholder={t('admin2.gpm_search_users_ph')}
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="mb-4" />
      
        
        <div className="admin-max-h-400-overflow">
          {filteredUsers.map((user) =>
        <div
          key={user.id}
          role="button"
          tabIndex={0}
          onClick={() => {
            setSelectedUser(user);
            loadUserPermissions(user.id);
          }}
          onKeyDown={(event) => handleActivationKeyDown(event, () => {
            setSelectedUser(user);
            loadUserPermissions(user.id);
          })}
          className="admin-perm-list-item"
          style={{
            '--admin-list-bg': selectedUser?.id === user.id ? 'var(--mac-accent-blue-light)' : 'transparent',
            '--admin-list-border': selectedUser?.id === user.id ? 'var(--mac-accent-blue)' : 'transparent'
          } as CSSProperties}>
          
              <div className="admin-list-username">
                {user.username}
              </div>
              <div className="admin-list-sub-xs">
                {user.full_name || t('admin2.gpm_no_name')}
              </div>
              <div className="admin-list-sub-tertiary-xs">
                {t('admin2.gpm_role_label', { role: user.role })}
              </div>
            </div>
        )}

          {filteredUsers.length === 0 &&
        <div className="admin-empty-p-16-sm-secondary">
              {t('admin2.gpm_users_not_found')}
            </div>
        }
        </div>
      </MacOSCard>

      {/* Правая панель - разрешения пользователя */}
      <MacOSCard className="admin-card-main-flex-1">
        {selectedUser ?
      <>
            <div className="admin-flex-between-mb-16">
              <h3 className="admin-header-h3-m0">
                <Shield className="w-5 h-5" />
                {t('admin2.gpm_permissions_for_user', { username: selectedUser.username })}
              </h3>
              <Button
            onClick={() => loadUserPermissions(selectedUser.id)}
            disabled={loading}>
            
                <RefreshCw className="w-4 h-4" />
                {t('admin2.gpm_refresh')}
              </Button>
            </div>

            {loading ?
        <div>
                <Skeleton height="20px" className="mb-2" />
                <Skeleton height="20px" className="mb-2" />
                <Skeleton height="20px" />
              </div> :
        userPermissions ?
        <div>
                <div className="mb-4">
                  <Badge variant="primary">
                    {t('admin2.gpm_total_permissions', { count: userPermissions.permissions_count })}
                  </Badge>
                  <Badge variant="secondary" className="admin-ml-8">
                    {t('admin2.gpm_roles_count', { count: userPermissions.roles.length })}
                  </Badge>
                  <Badge variant="info" className="admin-ml-8">
                    {t('admin2.gpm_groups_count', { count: userPermissions.groups.length })}
                  </Badge>
                </div>

                <div className="mb-6">
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_roles_section')}
                  </h4>
                  <div className="admin-flex-wrap-8">
                    {userPermissions.roles.map((role) =>
              <Badge key={role} variant="success">{role}</Badge>
              )}
                  </div>
                </div>

                <div className="mb-6">
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_groups_section')}
                  </h4>
                  <div className="admin-flex-wrap-8">
                    {userPermissions.groups.map((group) =>
              <Badge key={group} variant="info">{group}</Badge>
              )}
                  </div>
                </div>

                <div>
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_permissions_section')}
                  </h4>
                  <div className="admin-max-h-300-overflow admin-perms-grid">
                    {userPermissions.permissions.map((permission) =>
              <div key={permission} className="admin-perm-card">
                
                        <CheckCircle className="admin-icon-14-success" />
                        {permission}
                      </div>
              )}
                  </div>
                </div>

                {/* Инструменты проверки разрешений */}
                <div className="admin-perm-summary-box">
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_check_permission_section')}
                  </h4>
                  <div className="admin-flex-start-end admin-gap-8">
                    <div className="admin-flex-1">
                      <Select
                  value={permissionToCheck}
                  onChange={(value) => {
                    setPermissionToCheck(value);
                    if (value) {
                      checkUserPermission(selectedUser.id, value);
                    }
                  }}
                  options={[
                  { value: '', label: t('admin2.gpm_select_permission_ph') },
                  ...permissions.map((perm) => ({
                    value: perm.codename,
                    label: `${perm.name} (${perm.codename})`
                  }))]
                  }
                  size="large"
                  className="w-full" />
                
                    </div>
                  </div>
                </div>
              </div> :

        <div className="admin-empty-sm-center-secondary">
                {t('admin2.gpm_select_user_hint')}
              </div>
        }
          </> :

      <div className="admin-empty-p-32-sm-secondary">
            <User className="admin-icon-48-mb-16-tertiary" />
            <p className="admin-m-0">{t('admin2.gpm_select_user_left')}</p>
          </div>
      }
      </MacOSCard>
    </div>;


  const renderGroupsTab = () =>
  <div className="admin-flex admin-gap-24">
      {/* Левая панель - список групп */}
      <MacOSCard className="admin-card-sidebar-300">
        <h3 className="admin-list-h3">
          <Users className="w-5 h-5" />
          {t('admin2.gpm_groups')}
        </h3>
        
        <Input
        placeholder={t('admin2.gpm_search_groups_ph')}
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="mb-4" />
      
        
        <div className="admin-max-h-400-overflow">
          {filteredGroups.map((group) =>
        <div
          key={group.id}
          role="button"
          tabIndex={0}
          onClick={() => {
            setSelectedGroup(group);
            loadGroupSummary(group.id);
          }}
          onKeyDown={(event) => handleActivationKeyDown(event, () => {
            setSelectedGroup(group);
            loadGroupSummary(group.id);
          })}
          className="admin-perm-list-item"
          style={{
            '--admin-list-bg': selectedGroup?.id === group.id ? 'var(--mac-accent-blue-light)' : 'transparent',
            '--admin-list-border': selectedGroup?.id === group.id ? 'var(--mac-accent-blue)' : 'transparent'
          } as CSSProperties}>
          
              <div className="admin-list-username">
                {group.display_name}
              </div>
              <div className="admin-list-sub-xs">
                {group.name}
              </div>
              <div className="admin-list-sub-tertiary-xs">
                {t('admin2.gpm_group_users_roles_summary', { users_count: group.users_count, roles_count: group.roles_count })}
              </div>
              <Badge variant={group.group_type === 'department' ? 'primary' : 'secondary'} className="admin-text-xs">
                {group.group_type}
              </Badge>
            </div>
        )}
        </div>
      </MacOSCard>

      {/* Правая панель - сводка группы */}
      <MacOSCard className="admin-card-main-flex-1">
        {selectedGroup ?
      <>
            <div className="admin-flex-between-mb-16">
              <h3 className="admin-header-h3-m0">
                <Shield className="w-5 h-5" />
                {t('admin2.gpm_group_title', { name: selectedGroup.display_name })}
              </h3>
              <Button
            onClick={() => loadGroupSummary(selectedGroup.id)}
            disabled={loading}>
            
                <RefreshCw className="w-4 h-4" />
                {t('admin2.gpm_refresh')}
              </Button>
            </div>

            {loading ?
        <div>
                <Skeleton height="20px" className="mb-2" />
                <Skeleton height="20px" className="mb-2" />
                <Skeleton height="20px" />
              </div> :
        groupSummary ?
        <div>
                <div className="mb-4">
                  <Badge variant="primary">
                    {t('admin2.gpm_group_users_count', { count: groupSummary.users_count })}
                  </Badge>
                  <Badge variant="secondary" className="admin-ml-8">
                    {t('admin2.gpm_group_roles_count', { count: groupSummary.roles.length })}
                  </Badge>
                  <Badge variant="info" className="admin-ml-8">
                    {t('admin2.gpm_group_permissions_count', { count: groupSummary.permissions_count })}
                  </Badge>
                </div>

                <div className="mb-6">
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_group_roles_section')}
                  </h4>
                  <div className="admin-flex-wrap-8-mb-8">
                    {groupSummary.roles.map((role) =>
              <div key={role.id} className="flex items-center justify-center gap-2">
                        <Badge variant="success">{role.display_name}</Badge>
                        <Button
                  type="button"
                  size="small"
                  variant="danger"
                  title={`Revoke ${role.display_name} from group`}
                  aria-label={`Revoke ${role.display_name} from group`}
                  onClick={() => revokeRoleFromGroup(selectedGroup.id, role.id)}>
                  
                          <Trash2 className="admin-icon-12" />
                        </Button>
                      </div>
              )}
                  </div>
                  
                  {/* Добавление новой роли */}
                  <div className="admin-flex-start-end admin-gap-8">
                    <div className="admin-flex-1">
                      <Select
                  value={roleToAssign}
                  onChange={(value) => {
                    setRoleToAssign(value);
                    if (value) {
                      assignRoleToGroup(selectedGroup.id, parseInt(value));
                      setRoleToAssign('');
                    }
                  }}
                  options={[
                  { value: '', label: t('admin2.gpm_select_role_ph') },
                  ...roles.filter((role) => !groupSummary.roles.some((gr) => gr.id === role.id)).map((role) => ({
                    value: role.id,
                    label: role.display_name
                  }))]
                  }
                  size="large"
                  className="w-full" />
                
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="admin-form-h4">
                    {t('admin2.gpm_permissions_by_category')}
                  </h4>
                  <div className="admin-max-h-300-overflow">
                    {Object.entries(groupSummary.permissions_by_category).map(([category, perms]: [string, any]) =>
              <div key={category} className="mb-4">
                        <h5 className="admin-perm-category-h5">
                          {category} ({perms.length})
                        </h5>
                        <div className="admin-perms-grid-200">
                          {perms.map((perm) =>
                  <div key={perm.codename} className="admin-perm-card-static">
                    
                              <div className="admin-perm-name">
                                {perm.name}
                              </div>
                              <div className="admin-perm-codename">
                                {perm.codename}
                              </div>
                            </div>
                  )}
                        </div>
                      </div>
              )}
                  </div>
                </div>
              </div> :

        <div className="admin-empty-sm-center-secondary">
                {t('admin2.gpm_loading_group_summary')}
              </div>
        }
          </> :

      <div className="admin-empty-p-32-sm-secondary">
            <Users className="admin-icon-48-mb-16-tertiary" />
            <p className="admin-m-0">{t('admin2.gpm_select_group_left')}</p>
          </div>
      }
      </MacOSCard>
    </div>;


  const renderCacheTab = () =>
  <MacOSCard className="p-6">
      <div className="admin-flex-between-mb-24">
        <h3 className="admin-header-h3-m0">
          <Settings className="w-5 h-5" />
          {t('admin2.gpm_cache_management')}
        </h3>
        <Button onClick={clearCache} variant="danger">
          <Trash2 className="w-4 h-4" />
          {t('admin2.gpm_clear_cache')}
        </Button>
      </div>

      {cacheStats &&
    <div className="admin-grid-auto-200">
          <MacOSCard className="admin-stat-banner-info">
            <div className="admin-flex-center-12">
              <Clock className="admin-icon-24-info" />
              <div>
                <div className="admin-stat-number-xl-bold">
                  {cacheStats.cache_ttl}{t('admin2.gpm_seconds_short')}
                </div>
                <div className="admin-text-sm-secondary">
                  {t('admin2.gpm_cache_ttl')}
                </div>
              </div>
            </div>
          </MacOSCard>

          <MacOSCard className="admin-stat-banner-success">
            <div className="admin-flex-center-12">
              <Users className="admin-icon-24-success" />
              <div>
                <div className="admin-stat-number-xl-bold">
                  {cacheStats.cache_size}
                </div>
                <div className="admin-text-sm-secondary">
                  {t('admin2.gpm_cache_entries')}
                </div>
              </div>
            </div>
          </MacOSCard>

          <MacOSCard className="admin-stat-banner-warning">
            <div className="admin-flex-center-12">
              <Key className="admin-icon-24-warning" />
              <div>
                <div className="admin-stat-number-xl-bold">
                  {cacheStats.cached_users.length}
                </div>
                <div className="admin-text-sm-secondary">
                  {t('admin2.gpm_cached_users_count')}
                </div>
              </div>
            </div>
          </MacOSCard>
        </div>
    }

      <div className="mt-6">
        <h4 className="admin-form-h4">
          {t('admin2.gpm_cached_users_section')}
        </h4>
        <div className="admin-cache-users-list">
          {cacheStats?.cached_users.map((userId) =>
        <Badge key={userId} variant="secondary">
              ID: {userId}
            </Badge>
        )}
        </div>
      </div>
    </MacOSCard>;


  return (
    <div style={containerStyle}>
      <div className="mb-6">
        <h1 className="admin-page-h1">
          <Shield className="admin-icon-32" />
          {t('admin2.gpm_page_title')}
        </h1>
        <p className="admin-page-p">
          {t('admin2.gpm_page_subtitle')}
        </p>
      </div>

      {/* Табы */}
      <div className="admin-tabs-scroll">
        <SegmentedControl
          aria-label={t('admin2.gpm_tabs_aria_label')}
          value={activeTab}
          onChange={(v: unknown) => setActiveTab(String(v))}
          options={[
            {
              value: 'users',
              label: (
                <span className="admin-inline-flex-center-8">
                  <User size={14} aria-hidden="true" />
                  {t('admin2.gpm_users')}
                </span>
              )
            },
            {
              value: 'groups',
              label: (
                <span className="admin-inline-flex-center-8">
                  <Users size={14} aria-hidden="true" />
                  {t('admin2.gpm_groups')}
                </span>
              )
            },
            {
              value: 'cache',
              label: (
                <span className="admin-inline-flex-center-8">
                  <Settings size={14} aria-hidden="true" />
                  {t('admin2.gpm_tab_cache')}
                </span>
              )
            }
          ]}
          size="large"
          className="admin-tabs-control-sidebar" />
      </div>

      {/* Содержимое табов */}
      {activeTab === 'users' && renderUsersTab()}
      {activeTab === 'groups' && renderGroupsTab()}
      {activeTab === 'cache' && renderCacheTab()}
    </div>);

};

export default GroupPermissionsManager;
