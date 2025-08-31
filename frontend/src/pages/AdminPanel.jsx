import React, { useState, useEffect } from 'react';

const AdminPanel = () => {
  const [activeTab, setActiveTab] = useState('providers');
  const [providers, setProviders] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);

  // Форма провайдера
  const [providerForm, setProviderForm] = useState({
    name: '',
    code: '',
    is_active: true,
    webhook_url: '',
    api_key: '',
    secret_key: '',
    commission_percent: 0,
    min_amount: 0,
    max_amount: 100000000
  });

  useEffect(() => {
    loadProviders();
    loadUsers();
  }, []);

  const loadProviders = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/admin/providers', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setProviders(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки провайдеров:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    // Заглушка для пользователей
    setUsers([
      { id: 1, username: 'admin', role: 'Admin', active: true },
      { id: 2, username: 'registrar', role: 'Registrar', active: true },
      { id: 3, username: 'doctor', role: 'Doctor', active: true }
    ]);
  };

  const handleProviderSubmit = async (e) => {
    e.preventDefault();
    try {
      const url = editingProvider 
        ? `/api/v1/admin/providers/${editingProvider.id}`
        : '/api/v1/admin/providers';
      
      const method = editingProvider ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(providerForm)
      });

      if (response.ok) {
        setShowProviderForm(false);
        setEditingProvider(null);
        setProviderForm({
          name: '',
          code: '',
          is_active: true,
          webhook_url: '',
          api_key: '',
          secret_key: '',
          commission_percent: 0,
          min_amount: 0,
          max_amount: 100000000
        });
        loadProviders();
      }
    } catch (error) {
      console.error('Ошибка сохранения провайдера:', error);
    }
  };

  const handleEditProvider = (provider) => {
    setEditingProvider(provider);
    setProviderForm({
      name: provider.name,
      code: provider.code,
      is_active: provider.is_active,
      webhook_url: provider.webhook_url || '',
      api_key: provider.api_key || '',
      secret_key: provider.secret_key || '',
      commission_percent: provider.commission_percent,
      min_amount: provider.min_amount,
      max_amount: provider.max_amount
    });
    setShowProviderForm(true);
  };

  const handleDeleteProvider = async (providerId) => {
    if (window.confirm('Вы уверены, что хотите удалить этого провайдера?')) {
      try {
        const response = await fetch(`/api/v1/admin/providers/${providerId}`, {
          method: 'DELETE',
                  headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
        });
        
        if (response.ok) {
          loadProviders();
        }
      } catch (error) {
        console.error('Ошибка удаления провайдера:', error);
      }
    }
  };

  const testProvider = async (providerId) => {
    try {
      const response = await fetch(`/api/v1/admin/providers/${providerId}/test`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Тест провайдера: ${result.message}`);
      }
    } catch (error) {
      console.error('Ошибка тестирования провайдера:', error);
    }
  };

  // Стили
  const pageStyle = {
    padding: '20px',
    maxWidth: '1200px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  };

  const cardStyle = {
    background: '#fff',
    border: '1px solid #e5e5e5',
    borderRadius: '8px',
    marginBottom: '20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  };

  const cardHeaderStyle = {
    padding: '20px',
    borderBottom: '1px solid #e5e5e5',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  };

  const cardContentStyle = {
    padding: '20px'
  };

  const buttonStyle = {
    padding: '8px 16px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    marginRight: '8px',
    fontSize: '14px'
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    backgroundColor: '#6c757d'
  };

  const buttonDangerStyle = {
    ...buttonStyle,
    backgroundColor: '#dc3545'
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    marginBottom: '12px'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '4px',
    fontWeight: '500',
    fontSize: '14px'
  };

  const tabsStyle = {
    display: 'flex',
    borderBottom: '1px solid #e5e5e5',
    marginBottom: '20px'
  };

  const tabStyle = {
    padding: '12px 20px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    borderBottom: '2px solid transparent'
  };

  const activeTabStyle = {
    padding: '12px 20px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    borderBottom: '2px solid #007bff',
    color: '#007bff'
  };

  const badgeStyle = {
    padding: '4px 8px',
    fontSize: '12px',
    borderRadius: '12px',
    display: 'inline-block',
    marginLeft: '8px'
  };

  const badgeActiveStyle = {
    ...badgeStyle,
    backgroundColor: '#d4edda',
    color: '#155724'
  };

  const badgeInactiveStyle = {
    ...badgeStyle,
    backgroundColor: '#f8d7da',
    color: '#721c24'
  };

  const providerItemStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px',
    border: '1px solid #e5e5e5',
    borderRadius: '4px',
    marginBottom: '12px'
  };

  const formStyle = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px'
  };

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px' }}>
          Админ-панель
        </h1>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Управление системой, провайдерами оплат и пользователями
        </p>
      </div>

      {/* Вкладки */}
      <div style={tabsStyle}>
        <button
          style={activeTab === 'providers' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('providers')}
        >
          💳 Провайдеры
        </button>
        <button
          style={activeTab === 'users' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('users')}
        >
          👥 Пользователи
        </button>
        <button
          style={activeTab === 'settings' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('settings')}
        >
          ⚙️ Настройки
        </button>
        <button
          style={activeTab === 'system' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('system')}
        >
          📊 Система
        </button>
      </div>

      {/* Вкладка Провайдеры */}
      {activeTab === 'providers' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Провайдеры оплат</h2>
              <button 
                style={buttonStyle}
                onClick={() => setShowProviderForm(true)}
              >
                ➕ Добавить провайдера
              </button>
            </div>
            <div style={cardContentStyle}>
              {loading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>Загрузка...</div>
              ) : (
                <div>
                  {providers.map((provider) => (
                    <div key={provider.id} style={providerItemStyle}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                          <h3 style={{ margin: 0, fontSize: '16px' }}>{provider.name}</h3>
                          <span style={provider.is_active ? badgeActiveStyle : badgeInactiveStyle}>
                            {provider.is_active ? "Активен" : "Неактивен"}
                          </span>
                          <span style={{ ...badgeStyle, backgroundColor: '#f8f9fa', color: '#6c757d' }}>
                            {provider.code}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          Комиссия: {provider.commission_percent}% | 
                          Лимиты: {provider.min_amount} - {provider.max_amount} сум
                        </div>
                      </div>
                      <div>
                        <button
                          style={buttonSecondaryStyle}
                          onClick={() => testProvider(provider.id)}
                        >
                          🧪 Тест
                        </button>
                        <button
                          style={buttonStyle}
                          onClick={() => handleEditProvider(provider)}
                        >
                          ✏️ Изменить
                        </button>
                        <button
                          style={buttonDangerStyle}
                          onClick={() => handleDeleteProvider(provider.id)}
                        >
                          🗑️ Удалить
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Форма добавления/редактирования провайдера */}
          {showProviderForm && (
            <div style={cardStyle}>
              <div style={cardHeaderStyle}>
                <h2 style={{ margin: 0, fontSize: '18px' }}>
                  {editingProvider ? 'Редактировать провайдера' : 'Добавить провайдера'}
                </h2>
              </div>
              <div style={cardContentStyle}>
                <form onSubmit={handleProviderSubmit}>
                  <div style={formStyle}>
                    <div>
                      <label style={labelStyle}>Название</label>
                      <input
                        style={inputStyle}
                        value={providerForm.name}
                        onChange={(e) => setProviderForm({...providerForm, name: e.target.value})}
                        required
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Код</label>
                      <input
                        style={inputStyle}
                        value={providerForm.code}
                        onChange={(e) => setProviderForm({...providerForm, code: e.target.value})}
                        required
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label style={labelStyle}>Webhook URL</label>
                    <input
                      style={inputStyle}
                      value={providerForm.webhook_url}
                      onChange={(e) => setProviderForm({...providerForm, webhook_url: e.target.value})}
                      placeholder="https://example.com/webhook"
                    />
                  </div>

                  <div style={formStyle}>
                    <div>
                      <label style={labelStyle}>API Ключ</label>
                      <input
                        style={inputStyle}
                        value={providerForm.api_key}
                        onChange={(e) => setProviderForm({...providerForm, api_key: e.target.value})}
                        type="password"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Секретный ключ</label>
                      <input
                        style={inputStyle}
                        value={providerForm.secret_key}
                        onChange={(e) => setProviderForm({...providerForm, secret_key: e.target.value})}
                        type="password"
                      />
                    </div>
                  </div>

                  <div style={{ ...formStyle, gridTemplateColumns: '1fr 1fr 1fr' }}>
                    <div>
                      <label style={labelStyle}>Комиссия (%)</label>
                      <input
                        style={inputStyle}
                        type="number"
                                                 value={providerForm.commission_percent || 0}
                                                 onChange={(e) => setProviderForm({...providerForm, commission_percent: parseInt(e.target.value) || 0})}
                        min="0"
                        max="100"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Мин. сумма</label>
                      <input
                        style={inputStyle}
                        type="number"
                                                 value={providerForm.min_amount || 0}
                                                 onChange={(e) => setProviderForm({...providerForm, min_amount: parseInt(e.target.value) || 0})}
                        min="0"
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Макс. сумма</label>
                      <input
                        style={inputStyle}
                        type="number"
                                                 value={providerForm.max_amount || 0}
                                                 onChange={(e) => setProviderForm({...providerForm, max_amount: parseInt(e.target.value) || 0})}
                        min="0"
                      />
                    </div>
                  </div>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={providerForm.is_active}
                        onChange={(e) => setProviderForm({...providerForm, is_active: e.target.checked})}
                        style={{ marginRight: '8px' }}
                      />
                      Активен
                    </label>
                  </div>

                  <div>
                    <button type="submit" style={buttonStyle}>
                      {editingProvider ? 'Сохранить' : 'Добавить'}
                    </button>
                    <button
                      type="button"
                      style={buttonSecondaryStyle}
                      onClick={() => {
                        setShowProviderForm(false);
                        setEditingProvider(null);
                        setProviderForm({
                          name: '',
                          code: '',
                          is_active: true,
                          webhook_url: '',
                          api_key: '',
                          secret_key: '',
                          commission_percent: 0,
                          min_amount: 0,
                          max_amount: 100000000
                        });
                      }}
                    >
                      Отмена
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Вкладка Пользователи */}
      {activeTab === 'users' && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Управление пользователями</h2>
          </div>
          <div style={cardContentStyle}>
            <div>
              {users.map((user) => (
                <div key={user.id} style={providerItemStyle}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '16px' }}>{user.username}</h3>
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      Роль: {user.role}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={user.active ? badgeActiveStyle : badgeInactiveStyle}>
                      {user.active ? "Активен" : "Неактивен"}
                    </span>
                    <button style={buttonStyle}>
                      ✏️ Изменить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Вкладка Настройки */}
      {activeTab === 'settings' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>🌐 Общие настройки</h2>
            </div>
            <div style={cardContentStyle}>
              <div>
                <label style={labelStyle}>Название клиники</label>
                <input style={inputStyle} defaultValue="Programma Clinic" />
              </div>
              <div>
                <label style={labelStyle}>Часовой пояс</label>
                <input style={inputStyle} defaultValue="Asia/Tashkent" />
              </div>
              <div>
                <label style={labelStyle}>Время начала онлайн-очереди</label>
                <input style={inputStyle} type="time" defaultValue="07:00" />
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>🤖 AI настройки</h2>
            </div>
            <div style={cardContentStyle}>
              <div>
                <label style={labelStyle}>Провайдер AI</label>
                <select style={inputStyle} defaultValue="openai">
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                  <option value="deepseek">DeepSeek</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>API ключ AI</label>
                <input style={inputStyle} type="password" placeholder="sk-..." />
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>🖨️ Настройки печати</h2>
            </div>
            <div style={cardContentStyle}>
              <div>
                <label style={labelStyle}>Принтер по умолчанию</label>
                <input style={inputStyle} placeholder="EPSON TM-T88VI" />
              </div>
              <div>
                <label style={labelStyle}>Формат рецепта</label>
                <select style={inputStyle} defaultValue="a5">
                  <option value="a5">A5</option>
                  <option value="a4">A4</option>
                </select>
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>🛡️ Безопасность</h2>
            </div>
            <div style={cardContentStyle}>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" defaultChecked style={{ marginRight: '8px' }} />
                  Двухфакторная аутентификация
                </label>
              </div>
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                  <input type="checkbox" defaultChecked style={{ marginRight: '8px' }} />
                  Ведение аудиторского журнала
                </label>
              </div>
              <div>
                <label style={labelStyle}>Таймаут сессии (минуты)</label>
                <input style={inputStyle} type="number" defaultValue="30" min="5" max="480" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Вкладка Система */}
      {activeTab === 'system' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Статус системы</h2>
            </div>
            <div style={cardContentStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span>База данных:</span>
                <span style={badgeActiveStyle}>Онлайн</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span>Redis:</span>
                <span style={badgeActiveStyle}>Онлайн</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span>Веб-сервер:</span>
                <span style={badgeActiveStyle}>Онлайн</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Печать:</span>
                <span style={{ ...badgeStyle, backgroundColor: '#fff3cd', color: '#856404' }}>Проверить</span>
              </div>
            </div>
          </div>

          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Быстрые действия</h2>
            </div>
            <div style={cardContentStyle}>
              <button style={{ ...buttonStyle, width: '100%', marginBottom: '8px' }}>
                📊 Проверить здоровье системы
              </button>
              <button style={{ ...buttonStyle, width: '100%', marginBottom: '8px' }}>
                🛡️ Сканировать безопасность
              </button>
              <button style={{ ...buttonStyle, width: '100%', marginBottom: '8px' }}>
                🧪 Запустить тесты
              </button>
              <button style={{ ...buttonStyle, width: '100%' }}>
                ⚙️ Создать резервную копию
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminPanel;
