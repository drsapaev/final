import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Shield, 
  Settings, 
  Plus, 
  Trash2, 
  Edit, 
  Search, 
  Filter,
  UserPlus,
  UserMinus,
  Key,
  Lock,
  Unlock,
  RefreshCw,
  Eye,
  AlertCircle,
  CheckCircle,
  Clock,
  User
} from 'lucide-react';
import { Card, Button, Badge, MacOSInput, MacOSSelect, Skeleton } from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const GroupPermissionsManager = () => {
  // Состояние
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  
  // Данные
  const [users, setUsers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [userPermissions, setUserPermissions] = useState(null);
  const [groupSummary, setGroupSummary] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);

  // Загрузка данных
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [groupsRes, rolesRes, permissionsRes, cacheRes] = await Promise.all([
        api.get('/admin/permissions/groups'),
        api.get('/admin/permissions/roles'),
        api.get('/admin/permissions/permissions'),
        api.get('/admin/permissions/cache/stats')
      ]);
      
      setGroups(groupsRes.data);
      setRoles(rolesRes.data);
      setPermissions(permissionsRes.data);
      setCacheStats(cacheRes.data.cache_stats);
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const loadUserPermissions = async (userId) => {
    if (!userId) return;
    
    setLoading(true);
    try {
      const response = await api.get(`/admin/permissions/users/${userId}/permissions`);
      setUserPermissions(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки разрешений пользователя:', error);
      toast.error('Ошибка загрузки разрешений пользователя');
    } finally {
      setLoading(false);
    }
  };

  const loadGroupSummary = async (groupId) => {
    if (!groupId) return;
    
    setLoading(true);
    try {
      const response = await api.get(`/admin/permissions/groups/${groupId}/permissions`);
      setGroupSummary(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки сводки группы:', error);
      toast.error('Ошибка загрузки сводки группы');
    } finally {
      setLoading(false);
    }
  };

  const checkUserPermission = async (userId, permission) => {
    try {
      const response = await api.get(`/admin/permissions/users/${userId}/permissions/check`, {
        params: { permission }
      });
      
      const hasPermission = response.data.has_permission;
      toast.success(
        hasPermission 
          ? `✅ У пользователя есть разрешение "${permission}"` 
          : `❌ У пользователя нет разрешения "${permission}"`
      );
    } catch (error) {
      logger.error('Ошибка проверки разрешения:', error);
      toast.error('Ошибка проверки разрешения');
    }
  };

  const assignRoleToGroup = async (groupId, roleId) => {
    try {
      const response = await api.post(`/admin/permissions/groups/${groupId}/roles`, {
        role_id: roleId
      });
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка назначения роли:', error);
      toast.error(error.response?.data?.detail || 'Ошибка назначения роли');
    }
  };

  const revokeRoleFromGroup = async (groupId, roleId) => {
    try {
      const response = await api.delete(`/admin/permissions/groups/${groupId}/roles/${roleId}`);
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка отзыва роли:', error);
      toast.error(error.response?.data?.detail || 'Ошибка отзыва роли');
    }
  };

  const addUserToGroup = async (groupId, userId) => {
    try {
      const response = await api.post(`/admin/permissions/groups/${groupId}/users`, {
        user_id: userId
      });
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка добавления пользователя:', error);
      toast.error(error.response?.data?.detail || 'Ошибка добавления пользователя');
    }
  };

  const removeUserFromGroup = async (groupId, userId) => {
    try {
      const response = await api.delete(`/admin/permissions/groups/${groupId}/users/${userId}`);
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      logger.error('Ошибка удаления пользователя:', error);
      toast.error(error.response?.data?.detail || 'Ошибка удаления пользователя');
    }
  };

  const createPermissionOverride = async (userId, permissionId, overrideType, reason, expiresHours) => {
    try {
      const response = await api.post('/admin/permissions/users/permission-override', {
        user_id: userId,
        permission_id: permissionId,
        override_type: overrideType,
        reason,
        expires_hours: expiresHours
      });
      
      toast.success(response.data.message);
      await loadUserPermissions(userId);
    } catch (error) {
      logger.error('Ошибка создания переопределения:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания переопределения');
    }
  };

  const clearCache = async () => {
    try {
      const response = await api.post('/admin/permissions/cache/clear');
      toast.success(response.data.message);
      
      // Обновляем статистику кэша
      const cacheRes = await api.get('/admin/permissions/cache/stats');
      setCacheStats(cacheRes.data.cache_stats);
    } catch (error) {
      logger.error('Ошибка очистки кэша:', error);
      toast.error('Ошибка очистки кэша');
    }
  };

  // Фильтрация данных
  const filteredGroups = groups.filter(group =>
    group.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    group.display_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredRoles = roles.filter(role =>
    role.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    role.display_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredPermissions = permissions.filter(permission =>
    permission.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    permission.codename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Стили
  const containerStyle = {
    padding: '24px',
    minHeight: '100vh',
    backgroundColor: 'var(--mac-bg-primary)'
  };

  const tabStyle = (isActive) => ({
    padding: '12px 16px',
    backgroundColor: isActive ? 'var(--mac-accent-blue)' : 'transparent',
    color: isActive ? 'white' : 'var(--mac-text-secondary)',
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)'
  });

  const renderUsersTab = () => (
    <div style={{ display: 'flex', gap: '24px' }}>
      {/* Левая панель - список пользователей */}
      <Card style={{ flex: '0 0 300px', padding: '16px' }}>
        <h3 style={{ 
          margin: '0 0 16px 0', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <Users style={{ width: '20px', height: '20px' }} />
          Пользователи
        </h3>
        
        <MacOSInput
          placeholder="Поиск пользователей..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ marginBottom: '16px' }}
        />
        
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          {users.map(user => (
            <div
              key={user.id}
              onClick={() => {
                setSelectedUser(user);
                loadUserPermissions(user.id);
              }}
              style={{
                padding: '12px',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: 'pointer',
                backgroundColor: selectedUser?.id === user.id 
                  ? 'var(--mac-accent-blue-light)'
                  : 'transparent',
                marginBottom: '8px',
                border: selectedUser?.id === user.id 
                  ? '2px solid var(--mac-accent-blue)'
                  : '1px solid transparent',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            >
              <div style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                {user.username}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                {user.full_name || 'Без имени'}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-tertiary)' 
              }}>
                Роль: {user.role}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Правая панель - разрешения пользователя */}
      <Card style={{ flex: 1, padding: '16px' }}>
        {selectedUser ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ 
                margin: 0, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>
                <Shield style={{ width: '20px', height: '20px' }} />
                Разрешения: {selectedUser.username}
              </h3>
              <Button
                onClick={() => loadUserPermissions(selectedUser.id)}
                disabled={loading}
              >
                <RefreshCw style={{ width: '16px', height: '16px' }} />
                Обновить
              </Button>
            </div>

            {loading ? (
              <div>
                <Skeleton height="20px" style={{ marginBottom: '8px' }} />
                <Skeleton height="20px" style={{ marginBottom: '8px' }} />
                <Skeleton height="20px" />
              </div>
            ) : userPermissions ? (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <Badge variant="primary">
                    Всего разрешений: {userPermissions.permissions_count}
                  </Badge>
                  <Badge variant="secondary" style={{ marginLeft: '8px' }}>
                    Ролей: {userPermissions.roles.length}
                  </Badge>
                  <Badge variant="info" style={{ marginLeft: '8px' }}>
                    Групп: {userPermissions.groups.length}
                  </Badge>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Роли:
                  </h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {userPermissions.roles.map(role => (
                      <Badge key={role} variant="success">{role}</Badge>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Группы:
                  </h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {userPermissions.groups.map(group => (
                      <Badge key={group} variant="info">{group}</Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Разрешения:
                  </h4>
                  <div style={{ 
                    maxHeight: '300px', 
                    overflowY: 'auto',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                    gap: '8px'
                  }}>
                    {userPermissions.permissions.map(permission => (
                      <div
                        key={permission}
                        style={{
                          padding: '8px',
                          backgroundColor: 'var(--mac-success-bg)',
                          borderRadius: 'var(--mac-radius-sm)',
                          fontSize: 'var(--mac-font-size-xs)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          border: '1px solid var(--mac-success-border)'
                        }}
                      >
                        <CheckCircle style={{ width: '14px', height: '14px', color: 'var(--mac-success)' }} />
                        {permission}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Инструменты проверки разрешений */}
                <div style={{ 
                  marginTop: '24px', 
                  padding: '16px', 
                  backgroundColor: 'var(--mac-bg-secondary)', 
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border)'
                }}>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Проверить разрешение:
                  </h4>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'end' }}>
                    <div style={{ flex: 1 }}>
                      <MacOSSelect
                        onChange={(e) => {
                          if (e.target.value) {
                            checkUserPermission(selectedUser.id, e.target.value);
                          }
                        }}
                        options={[
                          { value: '', label: 'Выберите разрешение...' },
                          ...permissions.map(perm => ({
                            value: perm.codename,
                            label: `${perm.name} (${perm.codename})`
                          }))
                        ]}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ 
                textAlign: 'center', 
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                Выберите пользователя для просмотра разрешений
              </div>
            )}
          </>
        ) : (
          <div style={{ 
            textAlign: 'center', 
            color: 'var(--mac-text-secondary)', 
            padding: '32px',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            <User style={{ width: '48px', height: '48px', marginBottom: '16px', color: 'var(--mac-text-tertiary)' }} />
            <p style={{ margin: 0 }}>Выберите пользователя из списка слева</p>
          </div>
        )}
      </Card>
    </div>
  );

  const renderGroupsTab = () => (
    <div style={{ display: 'flex', gap: '24px' }}>
      {/* Левая панель - список групп */}
      <Card style={{ flex: '0 0 300px', padding: '16px' }}>
        <h3 style={{ 
          margin: '0 0 16px 0', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <Users style={{ width: '20px', height: '20px' }} />
          Группы
        </h3>
        
        <MacOSInput
          placeholder="Поиск групп..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ marginBottom: '16px' }}
        />
        
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          {filteredGroups.map(group => (
            <div
              key={group.id}
              onClick={() => {
                setSelectedGroup(group);
                loadGroupSummary(group.id);
              }}
              style={{
                padding: '12px',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: 'pointer',
                backgroundColor: selectedGroup?.id === group.id 
                  ? 'var(--mac-accent-blue-light)'
                  : 'transparent',
                marginBottom: '8px',
                border: selectedGroup?.id === group.id 
                  ? '2px solid var(--mac-accent-blue)'
                  : '1px solid transparent',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            >
              <div style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                {group.display_name}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                {group.name}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-tertiary)' 
              }}>
                Пользователей: {group.users_count} | Ролей: {group.roles_count}
              </div>
              <Badge variant={group.group_type === 'department' ? 'primary' : 'secondary'} style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                {group.group_type}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Правая панель - сводка группы */}
      <Card style={{ flex: 1, padding: '16px' }}>
        {selectedGroup ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ 
                margin: 0, 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>
                <Shield style={{ width: '20px', height: '20px' }} />
                Группа: {selectedGroup.display_name}
              </h3>
              <Button
                onClick={() => loadGroupSummary(selectedGroup.id)}
                disabled={loading}
              >
                <RefreshCw style={{ width: '16px', height: '16px' }} />
                Обновить
              </Button>
            </div>

            {loading ? (
              <div>
                <Skeleton height="20px" style={{ marginBottom: '8px' }} />
                <Skeleton height="20px" style={{ marginBottom: '8px' }} />
                <Skeleton height="20px" />
              </div>
            ) : groupSummary ? (
              <div>
                <div style={{ marginBottom: '16px' }}>
                  <Badge variant="primary">
                    Пользователей: {groupSummary.users_count}
                  </Badge>
                  <Badge variant="secondary" style={{ marginLeft: '8px' }}>
                    Ролей: {groupSummary.roles.length}
                  </Badge>
                  <Badge variant="info" style={{ marginLeft: '8px' }}>
                    Разрешений: {groupSummary.permissions_count}
                  </Badge>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Роли группы:
                  </h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                    {groupSummary.roles.map(role => (
                      <div key={role.id} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Badge variant="success">{role.display_name}</Badge>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => revokeRoleFromGroup(selectedGroup.id, role.id)}
                        >
                          <Trash2 style={{ width: '12px', height: '12px' }} />
                        </Button>
                      </div>
                    ))}
                  </div>
                  
                  {/* Добавление новой роли */}
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'end' }}>
                    <div style={{ flex: 1 }}>
                      <MacOSSelect
                        onChange={(e) => {
                          if (e.target.value) {
                            assignRoleToGroup(selectedGroup.id, parseInt(e.target.value));
                            e.target.value = '';
                          }
                        }}
                        options={[
                          { value: '', label: 'Выберите роль...' },
                          ...roles.filter(role => !groupSummary.roles.some(gr => gr.id === role.id)).map(role => ({
                            value: role.id,
                            label: role.display_name
                          }))
                        ]}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>
                    Разрешения по категориям:
                  </h4>
                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {Object.entries(groupSummary.permissions_by_category).map(([category, perms]) => (
                      <div key={category} style={{ marginBottom: '16px' }}>
                        <h5 style={{ 
                          color: 'var(--mac-accent-blue)',
                          textTransform: 'capitalize',
                          marginBottom: '8px',
                          fontSize: 'var(--mac-font-size-sm)',
                          fontWeight: 'var(--mac-font-weight-medium)'
                        }}>
                          {category} ({perms.length})
                        </h5>
                        <div style={{ 
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                          gap: '8px',
                          paddingLeft: '16px'
                        }}>
                          {perms.map(perm => (
                            <div
                              key={perm.codename}
                              style={{
                                padding: '8px',
                                backgroundColor: 'var(--mac-success-bg)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: 'var(--mac-font-size-xs)',
                                border: '1px solid var(--mac-success-border)'
                              }}
                            >
                              <div style={{ 
                                fontWeight: 'var(--mac-font-weight-semibold)',
                                color: 'var(--mac-text-primary)'
                              }}>
                                {perm.name}
                              </div>
                              <div style={{ 
                                fontSize: 'var(--mac-font-size-xs)', 
                                color: 'var(--mac-text-secondary)' 
                              }}>
                                {perm.codename}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ 
                textAlign: 'center', 
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                Загрузка сводки группы...
              </div>
            )}
          </>
        ) : (
          <div style={{ 
            textAlign: 'center', 
            color: 'var(--mac-text-secondary)', 
            padding: '32px',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            <Users style={{ width: '48px', height: '48px', marginBottom: '16px', color: 'var(--mac-text-tertiary)' }} />
            <p style={{ margin: 0 }}>Выберите группу из списка слева</p>
          </div>
        )}
      </Card>
    </div>
  );

  const renderCacheTab = () => (
    <Card style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h3 style={{ 
          margin: 0, 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          <Settings style={{ width: '20px', height: '20px' }} />
          Управление кэшем разрешений
        </h3>
        <Button onClick={clearCache} variant="danger">
          <Trash2 style={{ width: '16px', height: '16px' }} />
          Очистить кэш
        </Button>
      </div>

      {cacheStats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <Card style={{ padding: '16px', backgroundColor: 'var(--mac-info-bg)', border: '1px solid var(--mac-info-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Clock style={{ width: '24px', height: '24px', color: 'var(--mac-info)' }} />
              <div>
                <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)' }}>
                  {cacheStats.cache_ttl}с
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  TTL кэша
                </div>
              </div>
            </div>
          </Card>

          <Card style={{ padding: '16px', backgroundColor: 'var(--mac-success-bg)', border: '1px solid var(--mac-success-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Users style={{ width: '24px', height: '24px', color: 'var(--mac-success)' }} />
              <div>
                <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)' }}>
                  {cacheStats.cache_size}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  Записей в кэше
                </div>
              </div>
            </div>
          </Card>

          <Card style={{ padding: '16px', backgroundColor: 'var(--mac-warning-bg)', border: '1px solid var(--mac-warning-border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Key style={{ width: '24px', height: '24px', color: 'var(--mac-warning)' }} />
              <div>
                <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)' }}>
                  {cacheStats.cached_users.length}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  Пользователей в кэше
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      <div style={{ marginTop: '24px' }}>
        <h4 style={{ 
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          marginBottom: '8px'
        }}>
          Пользователи в кэше:
        </h4>
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: '8px',
          maxHeight: '200px',
          overflowY: 'auto'
        }}>
          {cacheStats?.cached_users.map(userId => (
            <Badge key={userId} variant="secondary">
              ID: {userId}
            </Badge>
          ))}
        </div>
      </div>
    </Card>
  );

  return (
    <div style={containerStyle}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: 'var(--mac-font-size-2xl)', 
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <Shield style={{ width: '32px', height: '32px' }} />
          Управление разрешениями групп
        </h1>
        <p style={{ 
          margin: '8px 0 0 0', 
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          Управление ролями, группами и разрешениями пользователей
        </p>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        marginBottom: '24px'
      }}>
        <button
          onClick={() => setActiveTab('users')}
          style={{
            padding: '12px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: activeTab === 'users' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
            fontWeight: activeTab === 'users' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
            fontSize: 'var(--mac-font-size-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            position: 'relative',
            marginBottom: '-1px'
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'users') {
              e.target.style.color = 'var(--mac-text-primary)';
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'users') {
              e.target.style.color = 'var(--mac-text-secondary)';
            }
          }}
        >
          <User style={{ 
            width: '16px', 
            height: '16px',
            color: activeTab === 'users' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
          }} />
          Пользователи
          {activeTab === 'users' && (
            <div style={{
              position: 'absolute',
              bottom: '0',
              left: '0',
              right: '0',
              height: '3px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: '2px 2px 0 0'
            }} />
          )}
        </button>
        <button
          onClick={() => setActiveTab('groups')}
          style={{
            padding: '12px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: activeTab === 'groups' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
            fontWeight: activeTab === 'groups' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
            fontSize: 'var(--mac-font-size-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            position: 'relative',
            marginBottom: '-1px'
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'groups') {
              e.target.style.color = 'var(--mac-text-primary)';
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'groups') {
              e.target.style.color = 'var(--mac-text-secondary)';
            }
          }}
        >
          <Users style={{ 
            width: '16px', 
            height: '16px',
            color: activeTab === 'groups' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
          }} />
          Группы
          {activeTab === 'groups' && (
            <div style={{
              position: 'absolute',
              bottom: '0',
              left: '0',
              right: '0',
              height: '3px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: '2px 2px 0 0'
            }} />
          )}
        </button>
        <button
          onClick={() => setActiveTab('cache')}
          style={{
            padding: '12px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: activeTab === 'cache' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
            fontWeight: activeTab === 'cache' ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
            fontSize: 'var(--mac-font-size-sm)',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            position: 'relative',
            marginBottom: '-1px'
          }}
          onMouseEnter={(e) => {
            if (activeTab !== 'cache') {
              e.target.style.color = 'var(--mac-text-primary)';
            }
          }}
          onMouseLeave={(e) => {
            if (activeTab !== 'cache') {
              e.target.style.color = 'var(--mac-text-secondary)';
            }
          }}
        >
          <Settings style={{ 
            width: '16px', 
            height: '16px',
            color: activeTab === 'cache' ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
          }} />
          Кэш
          {activeTab === 'cache' && (
            <div style={{
              position: 'absolute',
              bottom: '0',
              left: '0',
              right: '0',
              height: '3px',
              backgroundColor: 'var(--mac-accent-blue)',
              borderRadius: '2px 2px 0 0'
            }} />
          )}
        </button>
      </div>
      
      {/* Разделительная линия */}
      <div style={{ 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }} />

      {/* Содержимое табов */}
      {activeTab === 'users' && renderUsersTab()}
      {activeTab === 'groups' && renderGroupsTab()}
      {activeTab === 'cache' && renderCacheTab()}
    </div>
  );
};

export default GroupPermissionsManager;

