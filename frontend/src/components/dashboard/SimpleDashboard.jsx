import React from 'react';

const SimpleDashboard = () => {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#1976d2', marginBottom: '20px' }}>
        🏥 Простая Панель Управления
      </h1>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        <div style={{ 
          border: '1px solid #ddd', 
          borderRadius: '8px', 
          padding: '20px', 
          backgroundColor: '#f9f9f9' 
        }}>
          <h3>📊 Статистика</h3>
          <p>Пациентов сегодня: <strong>24</strong></p>
          <p>Записей на завтра: <strong>18</strong></p>
          <p>Врачей на смене: <strong>6</strong></p>
        </div>
        
        <div style={{ 
          border: '1px solid #ddd', 
          borderRadius: '8px', 
          padding: '20px', 
          backgroundColor: '#f0f8ff' 
        }}>
          <h3>⚡ Быстрые действия</h3>
          <button style={{ 
            margin: '5px', 
            padding: '10px 15px', 
            border: 'none', 
            borderRadius: '4px', 
            backgroundColor: '#1976d2', 
            color: 'white', 
            cursor: 'pointer' 
          }}>
            Добавить пациента
          </button>
          <button style={{ 
            margin: '5px', 
            padding: '10px 15px', 
            border: 'none', 
            borderRadius: '4px', 
            backgroundColor: '#4caf50', 
            color: 'white', 
            cursor: 'pointer' 
          }}>
            Новая запись
          </button>
        </div>
        
        <div style={{ 
          border: '1px solid #ddd', 
          borderRadius: '8px', 
          padding: '20px', 
          backgroundColor: '#fff3e0' 
        }}>
          <h3>🔔 Уведомления</h3>
          <p>✅ Система работает нормально</p>
          <p>⚠️ 3 записи требуют подтверждения</p>
          <p>📋 Обновление базы данных завершено</p>
        </div>
      </div>
      
      <div style={{ marginTop: '30px', textAlign: 'center' }}>
        <p style={{ color: '#666' }}>
          Это простая версия панели управления без Material-UI зависимостей
        </p>
      </div>
    </div>
  );
};

export default SimpleDashboard;
