import { useTranslation } from '../hooks/useTranslation';
import { useTheme } from '../contexts/ThemeContext';
import {
  Select, Button,
} from './ui/macos';

/**
 * Тестовый компонент для проверки работы селектора языка
 */
const LanguageTest = () => {
  const { language, setLanguage, t, availableLanguages } = useTranslation();
  const { isDark, toggleTheme } = useTheme();

  return (
    <div style={{
      padding: 'var(--mac-spacing-5)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      minHeight: '100vh'
    }}>
      <h1>🧪 Тест селектора языка</h1>

      <div style={{ marginBottom: 'var(--mac-spacing-5)' }}>
        <h2>Информация о контексте:</h2>
        <p>Текущий язык: <strong>{language}</strong></p>
        <p>Функция t: <strong>{typeof t}</strong></p>
        <p>availableLanguages: <strong>{availableLanguages ? availableLanguages.length : 'undefined'}</strong></p>
        <p>Тема: <strong>{isDark ? 'темная' : 'светлая'}</strong></p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-5)' }}>
        <h2>Тест переводов:</h2>
        <p>title: {t('title')}</p>
        <p>loginButton: {t('loginButton')}</p>
        <p>address: {t('address')}</p>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-5)' }}>
        <h2>Селектор языка:</h2>
        <Select
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
        </Select>
      </div>

      <div style={{ marginBottom: 'var(--mac-spacing-5)' }}>
        <h2>Кнопка переключения темы:</h2>
        <Button onClick={toggleTheme}>
          Переключить на {isDark ? 'светлую' : 'темную'} тему
        </Button>
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
