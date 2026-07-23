
import { useState, useEffect } from 'react';
import { Card, Button, Badge,
  Input } from '../ui/macos';
import { useQueueManager } from '../../hooks/useQueueManager';
import type { UseQueueManagerReturn } from '../../hooks/useQueueManager';
import { useEMRAI } from '../../hooks/useEMRAI';
import { useAppData } from '../../contexts/AppDataContext';
import { useTranslation } from '../../i18n/useTranslation';

// IntegrationDemo reads fields that don't exist on UseQueueManagerReturn
// (generateQRCode, error, success). This is pre-existing demo breakage —
// the demo was written against an older hook API. We extend the real
// return type with the missing fields so the demo compiles without
// forcing the production hook to add them.
interface IntegrationDemoQueueManager extends UseQueueManagerReturn {
  generateQRCode?: (date: string, specialistId: string) => Promise<unknown>;
  error?: string;
  success?: string;
}

/**
 * Демонстрационный компонент для проверки интеграции
 * Показывает работу всех созданных хуков и контекстов
 */
const IntegrationDemo = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeDemo, setActiveDemo] = useState('queue');

  // Используем созданные хуки
  const queueManager = useQueueManager() as unknown as IntegrationDemoQueueManager;
  const emrAI = useEMRAI();
  const { users, appointments, actions } = useAppData() as unknown as { users: unknown[]; appointments: unknown[]; actions: { setLoading: (key: string, v: boolean) => void; setUsers: (v: unknown[]) => void; [key: string]: unknown }; };

  // Локальные состояния для демо
  const [testSymptoms, setTestSymptoms] = useState(t('misc.id_golovnaya_bol_toshnota'));
  const [testDiagnosis, setTestDiagnosis] = useState(t('misc.id_migren'));

  useEffect(() => {
    // Имитируем загрузку данных при монтировании
    actions.setLoading('users', true);
    
    // Симулируем задержку API
    setTimeout(() => {
      actions.setUsers([
        { id: 1, name: t('misc.id_doktor_ivanov'), role: 'Doctor' },
        { id: 2, name: t('misc.id_medsestra_petrova'), role: 'Nurse' }
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
          <h4>{t('misc.id_spetsialisty')}</h4>
          {queueManager.loading ? (
            <p>{t('misc.id_zagruzka')}</p>
          ) : (
            <div className="clinic-space-y-sm">
              {queueManager.specialists.map((specialist: Record<string, unknown>) => (
                <div key={String(specialist.id)} className="clinic-flex clinic-justify-between">
                  <span>{String(specialist.name)}</span>
                  <Badge variant="info">{String(specialist.role)}</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
        
        <Card className="clinic-p-md">
          <h4>{t('misc.id_deystviya')}</h4>
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
                ✅ QR код сгенерирован: {String((queueManager.qrData as Record<string, unknown>).queue_url)}
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
          <h4>{t('misc.id_vhodnye_dannye')}</h4>
          <div className="clinic-space-y-sm">
            <div>
              <label className="clinic-label">{t('misc.id_simptomy')}</label>
              <Input
                type="text"
                aria-label="Test symptoms"
                value={testSymptoms}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setTestSymptoms(e.target.value)}
                className="clinic-input"
                placeholder={t('misc.id_vvedite_simptomy')}
              />
            </div>
            
            <div>
              <label className="clinic-label">{t('misc.id_diagnoz')}</label>
              <Input
                type="text"
                aria-label="Test diagnosis"
                value={testDiagnosis}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setTestDiagnosis(e.target.value)}
                className="clinic-input"
                placeholder={t('misc.id_vvedite_diagnoz')}
              />
            </div>
            
            <Button 
              variant="primary" 
              onClick={handleAITest}
              disabled={emrAI.loading || (!testSymptoms && !testDiagnosis)}
            >
              {emrAI.loading ? t('misc.id_analiz') : t('misc.id_poluchit_mkb_10')}
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
            <p className="clinic-text-secondary">{t('misc.id_net_rezultatov')}</p>
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
          <h4>{t('misc.id_polzovateli_iz_konteksta')}</h4>
          {users.length > 0 ? (
            <div className="clinic-space-y-sm">
              {users.map((user: Record<string, unknown>) => (
                <div key={String(user.id)} className="clinic-flex clinic-justify-between">
                  <span>{String(user.name)}</span>
                  <Badge variant="success">{String(user.role)}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <p>{t('misc.id_zagruzka_polzovateley')}</p>
          )}
        </Card>
        
        <Card className="clinic-p-md">
          <h4>{t('misc.id_deystviya_s_kontekstom')}</h4>
          <div className="clinic-space-y-sm">
            <Button 
              variant="secondary"
              onClick={() => (actions as unknown as { addUser: (user: unknown) => void }).addUser({
                id: Date.now(),
                name: t('misc.id_polzovatel_users_length_1', { length: users.length + 1 }),
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
        <strong>{t('misc.id_statistika')}</strong>
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
        <p>{t('misc.id_testirovanie_kastomnyh_hukov')}</p>
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
            <div className="clinic-font-semibold">{t('misc.id_huki_sozdany')}</div>
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

