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
import { Card, Button, Badge, Input, Select, Label, Skeleton } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const GroupPermissionsManager = () => {
  const { theme, getColor, getSpacing } = useTheme();
  
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
      console.error('Ошибка загрузки данных:', error);
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
      console.error('Ошибка загрузки разрешений пользователя:', error);
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
      console.error('Ошибка загрузки сводки группы:', error);
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
      console.error('Ошибка проверки разрешения:', error);
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
      console.error('Ошибка назначения роли:', error);
      toast.error(error.response?.data?.detail || 'Ошибка назначения роли');
    }
  };

  const revokeRoleFromGroup = async (groupId, roleId) => {
    try {
      const response = await api.delete(`/admin/permissions/groups/${groupId}/roles/${roleId}`);
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      console.error('Ошибка отзыва роли:', error);
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
      console.error('Ошибка добавления пользователя:', error);
      toast.error(error.response?.data?.detail || 'Ошибка добавления пользователя');
    }
  };

  const removeUserFromGroup = async (groupId, userId) => {
    try {
      const response = await api.delete(`/admin/permissions/groups/${groupId}/users/${userId}`);
      
      toast.success(response.data.message);
      await loadGroupSummary(groupId);
    } catch (error) {
      console.error('Ошибка удаления пользователя:', error);
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
      console.error('Ошибка создания переопределения:', error);
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
      console.error('Ошибка очистки кэша:', error);
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
    padding: getSpacing('lg'),
    minHeight: '100vh',
    backgroundColor: theme === 'light' ? getColor('gray', 50) : getColor('gray', 900)
  };

  const tabStyle = (isActive) => ({
    padding: `${getSpacing('sm')} ${getSpacing('md')}`,
    backgroundColor: isActive 
      ? (theme === 'light' ? getColor('blue', 500) : getColor('blue', 600))
      : 'transparent',
    color: isActive 
      ? 'white' 
      : (theme === 'light' ? getColor('gray', 700) : getColor('gray', 300)),
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('xs')
  });

  const renderUsersTab = () => (
    <div style={{ display: 'flex', gap: getSpacing('lg') }}>
      {/* Левая панель - список пользователей */}
      <Card style={{ flex: '0 0 300px', padding: getSpacing('md') }}>
        <h3 style={{ margin: `0 0 ${getSpacing('md')} 0`, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <Users size={20} />
          Пользователи
        </h3>
        
        <Input
          placeholder="Поиск пользователей..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ marginBottom: getSpacing('md') }}
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
                padding: getSpacing('sm'),
                borderRadius: '6px',
                cursor: 'pointer',
                backgroundColor: selectedUser?.id === user.id 
                  ? (theme === 'light' ? getColor('blue', 100) : getColor('blue', 900))
                  : 'transparent',
                marginBottom: getSpacing('xs'),
                border: selectedUser?.id === user.id 
                  ? `2px solid ${getColor('blue', 500)}`
                  : '1px solid transparent'
              }}
            >
              <div style={{ fontWeight: 'bold' }}>{user.username}</div>
              <div style={{ fontSize: '0.875rem', color: getColor('gray', 600) }}>
                {user.full_name || 'Без имени'}
              </div>
              <div style={{ fontSize: '0.75rem', color: getColor('gray', 500) }}>
                Роль: {user.role}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Правая панель - разрешения пользователя */}
      <Card style={{ flex: 1, padding: getSpacing('md') }}>
        {selectedUser ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: getSpacing('md') }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                <Shield size={20} />
                Разрешения: {selectedUser.username}
              </h3>
              <Button
                onClick={() => loadUserPermissions(selectedUser.id)}
                disabled={loading}
              >
                <RefreshCw size={16} />
                Обновить
              </Button>
            </div>

            {loading ? (
              <div>
                <Skeleton height="20px" style={{ marginBottom: getSpacing('sm') }} />
                <Skeleton height="20px" style={{ marginBottom: getSpacing('sm') }} />
                <Skeleton height="20px" />
              </div>
            ) : userPermissions ? (
              <div>
                <div style={{ marginBottom: getSpacing('md') }}>
                  <Badge variant="primary">
                    Всего разрешений: {userPermissions.permissions_count}
                  </Badge>
                  <Badge variant="secondary" style={{ marginLeft: getSpacing('xs') }}>
                    Ролей: {userPermissions.roles.length}
                  </Badge>
                  <Badge variant="info" style={{ marginLeft: getSpacing('xs') }}>
                    Групп: {userPermissions.groups.length}
                  </Badge>
                </div>

                <div style={{ marginBottom: getSpacing('lg') }}>
                  <h4>Роли:</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: getSpacing('xs') }}>
                    {userPermissions.roles.map(role => (
                      <Badge key={role} variant="success">{role}</Badge>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: getSpacing('lg') }}>
                  <h4>Группы:</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: getSpacing('xs') }}>
                    {userPermissions.groups.map(group => (
                      <Badge key={group} variant="info">{group}</Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <h4>Разрешения:</h4>
                  <div style={{ 
                    maxHeight: '300px', 
                    overflowY: 'auto',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                    gap: getSpacing('xs')
                  }}>
                    {userPermissions.permissions.map(permission => (
                      <div
                        key={permission}
                        style={{
                          padding: getSpacing('xs'),
                          backgroundColor: theme === 'light' ? getColor('green', 50) : getColor('green', 900),
                          borderRadius: '4px',
                          fontSize: '0.875rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: getSpacing('xs')
                        }}
                      >
                        <CheckCircle size={14} color={getColor('green', 600)} />
                        {permission}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Инструменты проверки разрешений */}
                <div style={{ marginTop: getSpacing('lg'), padding: getSpacing('md'), backgroundColor: theme === 'light' ? getColor('gray', 100) : getColor('gray', 800), borderRadius: '8px' }}>
                  <h4>Проверить разрешение:</h4>
                  <div style={{ display: 'flex', gap: getSpacing('sm'), alignItems: 'end' }}>
                    <div style={{ flex: 1 }}>
                      <Label>Код разрешения:</Label>
                      <Select
                        onChange={(e) => {
                          if (e.target.value) {
                            checkUserPermission(selectedUser.id, e.target.value);
                          }
                        }}
                      >
                        <option value="">Выберите разрешение...</option>
                        {permissions.map(perm => (
                          <option key={perm.id} value={perm.codename}>
                            {perm.name} ({perm.codename})
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: getColor('gray', 500) }}>
                Выберите пользователя для просмотра разрешений
              </div>
            )}
          </>
        ) : (
          <div style={{ textAlign: 'center', color: getColor('gray', 500), padding: getSpacing('xl') }}>
            <User size={48} style={{ marginBottom: getSpacing('md') }} />
            <p>Выберите пользователя из списка слева</p>
          </div>
        )}
      </Card>
    </div>
  );

  const renderGroupsTab = () => (
    <div style={{ display: 'flex', gap: getSpacing('lg') }}>
      {/* Левая панель - список групп */}
      <Card style={{ flex: '0 0 300px', padding: getSpacing('md') }}>
        <h3 style={{ margin: `0 0 ${getSpacing('md')} 0`, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <Users size={20} />
          Группы
        </h3>
        
        <Input
          placeholder="Поиск групп..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ marginBottom: getSpacing('md') }}
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
                padding: getSpacing('sm'),
                borderRadius: '6px',
                cursor: 'pointer',
                backgroundColor: selectedGroup?.id === group.id 
                  ? (theme === 'light' ? getColor('blue', 100) : getColor('blue', 900))
                  : 'transparent',
                marginBottom: getSpacing('xs'),
                border: selectedGroup?.id === group.id 
                  ? `2px solid ${getColor('blue', 500)}`
                  : '1px solid transparent'
              }}
            >
              <div style={{ fontWeight: 'bold' }}>{group.display_name}</div>
              <div style={{ fontSize: '0.875rem', color: getColor('gray', 600) }}>
                {group.name}
              </div>
              <div style={{ fontSize: '0.75rem', color: getColor('gray', 500) }}>
                Пользователей: {group.users_count} | Ролей: {group.roles_count}
              </div>
              <Badge variant={group.group_type === 'department' ? 'primary' : 'secondary'} style={{ fontSize: '0.7rem' }}>
                {group.group_type}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Правая панель - сводка группы */}
      <Card style={{ flex: 1, padding: getSpacing('md') }}>
        {selectedGroup ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: getSpacing('md') }}>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                <Shield size={20} />
                Группа: {selectedGroup.display_name}
              </h3>
              <Button
                onClick={() => loadGroupSummary(selectedGroup.id)}
                disabled={loading}
              >
                <RefreshCw size={16} />
                Обновить
              </Button>
            </div>

            {loading ? (
              <div>
                <Skeleton height="20px" style={{ marginBottom: getSpacing('sm') }} />
                <Skeleton height="20px" style={{ marginBottom: getSpacing('sm') }} />
                <Skeleton height="20px" />
              </div>
            ) : groupSummary ? (
              <div>
                <div style={{ marginBottom: getSpacing('md') }}>
                  <Badge variant="primary">
                    Пользователей: {groupSummary.users_count}
                  </Badge>
                  <Badge variant="secondary" style={{ marginLeft: getSpacing('xs') }}>
                    Ролей: {groupSummary.roles.length}
                  </Badge>
                  <Badge variant="info" style={{ marginLeft: getSpacing('xs') }}>
                    Разрешений: {groupSummary.permissions_count}
                  </Badge>
                </div>

                <div style={{ marginBottom: getSpacing('lg') }}>
                  <h4>Роли группы:</h4>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: getSpacing('xs'), marginBottom: getSpacing('sm') }}>
                    {groupSummary.roles.map(role => (
                      <div key={role.id} style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                        <Badge variant="success">{role.display_name}</Badge>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => revokeRoleFromGroup(selectedGroup.id, role.id)}
                        >
                          <Trash2 size={12} />
                        </Button>
                      </div>
                    ))}
                  </div>
                  
                  {/* Добавление новой роли */}
                  <div style={{ display: 'flex', gap: getSpacing('sm'), alignItems: 'end' }}>
                    <div style={{ flex: 1 }}>
                      <Label>Добавить роль:</Label>
                      <Select
                        onChange={(e) => {
                          if (e.target.value) {
                            assignRoleToGroup(selectedGroup.id, parseInt(e.target.value));
                            e.target.value = '';
                          }
                        }}
                      >
                        <option value="">Выберите роль...</option>
                        {roles.filter(role => !groupSummary.roles.some(gr => gr.id === role.id)).map(role => (
                          <option key={role.id} value={role.id}>
                            {role.display_name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                </div>

                <div>
                  <h4>Разрешения по категориям:</h4>
                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {Object.entries(groupSummary.permissions_by_category).map(([category, perms]) => (
                      <div key={category} style={{ marginBottom: getSpacing('md') }}>
                        <h5 style={{ 
                          color: getColor('blue', 600),
                          textTransform: 'capitalize',
                          marginBottom: getSpacing('xs')
                        }}>
                          {category} ({perms.length})
                        </h5>
                        <div style={{ 
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                          gap: getSpacing('xs'),
                          paddingLeft: getSpacing('md')
                        }}>
                          {perms.map(perm => (
                            <div
                              key={perm.codename}
                              style={{
                                padding: getSpacing('xs'),
                                backgroundColor: theme === 'light' ? getColor('green', 50) : getColor('green', 900),
                                borderRadius: '4px',
                                fontSize: '0.875rem'
                              }}
                            >
                              <div style={{ fontWeight: 'bold' }}>{perm.name}</div>
                              <div style={{ fontSize: '0.75rem', color: getColor('gray', 600) }}>
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
              <div style={{ textAlign: 'center', color: getColor('gray', 500) }}>
                Загрузка сводки группы...
              </div>
            )}
          </>
        ) : (
          <div style={{ textAlign: 'center', color: getColor('gray', 500), padding: getSpacing('xl') }}>
            <Users size={48} style={{ marginBottom: getSpacing('md') }} />
            <p>Выберите группу из списка слева</p>
          </div>
        )}
      </Card>
    </div>
  );

  const renderCacheTab = () => (
    <Card style={{ padding: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: getSpacing('lg') }}>
        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
          <Settings size={20} />
          Управление кэшем разрешений
        </h3>
        <Button onClick={clearCache} variant="danger">
          <Trash2 size={16} />
          Очистить кэш
        </Button>
      </div>

      {cacheStats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md') }}>
          <Card style={{ padding: getSpacing('md'), backgroundColor: theme === 'light' ? getColor('blue', 50) : getColor('blue', 900) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
              <Clock size={24} color={getColor('blue', 600)} />
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{cacheStats.cache_ttl}с</div>
                <div style={{ fontSize: '0.875rem', color: getColor('gray', 600) }}>TTL кэша</div>
              </div>
            </div>
          </Card>

          <Card style={{ padding: getSpacing('md'), backgroundColor: theme === 'light' ? getColor('green', 50) : getColor('green', 900) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
              <Users size={24} color={getColor('green', 600)} />
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{cacheStats.cache_size}</div>
                <div style={{ fontSize: '0.875rem', color: getColor('gray', 600) }}>Записей в кэше</div>
              </div>
            </div>
          </Card>

          <Card style={{ padding: getSpacing('md'), backgroundColor: theme === 'light' ? getColor('purple', 50) : getColor('purple', 900) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
              <Key size={24} color={getColor('purple', 600)} />
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{cacheStats.cached_users.length}</div>
                <div style={{ fontSize: '0.875rem', color: getColor('gray', 600) }}>Пользователей в кэше</div>
              </div>
            </div>
          </Card>
        </div>
      )}

      <div style={{ marginTop: getSpacing('lg') }}>
        <h4>Пользователи в кэше:</h4>
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: getSpacing('xs'),
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
      <div style={{ marginBottom: getSpacing('lg') }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: '1.875rem', 
          fontWeight: 'bold',
          color: theme === 'light' ? getColor('gray', 900) : getColor('gray', 100),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Shield size={32} />
          Управление разрешениями групп
        </h1>
        <p style={{ 
          margin: `${getSpacing('sm')} 0 0 0`, 
          color: getColor('gray', 600) 
        }}>
          Управление ролями, группами и разрешениями пользователей
        </p>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        gap: getSpacing('sm'), 
        marginBottom: getSpacing('lg'),
        borderBottom: `1px solid ${theme === 'light' ? getColor('gray', 200) : getColor('gray', 700)}`,
        paddingBottom: getSpacing('sm')
      }}>
        <button
          style={tabStyle(activeTab === 'users')}
          onClick={() => setActiveTab('users')}
        >
          <User size={16} />
          Пользователи
        </button>
        <button
          style={tabStyle(activeTab === 'groups')}
          onClick={() => setActiveTab('groups')}
        >
          <Users size={16} />
          Группы
        </button>
        <button
          style={tabStyle(activeTab === 'cache')}
          onClick={() => setActiveTab('cache')}
        >
          <Settings size={16} />
          Кэш
        </button>
      </div>

      {/* Содержимое табов */}
      {activeTab === 'users' && renderUsersTab()}
      {activeTab === 'groups' && renderGroupsTab()}
      {activeTab === 'cache' && renderCacheTab()}
    </div>
  );
};

export default GroupPermissionsManager;

