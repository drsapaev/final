import { useTranslation } from '../hooks/useTranslation';
import { useTheme } from '../contexts/ThemeContext';
import { MacOSSelect, MacOSButton } from './ui/macos';

/**
 * Тестовый компонент для проверки работы селектора языка
 */
const LanguageTest = () => {
  const { language, setLanguage, t, availableLanguages } = useTranslation();
  const { isDark, toggleTheme } = useTheme();

  return (
    <div style={{
      padding: '20px',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      minHeight: '100vh'
    }}>
      <h1>🧪 Тест селектора языка</h1>

      <div style={{ marginBottom: '20px' }}>
        <h2>Информация о контексте:</h2>
        <p>Текущий язык: <strong>{language}</strong></p>
        <p>Функция t: <strong>{typeof t}</strong></p>
        <p>availableLanguages: <strong>{availableLanguages ? availableLanguages.length : 'undefined'}</strong></p>
        <p>Тема: <strong>{isDark ? 'темная' : 'светлая'}</strong></p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h2>Тест переводов:</h2>
        <p>title: {t('title')}</p>
        <p>loginButton: {t('loginButton')}</p>
        <p>address: {t('address')}</p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h2>Селектор языка:</h2>
        <MacOSSelect
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{ width: '200px' }}
        >
          {availableLanguages && availableLanguages.length > 0 ? (
            availableLanguages.map(lang => (
              <option key={lang.code} value={lang.code}>
                {lang.flag} {lang.name} ({lang.code.toUpperCase()})
              </option>
            ))
          ) : (
            <option disabled>Загрузка языков...</option>
          )}
        </MacOSSelect>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h2>Кнопка переключения темы:</h2>
        <MacOSButton onClick={toggleTheme}>
          Переключить на {isDark ? 'светлую' : 'темную'} тему
        </MacOSButton>
      </div>

      <div>
        <h2>Список доступных языков:</h2>
        {availableLanguages && availableLanguages.length > 0 ? (
          <ul>
            {availableLanguages.map(lang => (
              <li key={lang.code}>
                {lang.flag} {lang.name} - {lang.code}
              </li>
            ))}
          </ul>
        ) : (
          <p>availableLanguages не загружен</p>
        )}
      </div>
    </div>
  );
};

export default LanguageTest;
