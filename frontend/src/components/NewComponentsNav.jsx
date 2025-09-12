import React from 'react';
import { useNavigate } from 'react-router-dom';

const NewComponentsNav = () => {
  const navigate = useNavigate();

  const components = [
    {
      path: '/test',
      title: 'Test Component',
      description: 'Базовый тестовый компонент',
      icon: '🧪',
      color: '#4CAF50'
    },
    {
      path: '/simple-dashboard',
      title: 'Simple Dashboard',
      description: 'Простой дашборд с статистикой',
      icon: '📊',
      color: '#2196F3'
    },
    {
      path: '/simple-users',
      title: 'User Management',
      description: 'Управление пользователями',
      icon: '👥',
      color: '#FF9800'
    },
    {
      path: '/simple-emr',
      title: 'EMR Interface',
      description: 'Медицинские карты',
      icon: '🏥',
      color: '#9C27B0'
    },
    {
      path: '/simple-files',
      title: 'File Manager',
      description: 'Файловый менеджер',
      icon: '📁',
      color: '#607D8B'
    }
  ];

  return (
    <div style={{
      padding: '20px',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      minHeight: '100vh'
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto'
      }}>
        {/* Заголовок */}
        <div style={{
          textAlign: 'center',
          marginBottom: '40px',
          color: 'white'
        }}>
          <h1 style={{
            fontSize: '32px',
            fontWeight: 'bold',
            margin: '0 0 10px 0'
          }}>
            🚀 Новые компоненты системы
          </h1>
          <p style={{
            fontSize: '18px',
            margin: '0',
            opacity: 0.9
          }}>
            Выберите компонент для тестирования
          </p>
        </div>

        {/* Сетка компонентов */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '20px',
          marginBottom: '40px'
        }}>
          {components.map((component, index) => (
            <div
              key={component.path}
              onClick={() => navigate(component.path)}
              style={{
                background: 'white',
                borderRadius: '12px',
                padding: '24px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
                cursor: 'pointer',
                transition: 'all 0.3s ease',
                border: '2px solid transparent',
                position: 'relative',
                overflow: 'hidden'
              }}
              onMouseEnter={(e) => {
                e.target.style.transform = 'translateY(-5px)';
                e.target.style.boxShadow = '0 12px 40px rgba(0,0,0,0.15)';
                e.target.style.borderColor = component.color;
              }}
              onMouseLeave={(e) => {
                e.target.style.transform = 'translateY(0)';
                e.target.style.boxShadow = '0 8px 32px rgba(0,0,0,0.1)';
                e.target.style.borderColor = 'transparent';
              }}
            >
              {/* Иконка */}
              <div style={{
                fontSize: '48px',
                textAlign: 'center',
                marginBottom: '16px'
              }}>
                {component.icon}
              </div>

              {/* Заголовок */}
              <h3 style={{
                fontSize: '20px',
                fontWeight: 'bold',
                color: '#333',
                margin: '0 0 8px 0',
                textAlign: 'center'
              }}>
                {component.title}
              </h3>

              {/* Описание */}
              <p style={{
                color: '#666',
                fontSize: '14px',
                margin: '0 0 20px 0',
                textAlign: 'center',
                lineHeight: '1.5'
              }}>
                {component.description}
              </p>

              {/* Кнопка */}
              <div style={{
                textAlign: 'center'
              }}>
                <button
                  style={{
                    background: `linear-gradient(135deg, ${component.color} 0%, ${component.color}dd 100%)`,
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '12px 24px',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    width: '100%'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.transform = 'scale(1.05)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.transform = 'scale(1)';
                  }}
                >
                  Открыть →
                </button>
              </div>

              {/* Индекс */}
              <div style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                background: component.color,
                color: 'white',
                borderRadius: '50%',
                width: '24px',
                height: '24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {index + 1}
              </div>
            </div>
          ))}
        </div>

        {/* Навигация */}
        <div style={{
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '12px',
          padding: '20px',
          textAlign: 'center',
          backdropFilter: 'blur(10px)'
        }}>
          <h3 style={{
            color: 'white',
            margin: '0 0 16px 0',
            fontSize: '18px'
          }}>
            🔗 Быстрая навигация
          </h3>
          <div style={{
            display: 'flex',
            gap: '12px',
            justifyContent: 'center',
            flexWrap: 'wrap'
          }}>
            <button
              onClick={() => navigate('/')}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '6px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🏠 Главная
            </button>
            <button
              onClick={() => navigate('/login')}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '6px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🔐 Старый вход
            </button>
            <button
              onClick={() => navigate('/new-login')}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: 'white',
                border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: '6px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              ✨ Новый вход
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewComponentsNav;
