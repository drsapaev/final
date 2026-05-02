# EMR V2 Design System

> Профессиональный медицинский интерфейс для 8-10 часовой работы врача

---

## 📐 1. Цветовая токен-система

### Semantic Tokens (используйте эти)

```css
:root {
  /* ======== SURFACES ======== */
  --surface-app: #0f0f23;           /* Фон приложения */
  --surface-sidebar: linear-gradient(180deg, #4c1d95 0%, #2563eb 100%);
  --surface-card: #1a1a2e;          /* Карточка EMR */
  --surface-input: #252540;         /* Поле ввода */
  --surface-input-focus: #2d2d4a;   /* Поле ввода в фокусе */
  --surface-elevated: #1f1f35;      /* Модалки, dropdown */
  
  /* ======== TEXT ======== */
  --text-primary: #f0f1f4;          /* Основной текст - WCAG AAA */
  --text-secondary: #a8adb8;        /* Вторичный текст - WCAG AA */
  --text-muted: #6b7280;            /* Подписи, meta - осторожно! */
  --text-inverse: #1a1a2e;          /* Текст на светлом фоне */
  
  /* ======== ACCENT ======== */
  --accent-primary: #6366f1;        /* Indigo - основной акцент */
  --accent-primary-hover: #818cf8;
  --accent-primary-muted: rgba(99, 102, 241, 0.15);
  
  --accent-success: #22c55e;        /* Зелёный - успех */
  --accent-success-muted: rgba(34, 197, 94, 0.15);
  
  --accent-warning: #f59e0b;        /* Оранжевый - предупреждение */
  --accent-warning-muted: rgba(245, 158, 11, 0.15);
  
  --accent-danger: #ef4444;         /* Красный - ошибка */
  --accent-danger-muted: rgba(239, 68, 68, 0.15);
  
  /* ======== BORDERS ======== */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-default: rgba(255, 255, 255, 0.1);
  --border-focus: var(--accent-primary);
  
  /* ======== SPECIAL: My Experience ======== */
  --my-experience-bg: var(--accent-success-muted);
  --my-experience-border: var(--accent-success);
  --my-experience-text: #a7f3d0;
  
  /* ======== SPECIAL: Templates ======== */
  --templates-bg: var(--surface-input);
  --templates-border: var(--border-default);
  --templates-text: var(--text-secondary);
  
  /* ======== RADII ======== */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-brand: 20px;  /* Только sidebar */
  
  /* ======== SHADOWS ======== */
  --shadow-input-focus: 0 0 0 3px rgba(99, 102, 241, 0.25);
  --shadow-elevated: 0 4px 20px rgba(0, 0, 0, 0.3);
  
  /* ======== SPACING ======== */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  
  /* ======== TYPOGRAPHY ======== */
  --font-size-xs: 11px;
  --font-size-sm: 12px;
  --font-size-base: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 18px;
}
```

### Контраст-матрица (WCAG)

| Токен | На --surface-card | Коэффициент |
|-------|-------------------|-------------|
| --text-primary | ✅ | 12.5:1 (AAA) |
| --text-secondary | ✅ | 6.2:1 (AA) |
| --text-muted | ⚠️ | 3.8:1 (Осторожно) |
| --accent-primary | ✅ | 5.1:1 (AA) |

---

## 🎨 2. TreatmentSection — Идеальный Layout

### Визуальная структура

```
┌─────────────────────────────────────────────────────────────────┐
│ 💊 Лечение                              [ 🕒 History ] [ ⚙️ ]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ План лечения, назначения...                        [🧠]  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Источники рекомендаций                                     ││
│  │  ┌─────────────────┐  ┌─────────────────┐                  ││
│  │  │ 🕒 Мой опыт (3) │  │ 📋 Шаблоны      │                  ││
│  │  │ ● I10: 3 шабл.  │  │ По специальн.   │                  ││
│  │  └─────────────────┘  └─────────────────┘                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Лекарственные назначения                    [ + Добавить ] ││
│  │  ┌───────────┬────────────┬───────────┬──────────────────┐ ││
│  │  │ Препарат  │ Дозировка  │ Частота   │ Длительность     │ ││
│  │  └───────────┴────────────┴───────────┴──────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Кнопки CSS

```css
/* Мой опыт — Primary Subtle (зелёный акцент) */
.btn-my-experience {
  background: var(--my-experience-bg);
  border: 1px solid var(--my-experience-border);
  color: var(--my-experience-text);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-my-experience:hover {
  background: rgba(34, 197, 94, 0.25);
}

.btn-my-experience:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-my-experience:focus-visible {
  outline: 2px solid var(--accent-success);
  outline-offset: 2px;
}

/* Шаблоны — Secondary (нейтральный) */
.btn-templates {
  background: var(--templates-bg);
  border: 1px solid var(--templates-border);
  color: var(--templates-text);
}
```

### Иконки (Lucide React)

```jsx
import { History, LayoutTemplate, Brain, Plus, Edit2, X } from 'lucide-react';

const ICONS = {
  myExperience: History,      // Было: 📜
  templates: LayoutTemplate,  // Было: 📋
  ai: Brain,                  // Было: 🧠
};
```

---

## 📜 3. UX Policy: "No Surprise UI for Doctors"

### Принцип #1: Предсказуемость
> Врач должен знать, что произойдёт **до** клика

### Принцип #2: Никаких модальных окон без необходимости
> Модалки прерывают flow. Используйте inline-панели.

### Принцип #3: Keyboard-first
> 80% действий должны быть доступны с клавиатуры

### Принцип #4: Состояния видимы
> default, hover, focus, active, disabled, loading, error

### Принцип #5: Feedback < 100ms
> Каждое действие должно дать feedback за 100ms

### Принцип #6: Консистентность иконок
> Одна иконка = Одно значение везде

### Принцип #7: No Aggressive Colors
> Яркие цвета только для ошибок и предупреждений

---

## 📋 Чеклист UI-изменений

- [ ] Контраст ≥ WCAG AA
- [ ] Focus state виден
- [ ] Disabled state + tooltip
- [ ] Loading state
- [ ] Error state
- [ ] Keyboard navigation
- [ ] Иконки из Lucide
- [ ] Цвета из токенов

---

*Документ: EMR V2 Design System v1.0*
*Дата: 18.01.2026*
