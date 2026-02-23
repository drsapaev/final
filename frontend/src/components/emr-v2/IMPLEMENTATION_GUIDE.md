# 🚀 Руководство по использованию EMR v2 с специализациями

## ✅ Что было сделано

### 1. Созданы специализированные секции
- ✅ `CardiologySection.jsx` - для кардиологии (ЭКГ, ЭхоКГ, анализы, риски)
- ✅ `DermatologySection.jsx` - для дерматологии (фото, тип кожи, AI анализ)
- ✅ `DentistrySection.jsx` - для стоматологии (зубная карта, индексы, прикус)

### 2. Интеграция в EMRContainerV2
- ✅ Условный рендеринг специализированных секций на основе `data.specialty`
- ✅ Поддержка `specialty_data` из backend
- ✅ Автоматическое отображение нужной секции

### 3. Расширение ExaminationMatrix
- ✅ Добавлены матрицы для `dermatology` и `dentist`
- ✅ Расширена матрица для `cardiology`
- ✅ Добавлены текстовые шаблоны для всех специализаций

## 📖 Использование

### Базовое использование

```jsx
import { EMRContainerV2 } from '../components/emr-v2';

<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    // specialty определяется автоматически из data.specialty
/>
```

### Специализированные панели

#### Кардиология
```jsx
// В CardiologistPanelUnified.jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    // specialty='cardiology' из appointment.specialty
/>
```

#### Дерматология
```jsx
// В DermatologistPanelUnified.jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    // specialty='dermatology' из appointment.specialty
/>
```

#### Стоматология
```jsx
// В DentistPanelUnified.jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    // specialty='dentist' или 'dentistry' из appointment.specialty
/>
```

## 🔧 Структура данных

### Backend (specialty_data)

```json
{
  "specialty_data": {
    // Для кардиологии
    "ecg": {
      "files": [...],
      "interpretation": "...",
      "parameters": {...}
    },
    "echo": {
      "ef": 60,
      "chambers": {...}
    },
    "cardio_labs": {
      "troponin_i": "0.02",
      "crp": "2.5",
      "cholesterol_total": "5.2"
    },
    
    // Для дерматологии
    "photos": [
      {
        "id": 1,
        "url": "...",
        "category": "examination",
        "analysis": {...}
      }
    ],
    "skin_type": "combination",
    "conditions": ["Акне", "Пигментация"],
    "localization": {
      "description": "..."
    },
    
    // Для стоматологии
    "tooth_status": {
      "11": {"status": "caries", ...},
      "21": {"status": "filled", ...}
    },
    "hygiene_indices": {
      "ohis": "2.5",
      "pli": "1.2",
      "cpi": "2",
      "bleeding": "15"
    },
    "measurements": {
      "overjet": "3",
      "overbite": "2",
      "midline": "0",
      "crossbite": false,
      "openBite": false
    },
    "radiographs": {
      "panoramic": "...",
      "cbct": "..."
    }
  }
}
```

## 🎨 Особенности каждой специализации

### Кардиология
- **ЭКГ**: Интеграция с ECGViewer для загрузки и анализа ЭКГ файлов
- **ЭхоКГ**: Форма для ввода результатов эхокардиографии
- **Анализы**: Поля для кардиологических маркеров (тропонин, CRP, холестерин)
- **Риски**: Калькулятор SCORE2 (TODO: реализовать)

### Дерматология
- **Фото-архив**: Загрузка и управление фотографиями до/после
- **Тип кожи**: Выбор типа кожи из списка
- **Состояния**: Чекбоксы для различных состояний кожи
- **AI анализ**: Автоматический анализ загруженных фото

### Стоматология
- **Зубная карта**: Интерактивная карта зубов (TeethChart)
- **Индексы гигиены**: OHIS, PLI, CPI, Bleeding Index
- **Пародонт**: Измерение пародонтальных карманов
- **Прикус**: Измерения overjet, overbite, midline
- **Рентген**: Поля для панорамных снимков и КЛКТ

## 🔄 Миграция со старого EMRSystem

### Шаг 1: Заменить импорт

**Было:**
```jsx
import EMRSystem from '../components/medical/EMRSystem';
```

**Стало:**
```jsx
import { EMRContainerV2 } from '../components/emr-v2';
```

### Шаг 2: Обновить использование

**Было:**
```jsx
<EMRSystem
    appointment={appointment}
    emr={emr}
    onSave={saveEMR}
/>
```

**Стало:**
```jsx
<EMRContainerV2
    visitId={appointment.id}
    patientId={appointment.patient_id}
    // onSave встроен в EMRContainerV2 через useEMR hook
/>
```

### Шаг 3: Проверить specialty

Убедитесь, что `appointment.specialty` правильно установлен:
- `'cardiology'` для кардиолога
- `'dermatology'` для дерматолога
- `'dentist'` или `'dentistry'` для стоматолога

## ⚠️ Важные замечания

1. **Совместимость данных**: Старый EMRSystem использует `dentalData`, новый использует `specialty_data.tooth_status`. При миграции нужно преобразовать данные.

2. **Ленивая загрузка**: Специализированные секции загружаются только когда `specialty` соответствует. Это оптимизирует производительность.

3. **Валидация**: Каждая секция имеет свою валидацию. Убедитесь, что backend правильно обрабатывает `specialty_data`.

4. **Тестирование**: После миграции протестируйте:
   - Сохранение специализированных данных
   - Загрузку существующих ЭМК
   - Отображение в режиме только чтения (подписанные ЭМК)

## 🐛 Известные ограничения

1. **Калькулятор рисков**: SCORE2 калькулятор пока не реализован (TODO)
2. **Пародонтальные карманы**: Визуализация карманов в DentistrySection требует доработки
3. **Рентген**: Загрузка файлов рентгенограмм требует интеграции с файловой системой

## 📚 Дополнительные ресурсы

- [EMR_V2_OPTIMIZATION_REPORT.md](./EMR_V2_OPTIMIZATION_REPORT.md) - Полный отчет по оптимизации
- [Backend EMR v2 Schema](../../../backend/app/schemas/emr_v2.py) - Схема данных
- [ExaminationMatrix](../../emr/ExaminationMatrix.jsx) - Матрица быстрого ввода

---

**Дата создания:** 2026-02-06  
**Версия:** 1.0.0
