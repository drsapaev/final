import React from 'react';
import { Button, Card, Badge } from '../../design-system/components';

const SimpleDashboard = () => {
  return (
    <div className="clinic-page clinic-p-lg">
      <div className="clinic-header">
        <h1>🏥 Простая Панель Управления</h1>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        <Card>
          <h3>📊 Статистика</h3>
          <p>Пациентов сегодня: <Badge variant="info">24</Badge></p>
          <p>Записей на завтра: <Badge variant="warning">18</Badge></p>
          <p>Врачей на смене: <Badge variant="success">6</Badge></p>
        </Card>
        
        <Card>
          <h3>⚡ Быстрые действия</h3>
          <div className="clinic-flex clinic-flex-col clinic-gap-sm">
            <Button variant="primary">
              Добавить пациента
            </Button>
            <Button variant="success">
              Новая запись
            </Button>
          </div>
        </Card>
        
        <Card>
          <h3>🔔 Уведомления</h3>
          <p>✅ Система работает нормально</p>
          <p>⚠️ 3 записи требуют подтверждения</p>
          <p>📋 Обновление базы данных завершено</p>
        </Card>
      </div>
      
      <div className="clinic-text-center clinic-m-lg">
        <p style={{ color: 'var(--text-secondary)' }}>
          Это простая версия панели управления без Material-UI зависимостей
        </p>
      </div>
    </div>
  );
};

export default SimpleDashboard;
