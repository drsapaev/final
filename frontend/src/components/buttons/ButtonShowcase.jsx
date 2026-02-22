import { useState } from 'react';
import {
  ModernButton,
  MedicalButton,
  EmergencyButton,
  DiagnoseButton,
  TreatButton,
  ApproveButton,
  RejectButton,
  CardiologyButton,
  LabButton,
  IconButton,
  FloatingActionButton } from





'./index';
import {
  Heart,
  Activity,
  Stethoscope,
  Pill,
  AlertTriangle,
  CheckCircle,

  TestTube,
  Plus,
  Settings,
  Save } from

'lucide-react';

/**
 * ButtonShowcase - демонстрация всех возможностей системы кнопок
 * Используется для тестирования и демонстрации новых функций
 */
const ButtonShowcase = () => {
  const [theme, setTheme] = useState('light');
  const [showMedical, setShowMedical] = useState(true);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  return (
    <div style={{
      padding: '2rem',
      background: 'var(--background)',
      color: 'var(--text-primary)',
      minHeight: '100vh'
    }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
        <h1 style={{ marginBottom: '1rem', color: 'var(--accent-primary)' }}>
          🏥 Система кнопок MediClinic Pro
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
          Современная дизайн-система кнопок для медицинских приложений
        </p>

        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '2rem' }}>
          <ModernButton
            variant="primary"
            onClick={toggleTheme}
            style={{ minWidth: '120px' }}>
            
            {theme === 'light' ? '🌙 Темная' : '☀️ Светлая'}
          </ModernButton>

          <ModernButton
            variant="secondary"
            onClick={() => setShowMedical(!showMedical)}
            style={{ minWidth: '120px' }}>
            
            {showMedical ? '🔄 Modern' : '⚕️ Medical'}
          </ModernButton>
        </div>
      </div>

      {showMedical ?
      <>
          {/* Медицинские кнопки */}
          <section style={{ marginBottom: '3rem' }}>
            <h2 style={{ color: 'var(--accent-primary)', marginBottom: '1.5rem' }}>
              🏥 Медицинские кнопки (семантические действия)
            </h2>

            {/* Экстренные случаи */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                🚨 Экстренные случаи
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <EmergencyButton
                priority="critical"
                onClick={() => alert('Экстренный вызов!')}>
                
                  Экстренный вызов
                </EmergencyButton>

                <MedicalButton
                action="emergency"
                priority="urgent"
                icon={AlertTriangle}>
                
                  Срочно
                </MedicalButton>

                <MedicalButton
                action="emergency"
                priority="high"
                status="active">
                
                  Высокий приоритет
                </MedicalButton>
              </div>
            </div>

            {/* Диагностика и лечение */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                🔍 Диагностика и лечение
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <DiagnoseButton
                onClick={() => alert('Начать диагностику')}>
                
                  Диагностировать
                </DiagnoseButton>

                <TreatButton
                icon={Pill}
                onClick={() => alert('Назначить лечение')}>
                
                  Лечение
                </TreatButton>

                <MedicalButton
                action="monitor"
                priority="normal"
                icon={Activity}
                status="active">
                
                  Мониторинг
                </MedicalButton>
              </div>
            </div>

            {/* Одобрение/отклонение */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                ✅ Управление решениями
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <ApproveButton
                onClick={() => alert('Одобрено')}
                status="success">
                
                  Одобрить
                </ApproveButton>

                <RejectButton
                onClick={() => alert('Отклонено')}
                status="error">
                
                  Отклонить
                </RejectButton>

                <MedicalButton
                action="prescribe"
                icon={CheckCircle}
                status="success">
                
                  Выписать рецепт
                </MedicalButton>
              </div>
            </div>

            {/* Медицинские отделы */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                🏥 Специализации
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <CardiologyButton
                icon={Heart}
                onClick={() => alert('Кардиология')}>
                
                  Кардиология
                </CardiologyButton>

                <MedicalButton
                department="dermatology"
                icon={Activity}>
                
                  Дерматология
                </MedicalButton>

                <MedicalButton
                department="dentistry"
                icon={Stethoscope}>
                
                  Стоматология
                </MedicalButton>

                <LabButton
                icon={TestTube}
                onClick={() => alert('Лаборатория')}>
                
                  Анализы
                </LabButton>
              </div>
            </div>
          </section>

          {/* Приоритеты и статусы */}
          <section style={{ marginBottom: '3rem' }}>
            <h2 style={{ color: 'var(--accent-primary)', marginBottom: '1.5rem' }}>
              📊 Приоритеты и статусы
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem' }}>
              {/* Приоритеты */}
              <div>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                  Приоритеты
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <MedicalButton priority="low">Низкий приоритет</MedicalButton>
                  <MedicalButton priority="normal">Нормальный приоритет</MedicalButton>
                  <MedicalButton priority="high">Высокий приоритет</MedicalButton>
                  <MedicalButton priority="urgent">Срочный</MedicalButton>
                  <MedicalButton priority="critical">Критический</MedicalButton>
                </div>
              </div>

              {/* Статусы */}
              <div>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                  Статусы
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <MedicalButton status="active">Активный</MedicalButton>
                  <MedicalButton status="inactive">Неактивный</MedicalButton>
                  <MedicalButton status="loading" loading>Загрузка</MedicalButton>
                  <MedicalButton status="success">Успех</MedicalButton>
                  <MedicalButton status="error">Ошибка</MedicalButton>
                </div>
              </div>
            </div>
          </section>
        </> :

      <>
          {/* Modern Button showcase */}
          <section style={{ marginBottom: '3rem' }}>
            <h2 style={{ color: 'var(--accent-primary)', marginBottom: '1.5rem' }}>
              🎨 Modern Button - базовые возможности
            </h2>

            {/* Варианты */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                Варианты цветов
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <ModernButton variant="primary">Primary</ModernButton>
                <ModernButton variant="secondary">Secondary</ModernButton>
                <ModernButton variant="success">Success</ModernButton>
                <ModernButton variant="warning">Warning</ModernButton>
                <ModernButton variant="danger">Danger</ModernButton>
                <ModernButton variant="info">Info</ModernButton>
                <ModernButton variant="light">Light</ModernButton>
                <ModernButton variant="dark">Dark</ModernButton>
              </div>
            </div>

            {/* Размеры */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                Размеры
              </h3>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <ModernButton size="small">Small</ModernButton>
                <ModernButton size="medium">Medium</ModernButton>
                <ModernButton size="large">Large</ModernButton>
              </div>
            </div>

            {/* Стили */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                Стили
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <ModernButton outlined>Outlined</ModernButton>
                <ModernButton ghost>Ghost</ModernButton>
                <ModernButton rounded>Rounded</ModernButton>
                <ModernButton fullWidth style={{ maxWidth: '200px' }}>Full Width</ModernButton>
              </div>
            </div>

            {/* С иконками */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                С иконками
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <ModernButton icon={Heart} iconPosition="left">Слева</ModernButton>
                <ModernButton icon={Activity} iconPosition="right">Справа</ModernButton>
                <IconButton icon={Settings} tooltip="Настройки" />
                <IconButton icon={Save} size="large" variant="success" />
              </div>
            </div>

            {/* Состояния */}
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>
                Состояния
              </h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <ModernButton disabled>Disabled</ModernButton>
                <ModernButton loading>Loading</ModernButton>
                <ModernButton pulsing>Pulsing</ModernButton>
                <ModernButton elevated>Elevated</ModernButton>
              </div>
            </div>
          </section>

          {/* Floating Action Button */}
          <section style={{ marginBottom: '3rem' }}>
            <h2 style={{ color: 'var(--accent-primary)', marginBottom: '1.5rem' }}>
              ➕ Floating Action Button
            </h2>

            <div style={{
            position: 'relative',
            height: '200px',
            border: '2px dashed var(--border)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--surface)'
          }}>
              <FloatingActionButton
              position="bottom-right"
              actions={[
              {
                icon: Plus,
                label: 'Добавить пациента',
                onClick: () => alert('Добавить пациента'),
                variant: 'primary'
              },
              {
                icon: Heart,
                label: 'ЭКГ',
                onClick: () => alert('ЭКГ'),
                variant: 'cardiology'
              },
              {
                icon: TestTube,
                label: 'Анализы',
                onClick: () => alert('Анализы'),
                variant: 'laboratory'
              }]
              }
              tooltip="Быстрые действия"
              style={{
                position: 'absolute',
                bottom: '20px',
                right: '20px'
              }} />
            

              <p style={{ color: 'var(--text-secondary)' }}>
                FAB с действиями в правом нижнем углу
              </p>
            </div>
          </section>
        </>
      }

      {/* Footer */}
      <div style={{
        textAlign: 'center',
        padding: '2rem 0',
        borderTop: '1px solid var(--border)',
        marginTop: '3rem'
      }}>
        <p style={{ color: 'var(--text-secondary)' }}>
          🎨 Система кнопок MediClinic Pro | v2.1.0
        </p>
        <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
          Современный дизайн • Медицинская семантика • Полная доступность
        </p>
      </div>
    </div>);

};

export default ButtonShowcase;