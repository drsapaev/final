```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import ru from './locales/ru.json';
import uz from './locales/uz.json';
import './index.css';

i18next.use(initReactI18next).init({
  resources: { ru: { translation: ru }, uz: { translation: uz } },
  lng: localStorage.getItem('lang') || 'ru',
  fallbackLng: 'ru',
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
```