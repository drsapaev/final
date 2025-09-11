import React, { useState } from 'react';

const SimpleUserManagement = () => {
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
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#1976d2', marginBottom: '20px' }}>
        👥 Управление Пользователями
      </h1>

      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={() => setShowAddForm(!showAddForm)}
          style={{
            padding: '10px 20px',
            backgroundColor: '#4caf50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '16px'
          }}
        >
          {showAddForm ? 'Отмена' : '+ Добавить пользователя'}
        </button>
      </div>

      {showAddForm && (
        <div style={{
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px',
          backgroundColor: '#f9f9f9'
        }}>
          <h3>Добавить нового пользователя</h3>
          <div style={{ marginBottom: '10px' }}>
            <input
              type="text"
              placeholder="Имя пользователя"
              value={newUser.name}
              onChange={(e) => setNewUser({...newUser, name: e.target.value})}
              style={{ padding: '8px', marginRight: '10px', width: '200px' }}
            />
            <input
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={(e) => setNewUser({...newUser, email: e.target.value})}
              style={{ padding: '8px', marginRight: '10px', width: '200px' }}
            />
            <select
              value={newUser.role}
              onChange={(e) => setNewUser({...newUser, role: e.target.value})}
              style={{ padding: '8px', marginRight: '10px' }}
            >
              <option value="Врач">Врач</option>
              <option value="Медсестра">Медсестра</option>
              <option value="Администратор">Администратор</option>
              <option value="Лаборант">Лаборант</option>
            </select>
            <button 
              onClick={handleAddUser}
              style={{
                padding: '8px 16px',
                backgroundColor: '#1976d2',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Добавить
            </button>
          </div>
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse', 
          border: '1px solid #ddd',
          backgroundColor: 'white'
        }}>
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
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: user.status === 'Активен' ? '#4caf50' : '#f44336',
                    color: 'white',
                    fontSize: '12px'
                  }}>
                    {user.status}
                  </span>
                </td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <button
                    onClick={() => toggleUserStatus(user.id)}
                    style={{
                      padding: '4px 8px',
                      marginRight: '5px',
                      backgroundColor: user.status === 'Активен' ? '#ff9800' : '#4caf50',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    {user.status === 'Активен' ? 'Деактивировать' : 'Активировать'}
                  </button>
                  <button
                    onClick={() => deleteUser(user.id)}
                    style={{
                      padding: '4px 8px',
                      backgroundColor: '#f44336',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <p style={{ color: '#666' }}>
          Всего пользователей: <strong>{users.length}</strong> | 
          Активных: <strong>{users.filter(u => u.status === 'Активен').length}</strong>
        </p>
      </div>
    </div>
  );
};

export default SimpleUserManagement;
