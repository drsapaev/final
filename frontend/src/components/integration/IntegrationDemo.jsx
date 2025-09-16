import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../../design-system/components';
import { useQueueManager } from '../../hooks/useQueueManager';
import { useEMRAI } from '../../hooks/useEMRAI';
import { useAppData } from '../../contexts/AppDataContext';

/**
 * Демонстрационный компонент для проверки интеграции
 * Показывает работу всех созданных хуков и контекстов
 */
const IntegrationDemo = () => {
  const [activeDemo, setActiveDemo] = useState('queue');
  
  // Используем созданные хуки
  const queueManager = useQueueManager();
  const emrAI = useEMRAI();
  const { users, appointments, actions } = useAppData();

  // Локальные состояния для демо
  const [testSymptoms, setTestSymptoms] = useState('головная боль, тошнота');
  const [testDiagnosis, setTestDiagnosis] = useState('мигрень');

  useEffect(() => {
    // Имитируем загрузку данных при монтировании
    actions.setLoading('users', true);
    
    // Симулируем задержку API
    setTimeout(() => {
      actions.setUsers([
        { id: 1, name: 'Доктор Иванов', role: 'Doctor' },
        { id: 2, name: 'Медсестра Петрова', role: 'Nurse' }
      ]);
    }, 1000);
  }, [actions]);

  const handleQueueTest = async () => {
    const today = new Date().toISOString().split('T')[0];
    await queueManager.generateQRCode(today, '1');
  };

  const handleAITest = async () => {
    await emrAI.getICD10Suggestions(testSymptoms, testDiagnosis);
  };

  const renderQueueDemo = () => (
    <div className="clinic-space-y-md">
      <h3 className="clinic-heading-3">🔄 Тест Queue Manager Hook</h3>
      
      <div className="clinic-grid clinic-grid-cols-2 clinic-gap-md">
        <Card className="clinic-p-md">
          <h4>Специалисты</h4>
          {queueManager.loading ? (
            <p>Загрузка...</p>
          ) : (
            <div className="clinic-space-y-sm">
              {queueManager.specialists.map(specialist => (
                <div key={specialist.id} className="clinic-flex clinic-justify-between">
                  <span>{specialist.name}</span>
                  <Badge variant="info">{specialist.role}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
        
        <Card className="clinic-p-md">
          <h4>Действия</h4>
          <div className="clinic-space-y-sm">
            <Button 
              variant="primary" 
              onClick={handleQueueTest}
              disabled={queueManager.loading}
            >
              Генерировать QR
            </Button>
            
            {queueManager.qrData && (
              <div className="clinic-p-sm clinic-bg-success-light clinic-rounded">
                ✅ QR код сгенерирован: {queueManager.qrData.queue_url}
              </div>
            )}
          </div>
        </Card>
      </div>
      
      {queueManager.error && (
        <div className="clinic-p-md clinic-bg-danger-light clinic-text-danger clinic-rounded">
          ❌ Ошибка: {queueManager.error}
        </div>
      )}
      
      {queueManager.success && (
        <div className="clinic-p-md clinic-bg-success-light clinic-text-success clinic-rounded">
          ✅ {queueManager.success}
        </div>
      )}
    </div>
  );

  const renderAIDemo = () => (
    <div className="clinic-space-y-md">
      <h3 className="clinic-heading-3">🤖 Тест EMR AI Hook</h3>
      
      <div className="clinic-grid clinic-grid-cols-2 clinic-gap-md">
        <Card className="clinic-p-md">
          <h4>Входные данные</h4>
          <div className="clinic-space-y-sm">
            <div>
              <label className="clinic-label">Симптомы:</label>
              <input
                type="text"
                value={testSymptoms}
                onChange={(e) => setTestSymptoms(e.target.value)}
                className="clinic-input"
                placeholder="Введите симптомы"
              />
            </div>
            
            <div>
              <label className="clinic-label">Диагноз:</label>
              <input
                type="text"
                value={testDiagnosis}
                onChange={(e) => setTestDiagnosis(e.target.value)}
                className="clinic-input"
                placeholder="Введите диагноз"
              />
            </div>
            
            <Button 
              variant="primary" 
              onClick={handleAITest}
              disabled={emrAI.loading || (!testSymptoms && !testDiagnosis)}
            >
              {emrAI.loading ? 'Анализ...' : 'Получить МКБ-10'}
            </Button>
          </div>
        </Card>
        
        <Card className="clinic-p-md">
          <h4>AI Результаты</h4>
          {emrAI.loading ? (
            <p>🔄 Анализ данных...</p>
          ) : emrAI.icd10Suggestions.length > 0 ? (
            <div className="clinic-space-y-sm">
              {emrAI.icd10Suggestions.map((suggestion, index) => (
                <div key={index} className="clinic-p-sm clinic-border clinic-rounded">
                  <div className="clinic-font-semibold">{suggestion.code}</div>
                  <div className="clinic-text-sm clinic-text-secondary">
                    {suggestion.description}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="clinic-text-secondary">Нет результатов</p>
          )}
        </Card>
      </div>
      
      {emrAI.error && (
        <div className="clinic-p-md clinic-bg-danger-light clinic-text-danger clinic-rounded">
          ❌ Ошибка AI: {emrAI.error}
        </div>
      )}
    </div>
  );

  const renderContextDemo = () => (
    <div className="clinic-space-y-md">
      <h3 className="clinic-heading-3">📊 Тест App Data Context</h3>
      
      <div className="clinic-grid clinic-grid-cols-2 clinic-gap-md">
        <Card className="clinic-p-md">
          <h4>Пользователи из контекста</h4>
          {users.length > 0 ? (
            <div className="clinic-space-y-sm">
              {users.map(user => (
                <div key={user.id} className="clinic-flex clinic-justify-between">
                  <span>{user.name}</span>
                  <Badge variant="success">{user.role}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <p>Загрузка пользователей...</p>
          )}
        </Card>
        
        <Card className="clinic-p-md">
          <h4>Действия с контекстом</h4>
          <div className="clinic-space-y-sm">
            <Button 
              variant="secondary"
              onClick={() => actions.addUser({
                id: Date.now(),
                name: `Пользователь ${users.length + 1}`,
                role: 'Test'
              })}
            >
              Добавить пользователя
            </Button>
            
            <Button 
              variant="warning"
              onClick={() => actions.setUsers([])}
              disabled={users.length === 0}
            >
              Очистить список
            </Button>
          </div>
        </Card>
      </div>
      
      <div className="clinic-p-md clinic-bg-info-light clinic-rounded">
        <strong>Статистика:</strong>
        <ul className="clinic-mt-sm">
          <li>Пользователей в контексте: {users.length}</li>
          <li>Записей: {appointments.length}</li>
          <li>Активных загрузок: {Object.values(actions).filter(Boolean).length}</li>
        </ul>
      </div>
    </div>
  );

  return (
    <div className="clinic-page clinic-p-lg">
      <div className="clinic-header">
        <h1>🔧 Демо интеграции и размещения функций</h1>
        <p>Тестирование кастомных хуков, API интеграции и data flow</p>
      </div>

      {/* Навигация по демо */}
      <div className="clinic-flex clinic-gap-sm clinic-mb-lg">
        <Button
          variant={activeDemo === 'queue' ? 'primary' : 'secondary'}
          onClick={() => setActiveDemo('queue')}
        >
          Queue Manager
        </Button>
        <Button
          variant={activeDemo === 'ai' ? 'primary' : 'secondary'}
          onClick={() => setActiveDemo('ai')}
        >
          EMR AI
        </Button>
        <Button
          variant={activeDemo === 'context' ? 'primary' : 'secondary'}
          onClick={() => setActiveDemo('context')}
        >
          App Context
        </Button>
      </div>

      {/* Контент демо */}
      {activeDemo === 'queue' && renderQueueDemo()}
      {activeDemo === 'ai' && renderAIDemo()}
      {activeDemo === 'context' && renderContextDemo()}

      {/* Общая информация */}
      <Card className="clinic-mt-lg clinic-p-md clinic-bg-secondary">
        <h3>📋 Статус интеграции</h3>
        <div className="clinic-grid clinic-grid-cols-3 clinic-gap-md clinic-mt-md">
          <div className="clinic-text-center">
            <div className="clinic-text-2xl">✅</div>
            <div className="clinic-font-semibold">Хуки созданы</div>
            <div className="clinic-text-sm clinic-text-secondary">
              useQueueManager, useEMRAI
            </div>
          </div>
          
          <div className="clinic-text-center">
            <div className="clinic-text-2xl">🔄</div>
            <div className="clinic-font-semibold">API интеграция</div>
            <div className="clinic-text-sm clinic-text-secondary">
              Заменены прямые вызовы
            </div>
          </div>
          
          <div className="clinic-text-center">
            <div className="clinic-text-2xl">📊</div>
            <div className="clinic-font-semibold">Data Flow</div>
            <div className="clinic-text-sm clinic-text-secondary">
              Централизованное управление
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default IntegrationDemo;
