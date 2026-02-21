# 📋 Отчет по оптимизации EMR v2 для специализаций

## 🔍 Текущее состояние

### ✅ Что уже работает хорошо

1. **Модульная архитектура**
   - Разделение на независимые секции (ComplaintsSection, ExaminationSection, etc.)
   - Легко расширяемая структура
   - Переиспользуемые компоненты (EMRSection, EMRSmartFieldV2)

2. **Поддержка специализаций**
   - Prop `specialty` передается в секции
   - ExaminationMatrix поддерживает `cardiology` и `general`
   - TreatmentTemplatesPanel фильтрует по specialty

3. **AI интеграция**
   - Умные подсказки на основе жалоб
   - ICD-10 автодополнение
   - Анализ жалоб с учетом специализации

4. **История и шаблоны**
   - "Мой опыт" - персональные шаблоны врача
   - История фраз по специализации
   - Шаблоны лечения по ICD-10

### ⚠️ Что требует оптимизации

1. **Отсутствие специализированных секций**
   - Нет CardiologySection для ЭКГ/ЭхоКГ
   - Нет DermatologySection для фото-архива
   - Нет DentistrySection для зубной карты

2. **Неполная интеграция специализированных данных**
   - EMRContainerV2 не использует `specialty_data` из backend
   - Старый EMRSystem имеет `dentalData`, но v2 не поддерживает

3. **ExaminationMatrix ограничен**
   - Только `general` и `cardiology`
   - Нет матриц для `dermatology` и `dentist`

4. **Дублирование логики**
   - Старый EMRSystem и новый EMRContainerV2 существуют параллельно
   - Специализированные панели используют старый EMRSystem

---

## 🎯 Рекомендации по оптимизации

### 1. Кардиология (Cardiology)

#### Текущее состояние
- ✅ ECGViewer компонент существует
- ✅ ExaminationMatrix поддерживает cardiology
- ❌ EMRContainerV2 не интегрирует ЭКГ данные

#### Оптимизации

**1.1 Создать CardiologySection.jsx**
```jsx
// Специализированная секция для кардиологии
- Интеграция ECGViewer
- Поля для ЭхоКГ результатов
- Кардиологические маркеры (тропонин, CRP, холестерин)
- Калькуляторы рисков (SCORE, TIMI)
- Автоматическое заполнение на основе ЭКГ анализа
```

**1.2 Расширить ExaminationMatrix для кардиологии**
```javascript
cardiology: {
    'Осмотр': ['Окраска кожи', 'Отеки', 'Вены шеи', 'Пульсация'],
    'Сердце': ['Верхушечный толчок', 'Границы', 'Тоны', 'Ритм', 'Шумы', 'Галоп'],
    'Легкие': ['Дыхание', 'Хрипы', 'Застойные явления', 'Плевральный выпот'],
    'Пульс': ['Наполнение', 'Напряжение', 'Дефицит', 'Аритмия'],
    'АД': ['Систолическое', 'Диастолическое', 'Пульсовое давление']
}
```

**1.3 Интеграция с EMRContainerV2**
```jsx
// В EMRContainerV2.jsx добавить условный рендеринг
{data.specialty === 'cardiology' && (
    <CardiologySection
        ecgData={data.specialty_data?.ecg}
        echoData={data.specialty_data?.echo}
        labResults={data.specialty_data?.cardio_labs}
        onChange={(field, value) => handleSpecialtyDataChange(field, value)}
        disabled={isSigned}
    />
)}
```

**1.4 Оптимизация AI для кардиологии**
- Специализированные промпты для анализа ЭКГ
- Интерпретация кардиологических маркеров
- Рекомендации по дополнительным исследованиям

---

### 2. Дерматология (Dermatology)

#### Текущее состояние
- ✅ EMRSystem имеет поддержку изображений
- ✅ AI анализ кожи (analyzeSkinLesion)
- ❌ Нет специализированной секции в v2

#### Оптимизации

**2.1 Создать DermatologySection.jsx**
```jsx
// Специализированная секция для дерматологии
- Фото-галерея до/после
- Тип кожи (нормальная, сухая, жирная, комбинированная)
- Состояние (акне, розацеа, экзема, псориаз)
- Локализация поражений на схеме тела
- AI анализ изображений кожи
- Шаблоны косметологических процедур
```

**2.2 Расширить ExaminationMatrix для дерматологии**
```javascript
dermatology: {
    'Тип кожи': ['Нормальная', 'Сухая', 'Жирная', 'Комбинированная', 'Чувствительная'],
    'Состояние': ['Акне', 'Розацеа', 'Экзема', 'Псориаз', 'Пигментация', 'Морщины'],
    'Локализация': ['Лицо', 'Шея', 'Декольте', 'Руки', 'Тело'],
    'Характеристики': ['Размер', 'Цвет', 'Текстура', 'Границы', 'Симметрия']
}
```

**2.3 Интеграция фото-архива**
```jsx
<DermatologySection
    photos={data.specialty_data?.photos || []}
    skinType={data.specialty_data?.skin_type}
    conditions={data.specialty_data?.conditions || []}
    onPhotoUpload={(file) => handlePhotoUpload(file)}
    onPhotoAnalysis={(photoId) => handlePhotoAnalysis(photoId)}
    disabled={isSigned}
/>
```

**2.4 Оптимизация AI для дерматологии**
- Анализ изображений с помощью MCP
- Классификация поражений
- Рекомендации по лечению на основе фото

---

### 3. Стоматология (Dentistry)

#### Текущее состояние
- ✅ TeethChart компонент существует
- ✅ EMRSystem имеет dentalData структуру
- ❌ EMRContainerV2 не поддерживает стоматологические данные

#### Оптимизации

**3.1 Создать DentistrySection.jsx**
```jsx
// Специализированная секция для стоматологии
- Интерактивная зубная карта (TeethChart)
- Индексы гигиены (OHIS, PLI, CPI, Bleeding)
- Пародонтальные карманы
- Измерения прикуса (overjet, overbite, midline)
- Рентгенограммы (панорамный, прицельные, КЛКТ)
- План лечения по зубам
```

**3.2 Расширить ExaminationMatrix для стоматологии**
```javascript
dentist: {
    'Общий осмотр': ['Состояние слизистой', 'Язык', 'Губы', 'Щеки'],
    'Пародонт': ['Кровоточивость', 'Карманы', 'Подвижность', 'Рецессия'],
    'Прикус': ['Ортогнатический', 'Прогнатия', 'Прогения', 'Открытый', 'Глубокий'],
    'Гигиена': ['Хорошая', 'Удовлетворительная', 'Плохая', 'Очень плохая']
}
```

**3.3 Интеграция зубной карты**
```jsx
<DentistrySection
    toothStatus={data.specialty_data?.tooth_status || {}}
    hygieneIndices={data.specialty_data?.hygiene_indices || {}}
    periodontalPockets={data.specialty_data?.periodontal_pockets || {}}
    measurements={data.specialty_data?.measurements || {}}
    radiographs={data.specialty_data?.radiographs || {}}
    onToothChange={(toothNumber, status) => handleToothChange(toothNumber, status)}
    disabled={isSigned}
/>
```

**3.4 Оптимизация для стоматологии**
- Автоматический расчет индексов
- Валидация данных зубной карты
- Интеграция с системой протезирования

---

## 🔧 Технические улучшения

### 1. Унификация работы с specialty_data

**Проблема:** EMRContainerV2 не использует `specialty_data` из backend

**Решение:**
```jsx
// Добавить в EMRContainerV2.jsx
const handleSpecialtyDataChange = useCallback((field, value) => {
    setField('specialty_data', {
        ...(data.specialty_data || {}),
        [field]: value
    });
}, [data.specialty_data, setField]);
```

### 2. Создать хук useSpecialtyData

```jsx
// hooks/useSpecialtyData.js
export function useSpecialtyData(specialty, specialtyData, onChange) {
    const handleChange = useCallback((field, value) => {
        onChange('specialty_data', {
            ...specialtyData,
            [field]: value
        });
    }, [specialtyData, onChange]);

    return {
        data: specialtyData || {},
        setField: handleChange,
        // Специализированные геттеры
        getCardiologyData: () => specialty === 'cardiology' ? specialtyData : null,
        getDermatologyData: () => specialty === 'dermatology' ? specialtyData : null,
        getDentistryData: () => specialty === 'dentist' ? specialtyData : null,
    };
}
```

### 3. Расширить ExaminationMatrix

```javascript
// components/emr/ExaminationMatrix.jsx
const MATRICES = {
    // ... существующие
    dermatology: { /* ... */ },
    dentist: { /* ... */ },
    // Добавить поддержку динамической загрузки матриц
};
```

### 4. Оптимизация производительности

**Мемоизация специализированных секций:**
```jsx
const CardiologySectionMemo = React.memo(CardiologySection);
const DermatologySectionMemo = React.memo(DermatologySection);
const DentistrySectionMemo = React.memo(DentistrySection);
```

**Ленивая загрузка:**
```jsx
const CardiologySection = React.lazy(() => import('./sections/CardiologySection'));
const DermatologySection = React.lazy(() => import('./sections/DermatologySection'));
const DentistrySection = React.lazy(() => import('./sections/DentistrySection'));
```

---

## 📊 План миграции

### Этап 1: Подготовка (1-2 дня)
- [ ] Создать структуру `sections/specialty/`
- [ ] Добавить поддержку `specialty_data` в useEMR hook
- [ ] Расширить ExaminationMatrix для всех специализаций

### Этап 2: Кардиология (2-3 дня)
- [ ] Создать CardiologySection.jsx
- [ ] Интегрировать ECGViewer
- [ ] Добавить поля для ЭхоКГ и маркеров
- [ ] Протестировать в CardiologistPanelUnified

### Этап 3: Дерматология (2-3 дня)
- [ ] Создать DermatologySection.jsx
- [ ] Интегрировать фото-загрузку и анализ
- [ ] Добавить шаблоны процедур
- [ ] Протестировать в DermatologistPanelUnified

### Этап 4: Стоматология (2-3 дня)
- [ ] Создать DentistrySection.jsx
- [ ] Интегрировать TeethChart
- [ ] Добавить индексы и измерения
- [ ] Протестировать в DentistPanelUnified

### Этап 5: Интеграция (1-2 дня)
- [ ] Обновить EMRContainerV2 для условного рендеринга
- [ ] Мигрировать специализированные панели на EMRContainerV2
- [ ] Удалить старый EMRSystem (после полной миграции)

---

## 🎨 UX улучшения

### 1. Адаптивный интерфейс
- Секции сворачиваются по умолчанию, если не заполнены
- Быстрый доступ к специализированным инструментам
- Контекстные подсказки для каждой специализации

### 2. Визуальная обратная связь
- Индикаторы заполненности специализированных данных
- Предупреждения о незаполненных критических полях
- Прогресс-бар заполнения ЭМК

### 3. Горячие клавиши
- `Ctrl+E` - открыть ExaminationMatrix
- `Ctrl+T` - открыть шаблоны лечения
- `Ctrl+H` - открыть "Мой опыт"
- `Ctrl+P` - загрузить фото (дерматология)
- `Ctrl+C` - открыть зубную карту (стоматология)

---

## 📝 Примеры использования

### Кардиология
```jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    specialty="cardiology"
/>
// Автоматически рендерит CardiologySection с ЭКГ интеграцией
```

### Дерматология
```jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    specialty="dermatology"
/>
// Автоматически рендерит DermatologySection с фото-архивом
```

### Стоматология
```jsx
<EMRContainerV2
    visitId={visitId}
    patientId={patientId}
    specialty="dentist"
/>
// Автоматически рендерит DentistrySection с зубной картой
```

---

## ✅ Критерии успеха

1. **Функциональность**
   - Все специализированные данные сохраняются в `specialty_data`
   - Интеграция с существующими компонентами (ECGViewer, TeethChart)
   - Поддержка всех трех специализаций

2. **Производительность**
   - Ленивая загрузка специализированных секций
   - Мемоизация тяжелых компонентов
   - Оптимизация рендеринга

3. **UX**
   - Интуитивный интерфейс для каждой специализации
   - Быстрый доступ к специализированным инструментам
   - Контекстные подсказки и валидация

4. **Поддерживаемость**
   - Модульная структура кода
   - Переиспользуемые компоненты
   - Четкая документация

---

## 🔗 Связанные файлы

- `frontend/src/components/emr-v2/EMRContainerV2.jsx` - Основной контейнер
- `frontend/src/components/emr-v2/sections/` - Базовые секции
- `frontend/src/components/cardiology/ECGViewer.jsx` - Компонент ЭКГ
- `frontend/src/components/dental/TeethChart.jsx` - Зубная карта
- `frontend/src/components/emr/ExaminationMatrix.jsx` - Матрица осмотра
- `backend/app/schemas/emr_v2.py` - Схема данных (specialty_data)

---

**Дата создания:** 2026-02-06  
**Статус:** Требует реализации  
**Приоритет:** Высокий
