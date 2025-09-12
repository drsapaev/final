// Тестовый компонент для проверки работоспособности всех созданных компонентов
import React, { useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { 
  ErrorBoundary, 
  ToastProvider, 
  useToast, 
  Loading, 
  ModalProvider, 
  useModal, 
  FormProvider, 
  useForm, 
  Table,
  RoleGuard,
  useRoleAccess
} from '../common';

/**
 * Тестовый компонент для проверки всех созданных компонентов
 */
function ComponentTestInner() {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;
  const { addToast } = useToast();
  const { openModal } = useModal();
  const { form, setValue, setError, validateForm } = useForm('test-form', { name: '', email: '' });
  const { profile, hasRole, isAdmin } = useRoleAccess();

  const [loading, setLoading] = useState(false);
  const [tableData, setTableData] = useState([
    { id: 1, name: 'Иван Иванов', email: 'ivan@example.com', role: 'admin' },
    { id: 2, name: 'Петр Петров', email: 'petr@example.com', role: 'doctor' },
    { id: 3, name: 'Анна Сидорова', email: 'anna@example.com', role: 'patient' }
  ]);

  const tableColumns = [
    { key: 'name', title: 'Имя', sortable: true },
    { key: 'email', title: 'Email', sortable: true },
    { key: 'role', title: 'Роль', sortable: true }
  ];

  const containerStyle = {
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'primary'),
    minHeight: '100vh'
  };

  const sectionStyle = {
    marginBottom: getSpacing('xl'),
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px',
    border: `1px solid ${getColor('border', 'light')}`
  };

  const titleStyle = {
    fontSize: getFontSize('lg'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('md')
  };

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    margin: getSpacing('xs'),
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: getFontSize('sm')
  };

  const inputStyle = {
    padding: getSpacing('sm'),
    margin: getSpacing('xs'),
    border: `1px solid ${getColor('border', 'main')}`,
    borderRadius: '4px',
    fontSize: getFontSize('sm')
  };

  const handleTestToast = (type) => {
    addToast({
      type,
      title: `Тест ${type}`,
      message: `Это тестовое уведомление типа ${type}`,
      duration: 3000
    });
  };

  const handleTestModal = () => {
    openModal({
      title: 'Тестовое модальное окно',
      content: (
        <div>
          <p>Это тестовое модальное окно для проверки работоспособности.</p>
          <p>Тема: {theme.isLight ? 'Светлая' : 'Темная'}</p>
        </div>
      ),
      footer: (
        <button style={buttonStyle} onClick={() => {}}>
          Закрыть
        </button>
      )
    });
  };

  const handleTestLoading = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 2000);
  };

  const handleFormSubmit = (values) => {
    console.log('Form submitted:', values);
    addToast({
      type: 'success',
      title: 'Форма отправлена',
      message: `Данные: ${JSON.stringify(values)}`
    });
  };

  const handleFormValidation = () => {
    const isValid = validateForm({
      name: { required: 'Имя обязательно' },
      email: { 
        required: 'Email обязателен',
        email: 'Некорректный email'
      }
    });
    
    if (isValid) {
      addToast({
        type: 'success',
        title: 'Валидация прошла',
        message: 'Все поля корректны'
      });
    } else {
      addToast({
        type: 'error',
        title: 'Ошибка валидации',
        message: 'Проверьте заполнение полей'
      });
    }
  };

  return (
    <div style={containerStyle}>
      <h1 style={{ ...titleStyle, fontSize: getFontSize('xl') }}>
        Тест компонентов системы
      </h1>

      {/* Тест темы */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Тема и стили</h2>
        <p>Текущая тема: {theme.isLight ? 'Светлая' : 'Темная'}</p>
        <p>Цвета: primary={getColor('primary', 'main')}, secondary={getColor('secondary', 'main')}</p>
        <p>Отступы: sm={getSpacing('sm')}, md={getSpacing('md')}, lg={getSpacing('lg')}</p>
        <p>Размеры шрифтов: sm={getFontSize('sm')}, md={getFontSize('md')}, lg={getFontSize('lg')}</p>
      </div>

      {/* Тест уведомлений */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Система уведомлений (Toast)</h2>
        <button style={buttonStyle} onClick={() => handleTestToast('success')}>
          Успех
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('error')}>
          Ошибка
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('warning')}>
          Предупреждение
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('info')}>
          Информация
        </button>
      </div>

      {/* Тест модальных окон */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Модальные окна</h2>
        <button style={buttonStyle} onClick={handleTestModal}>
          Открыть модальное окно
        </button>
      </div>

      {/* Тест загрузки */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Компоненты загрузки</h2>
        <button style={buttonStyle} onClick={handleTestLoading}>
          Тест загрузки (2 сек)
        </button>
        {loading && <Loading text="Загрузка..." />}
      </div>

      {/* Тест форм */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Система форм</h2>
        <form onSubmit={(e) => { e.preventDefault(); handleFormSubmit(form?.values); }}>
          <input
            type="text"
            placeholder="Имя"
            value={form?.values?.name || ''}
            onChange={(e) => setValue('name', e.target.value)}
            style={inputStyle}
          />
          <input
            type="email"
            placeholder="Email"
            value={form?.values?.email || ''}
            onChange={(e) => setValue('email', e.target.value)}
            style={inputStyle}
          />
          <button type="button" style={buttonStyle} onClick={handleFormValidation}>
            Проверить валидацию
          </button>
          <button type="submit" style={buttonStyle}>
            Отправить форму
          </button>
        </form>
      </div>

      {/* Тест таблиц */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Таблицы</h2>
        <Table
          data={tableData}
          columns={tableColumns}
          sortable={true}
          filterable={true}
          pagination={true}
          pageSize={2}
        />
      </div>

      {/* Тест ролевой системы */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>Ролевая система</h2>
        <p>Профиль: {profile ? JSON.stringify(profile) : 'Не авторизован'}</p>
        <p>Роль admin: {hasRole(['admin']) ? 'Да' : 'Нет'}</p>
        <p>Админ: {isAdmin() ? 'Да' : 'Нет'}</p>
        
        <RoleGuard allowedRoles={['admin']} fallback={<p>Доступ запрещен</p>}>
          <p>Этот контент виден только админам</p>
        </RoleGuard>
      </div>

      {/* Тест API */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>API интеграция</h2>
        <p>API клиент: {typeof window !== 'undefined' ? 'Доступен' : 'Недоступен'}</p>
        <p>Токен: {localStorage.getItem('auth_token') ? 'Есть' : 'Нет'}</p>
        <p>Профиль: {localStorage.getItem('auth_profile') ? 'Есть' : 'Нет'}</p>
      </div>
    </div>
  );
}

/**
 * Обертка с провайдерами для тестирования
 */
export default function ComponentTest() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ModalProvider>
          <FormProvider>
            <ComponentTestInner />
          </FormProvider>
        </ModalProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
