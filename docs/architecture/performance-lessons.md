# Performance Lessons From Old Panels (EMR v2)

## Итог

Эти оптимизации проверены в бою, но их нельзя переносить "как есть" в новые компоненты. Правильный путь — нормализовать их в инфраструктуру (общие хуки, сервисы, policy) и использовать как единый источник правды.

См. решение: `docs/architecture/ADR-0001-centralized-caching.md`.

## Что централизуем

- Кэширование данных через единый сервис (TTL, теги, инвалидации).
- Дебаунс через общую policy и единые значения задержек.
- Инвалидацию состояния при смене `visitId` через единый хук жизненного цикла визита.

## Что запрещаем

- Локальные `localStorage`/TTL в компонентах.
- Разные debounce-задержки без policy.
- Частичную очистку состояния при смене визита.

## Что допускаем

- `useMemo`/`useCallback` только для O(n) вычислений и derived state.
- `Promise.all`/`Promise.allSettled` для параллельной загрузки с fallback.

---

# 🔍 Оптимизации из старых панелей специалистов

## 📋 Обзор

В старых панелях специалистов (CardiologistPanelUnified, DermatologistPanelUnified, DentistPanelUnified) были реализованы различные оптимизации производительности, которые можно применить к новой версии EMR v2.

---

## 🚀 1. Кэширование данных

### 1.1 Кэширование анализа жалоб (EMRSystem.jsx)

**Местоположение:** `frontend/src/components/medical/EMRSystem.jsx:160-201`

**Оптимизация:**
```javascript
const [complaintsAnalysisCache, setComplaintsAnalysisCache] = useState({});

// Проверяем кэш перед запросом
const cacheKey = complaints.trim().toLowerCase();
if (complaintsAnalysisCache[cacheKey]) {
    const cachedResult = complaintsAnalysisCache[cacheKey];
    // Используем кэшированные данные
    return;
}

// Сохраняем результат в кэш
setComplaintsAnalysisCache(prev => ({
    ...prev,
    [cacheKey]: result
}));
```

**Применение для EMR v2:**
- Добавить кэширование AI-запросов в `EMRContainerV2.jsx`
- Кэшировать результаты `handleRequestAI` по ключу (fieldName + complaints hash)
- TTL: 5 минут для AI-результатов

### 1.2 API кэширование (apiCache.js)

**Местоположение:** `frontend/src/utils/apiCache.js`

**Особенности:**
- TTL (Time To Live) для записей
- Автоматическая очистка истекших записей
- Инвалидация по паттерну
- Ограничение размера кэша

**Применение:**
```javascript
import { apiCache } from '../../utils/apiCache';

// В useEMR hook или EMRContainerV2
const cacheKey = `emr_${visitId}_${version}`;
const cached = apiCache.get(cacheKey);
if (cached) {
    return cached.data;
}
```

### 1.3 useCachedData hook

**Местоположение:** `frontend/src/hooks/useApi.js:304-350`

**Особенности:**
- Кэширование в localStorage
- Настраиваемый TTL
- Fallback значения

**Использование:**
```javascript
const { data, loading, clearCache } = useCachedData(
    `patient_${patientId}`,
    () => fetchPatientData(patientId),
    { ttl: 5 * 60 * 1000 } // 5 минут
);
```

---

## ⏱️ 2. Дебаунсинг (Debouncing)

### 2.1 Дебаунсинг анализа жалоб

**Местоположение:** `EMRSystem.jsx:161`

**Оптимизация:**
```javascript
const debouncedAnalyzeComplaints = useDebounce(
    useCallback(async (complaints) => {
        // Анализ жалоб
    }, [dependencies]),
    800 // 800ms задержка
);
```

**Применение для EMR v2:**
- Дебаунсинг `handleRequestAI` с задержкой 800ms
- Предотвращение множественных запросов при быстром вводе

### 2.2 Дебаунсинг поиска

**Местоположение:** `CashierPanel.jsx:50-63`, `RegistrarPanel.jsx:1393-1400`

**Особенности:**
- Кастомный хук `useDebounce`
- Задержка 500ms для поиска
- Задержка для ввода даты

**Применение:**
```javascript
const debouncedSearch = useDebounce(searchQuery, 500);
useEffect(() => {
    if (debouncedSearch) {
        performSearch(debouncedSearch);
    }
}, [debouncedSearch]);
```

### 2.3 Дебаунсинг в useDoctorPhrases

**Местоположение:** `frontend/src/hooks/useDoctorPhrases.js:177-203`

**Особенности:**
- Дебаунсинг запросов истории врача
- Проверка готовности перед запросом
- Минимальная длина запроса
- Предотвращение дублирующих запросов

**Код:**
```javascript
const debouncedFetch = useCallback((text, cursor) => {
    if (!readiness.ready) return;
    if (text.length < minQueryLength) {
        setSuggestions([]);
        return;
    }
    if (text === lastQueryRef.current) return;
    
    debounceRef.current = setTimeout(() => {
        fetchSuggestions(text, cursor);
    }, debounceMs);
}, [dependencies]);
```

---

## 🧠 3. Мемоизация (useMemo)

### 3.1 Мемоизация справочников цен

**Местоположение:** `DermatologistPanelUnified.jsx:140-157`

**Оптимизация:**
```javascript
const dermaPriceMap = useMemo(() => ({
    derma_consultation: 50000,
    derma_biopsy: 150000,
    cosm_cleaning: 80000,
    cosm_botox: 300000,
    cosm_laser: 250000,
}), []); // Пустой массив зависимостей - создается один раз

const servicesSubtotal = useMemo(() => {
    return selectedServices.reduce((sum, id) => sum + (dermaPriceMap[id] || 0), 0);
}, [selectedServices, dermaPriceMap]);

const totalCost = useMemo(() => {
    return servicesSubtotal + doctorPriceNum;
}, [servicesSubtotal, doctorPriceNum]);
```

**Применение для EMR v2:**
- Мемоизировать справочники ICD-10
- Мемоизировать вычисляемые значения (completeness, validation)
- Мемоизировать отфильтрованные списки

### 3.2 Мемоизация фильтрации

**Местоположение:** `RegistrarPanel.jsx:2537`, `DentistPanelUnified.jsx:771`

**Особенности:**
- Фильтрация списков через useMemo
- Зависимости только от исходных данных и фильтров
- Предотвращение лишних пересчетов

**Пример:**
```javascript
const filteredAppointments = useMemo(() => {
    return appointments.filter(appointment => {
        // Логика фильтрации
    });
}, [appointments, searchQuery, statusFilter]);
```

### 3.3 Мемоизация статистики

**Местоположение:** `RegistrarPanel.jsx:2107`, `DentistPanelUnified.jsx:771`

**Особенности:**
- Вычисление статистики только при изменении данных
- Агрегация данных через useMemo

---

## 🔄 4. useCallback оптимизации

### 4.1 Мемоизация обработчиков событий

**Местоположение:** Все панели используют `useCallback` для функций

**Примеры:**
- `loadPatientData` - загрузка данных пациента
- `handleEditPatient` - редактирование пациента
- `fetchPatientData` - получение данных пациента
- `transformPatientData` - преобразование данных
- `loadAppointments` - загрузка записей

**Применение для EMR v2:**
```javascript
const handleFieldChange = useCallback((field) => (value) => {
    setField(field, value);
}, [setField]);

const handleRequestAI = useCallback(async (fieldName) => {
    // AI запрос
}, [dependencies]);
```

### 4.2 Оптимизация загрузки данных

**Местоположение:** `CardiologistPanelUnified.jsx:106-134`

**Особенности:**
- Проверка наличия данных перед загрузкой
- Условная загрузка только нужных данных
- Обработка ошибок

**Код:**
```javascript
const loadPatientData = useCallback(async () => {
    if (!selectedPatient?.patient?.id && !selectedPatient?.patient_id) return;
    
    try {
        // Параллельная загрузка ЭКГ и анализов
        const [ecgResponse, bloodResponse] = await Promise.all([
            fetch(`${API_BASE}/api/v1/cardio/ecg?patient_id=${patientId}`),
            fetch(`${API_BASE}/api/v1/cardio/blood-tests?patient_id=${patientId}`)
        ]);
        // Обработка результатов
    } catch (error) {
        // Обработка ошибок
    }
}, [selectedPatient]);
```

---

## 🧹 5. Очистка состояния

### 5.1 Очистка при смене пациента

**Местоположение:** `CardiologistPanelUnified.jsx:136-150`

**Оптимизация:**
```javascript
const prevSelectedPatientRef = useRef(null);

useEffect(() => {
    if (selectedPatient) {
        const currentPatientId = selectedPatient.patient_id || selectedPatient.id;
        const previousPatientId = prevSelectedPatientRef.current;

        // Если это новый пациент
        if (previousPatientId !== null && previousPatientId !== currentPatientId) {
            // Очищаем EMR и visitData
            setEmr(null);
            setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
        }

        prevSelectedPatientRef.current = currentPatientId;
    }
}, [selectedPatient]);
```

**Применение для EMR v2:**
- Очистка AI-кэша при смене visitId
- Сброс состояния специализированных секций
- Очистка истории при смене пациента

### 5.2 Отмена запросов (AbortController)

**Местоположение:** `useOptimizedData.js:21-44`, `useDoctorPhrases.js:217-226`

**Особенности:**
- Использование AbortController для отмены запросов
- Очистка при размонтировании компонента
- Предотвращение утечек памяти

**Код:**
```javascript
const abortControllerRef = useRef(null);

useEffect(() => {
    return () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
    };
}, []);
```

---

## 📊 6. Оптимизация рендеринга

### 6.1 Условный рендеринг

**Местоположение:** Все панели используют условный рендеринг

**Особенности:**
- Рендеринг компонентов только при необходимости
- Ленивая загрузка тяжелых компонентов
- Скрытие неиспользуемых секций

**Пример:**
```javascript
{data.specialty === 'cardiology' && (
    <CardiologySection {...props} />
)}
```

### 6.2 React.memo для компонентов

**Местоположение:** `RegistrarPanel.jsx:1` (импорт memo)

**Применение:**
```javascript
const ExpensiveComponent = React.memo(({ data }) => {
    // Компонент
}, (prevProps, nextProps) => {
    // Кастомная функция сравнения
    return prevProps.data.id === nextProps.data.id;
});
```

---

## 🔗 7. Параллельная загрузка данных

### 7.1 Promise.all для параллельных запросов

**Местоположение:** `CardiologistPanelUnified.jsx:115-130`

**Оптимизация:**
```javascript
// Вместо последовательных запросов
const ecgData = await fetchECG(patientId);
const bloodData = await fetchBloodTests(patientId);

// Параллельные запросы
const [ecgResponse, bloodResponse] = await Promise.all([
    fetch(`${API_BASE}/api/v1/cardio/ecg?patient_id=${patientId}`),
    fetch(`${API_BASE}/api/v1/cardio/blood-tests?patient_id=${patientId}`)
]);
```

**Применение для EMR v2:**
- Параллельная загрузка EMR и specialty_data
- Параллельная загрузка истории и шаблонов
- Параллельная загрузка AI-подсказок для разных полей

---

## 🎯 8. Оптимизация URL синхронизации

### 8.1 Синхронизация вкладок с URL

**Местоположение:** Все панели используют `useLocation` и `useNavigate`

**Особенности:**
- Сохранение состояния в URL параметрах
- Восстановление состояния при загрузке
- Обновление URL при изменении вкладок

**Код:**
```javascript
const getActiveTabFromURL = useCallback(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('patientId')) {
        return 'visit';
    }
    return params.get('tab') || 'appointments';
}, [location.search]);

useEffect(() => {
    const urlTab = getActiveTabFromURL();
    if (urlTab !== activeTab) {
        setActiveTab(urlTab);
    }
}, [activeTab, getActiveTabFromURL]);
```

---

## 📝 9. Рекомендации для EMR v2

### 9.1 Применить кэширование

```javascript
// В EMRContainerV2.jsx
const [aiCache, setAiCache] = useState(new Map());

const handleRequestAI = useCallback(async (fieldName) => {
    const cacheKey = `${fieldName}_${hashComplaints(data.complaints)}`;
    const cached = aiCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
        setAiSuggestions(prev => ({ ...prev, [fieldName]: cached.suggestions }));
        return;
    }
    
    // Запрос AI...
    // Сохранение в кэш
}, [data.complaints, aiCache]);
```

### 9.2 Применить дебаунсинг

```javascript
// В EMRContainerV2.jsx
const debouncedRequestAI = useDebounce(handleRequestAI, 800);

// В ExaminationSection.jsx
const debouncedOnChange = useDebounce(onChange, 300);
```

### 9.3 Мемоизировать вычисления

```javascript
// В EMRContainerV2.jsx
const completeness = useMemo(() => {
    return calculateCompleteness(data);
}, [data]);

const validationErrors = useMemo(() => {
    return validateEMR(data);
}, [data]);
```

### 9.4 Оптимизировать загрузку

```javascript
// Параллельная загрузка
useEffect(() => {
    Promise.all([
        loadEMR(),
        loadSpecialtyData(),
        loadHistory(),
        loadTemplates()
    ]).then(([emr, specialty, history, templates]) => {
        // Обновление состояния
    });
}, [visitId]);
```

### 9.5 Очистка при смене visitId

```javascript
const prevVisitIdRef = useRef(null);

useEffect(() => {
    if (prevVisitIdRef.current !== null && prevVisitIdRef.current !== visitId) {
        // Очистка кэша
        setAiCache(new Map());
        setAiSuggestions({});
        setExperimentalGhostMode(false);
    }
    prevVisitIdRef.current = visitId;
}, [visitId]);
```

---

## ✅ Чеклист применения оптимизаций

- [ ] Добавить кэширование AI-запросов в `EMRContainerV2`
- [ ] Добавить дебаунсинг для `handleRequestAI` (800ms)
- [ ] Мемоизировать вычисления completeness и validation
- [ ] Мемоизировать отфильтрованные списки шаблонов
- [ ] Оптимизировать загрузку данных через Promise.all
- [ ] Добавить очистку кэша при смене visitId
- [ ] Использовать AbortController для отмены запросов
- [ ] Применить React.memo для тяжелых компонентов
- [ ] Оптимизировать условный рендеринг специализированных секций
- [ ] Добавить lazy loading для специализированных секций

---

## 📚 Связанные файлы

- `frontend/src/utils/debounce.js` - Утилита дебаунсинга
- `frontend/src/utils/apiCache.js` - API кэширование
- `frontend/src/hooks/useOptimizedData.js` - Хук оптимизированной загрузки
- `frontend/src/hooks/useCachedData.js` - Хук кэширования данных
- `frontend/src/hooks/useDoctorPhrases.js` - Оптимизированный хук истории врача

---

**Дата создания:** 2026-02-06  
**Статус:** Готово к применению
