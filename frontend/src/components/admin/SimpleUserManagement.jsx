import React, { useState } from 'react';
import { Button, Card, Badge } from '../../design-system/components';
import { useTheme } from '../../contexts/ThemeContext';

const SimpleUserManagement = () => {
  const { getColor, getSpacing } = useTheme();
  const [users, setUsers] = useState([
    { id: 1, name: 'Иван Петров', role: 'Врач', email: 'ivan@clinic.com', status: 'Активен' },
    { id: 2, name: 'Мария Сидорова', role: 'Медсестра', email: 'maria@clinic.com', status: 'Активен' },
    { id: 3, name: 'Алексей Козлов', role: 'Администратор', email: 'alex@clinic.com', status: 'Активен' },
    { id: 4, name: 'Елена Волкова', role: 'Лаборант', email: 'elena@clinic.com', status: 'Неактивен' }
  ]);

  const [newUser, setNewUser] = useState({ name: '', role: 'Врач', email: '' });
  const [showAddForm, setShowAddForm] = useState(false);

  const handleAddUser = () => {
    if (newUser.name && newUser.email) {
      const user = {
        id: users.length + 1,
        name: newUser.name,
        role: newUser.role,
        email: newUser.email,
        status: 'Активен'
      };
      setUsers([...users, user]);
      setNewUser({ name: '', role: 'Врач', email: '' });
      setShowAddForm(false);
    }
  };

  const toggleUserStatus = (id) => {
    setUsers(users.map(user => 
      user.id === id 
        ? { ...user, status: user.status === 'Активен' ? 'Неактивен' : 'Активен' }
        : user
    ));
  };

  const deleteUser = (id) => {
    setUsers(users.filter(user => user.id !== id));
  };

  return (
    <div className="clinic-page clinic-p-lg">
      <div className="clinic-header">
        <h1>👥 Управление Пользователями</h1>
      </div>

      <div className="clinic-m-md">
        <Button 
          variant="primary"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? 'Отмена' : '+ Добавить пользователя'}
        </Button>
      </div>

      {showAddForm && (
        <Card className="clinic-m-md">
          <h3>Добавить нового пользователя</h3>
          <div className="clinic-flex clinic-gap-md clinic-m-md">
            <input
              type="text"
              placeholder="Имя пользователя"
              value={newUser.name}
              onChange={(e) => setNewUser({...newUser, name: e.target.value})}
              className="clinic-input"
              style={{ width: '200px' }}
            />
            <input
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={(e) => setNewUser({...newUser, email: e.target.value})}
              className="clinic-input"
              style={{ width: '200px' }}
            />
            <select
              value={newUser.role}
              onChange={(e) => setNewUser({...newUser, role: e.target.value})}
              className="clinic-input"
            >
              <option value="Врач">Врач</option>
              <option value="Медсестра">Медсестра</option>
              <option value="Администратор">Администратор</option>
              <option value="Лаборант">Лаборант</option>
            </select>
            <Button 
              variant="primary"
              onClick={handleAddUser}
            >
              Добавить
            </Button>
          </div>
        </Card>
      )}

      <Card className="clinic-m-md">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f5f5f5' }}>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>ID</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Имя</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Роль</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Email</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Статус</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id}>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{user.id}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{user.name}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{user.role}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{user.email}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <Badge 
                    variant={user.status === 'Активен' ? 'success' : 'danger'}
                  >
                    {user.status}
                  </Badge>
                </td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <div className="clinic-flex clinic-gap-sm">
                    <Button
                      variant={user.status === 'Активен' ? 'secondary' : 'primary'}
                      size="small"
                      onClick={() => toggleUserStatus(user.id)}
                    >
                      {user.status === 'Активен' ? 'Деактивировать' : 'Активировать'}
                    </Button>
                    <Button
                      variant="danger"
                      size="small"
                      onClick={() => deleteUser(user.id)}
                    >
                      Удалить
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
          </table>
        </div>
      </Card>

      <div className="clinic-text-center clinic-m-md">
        <p style={{ color: 'var(--text-secondary)' }}>
          Всего пользователей: <strong>{users.length}</strong> | 
          Активных: <strong>{users.filter(u => u.status === 'Активен').length}</strong>
        </p>
      </div>
    </div>
  );
};

export default SimpleUserManagement;
