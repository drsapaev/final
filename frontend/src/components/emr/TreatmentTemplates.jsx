/**
 * TreatmentTemplates - Шаблоны назначений для быстрого ввода
 * 
 * Категории:
 * - Медикаменты (антигипертензивные, статины и т.д.)
 * - Обследования (ЭКГ, ЭхоКГ, лаборатория)
 * - Контрольный визит
 * 
 * Используется в секции "План" в SingleSheetEMR
 */

import React, { useState, useCallback, useMemo } from 'react';
import './TreatmentTemplates.css';

// ============================================
// ШАБЛОНЫ ПО СПЕЦИАЛЬНОСТЯМ
// ============================================
const TEMPLATES = {
    cardiology: {
        medications: [
            { id: 'med-1', name: 'Антигипертензивная терапия', template: 'Лизиноприл 10 мг 1 р/д утром' },
            { id: 'med-2', name: 'Бета-блокатор', template: 'Бисопролол 5 мг 1 р/д утром' },
            { id: 'med-3', name: 'Статин', template: 'Аторвастатин 20 мг вечером' },
            { id: 'med-4', name: 'Антиагрегант', template: 'Аспирин 100 мг после еды' },
            { id: 'med-5', name: 'Диуретик', template: 'Индапамид 2.5 мг утром' },
            { id: 'med-6', name: 'АРА II', template: 'Лозартан 50 мг 1 р/д' },
        ],
        examinations: [
            { id: 'exam-1', name: 'ЭКГ', template: 'ЭКГ в 12 отведениях' },
            { id: 'exam-2', name: 'ЭхоКГ', template: 'ЭхоКГ с допплерографией' },
            { id: 'exam-3', name: 'Холтер ЭКГ', template: 'Суточное мониторирование ЭКГ' },
            { id: 'exam-4', name: 'СМАД', template: 'Суточное мониторирование АД' },
            { id: 'exam-5', name: 'Коронарография', template: 'КАГ по показаниям' },
        ],
        labs: [
            { id: 'lab-1', name: 'Липидный профиль', template: 'Холестерин, ЛПНП, ЛПВП, триглицериды' },
            { id: 'lab-2', name: 'Кардиомаркеры', template: 'Тропонин I, КФК-МВ, миоглобин' },
            { id: 'lab-3', name: 'Коагулограмма', template: 'ПТИ, МНО, фибриноген' },
            { id: 'lab-4', name: 'Базовая биохимия', template: 'Глюкоза, креатинин, мочевина, K, Na' },
            { id: 'lab-5', name: 'BNP', template: 'NT-proBNP (маркер СН)' },
        ],
        followup: [
            { id: 'follow-1', name: 'Через 2 недели', template: 'Контроль через 2 недели с результатами обследований' },
            { id: 'follow-2', name: 'Через месяц', template: 'Контроль АД через 1 месяц' },
            { id: 'follow-3', name: 'Через 3 месяца', template: 'Плановый осмотр через 3 месяца' },
        ]
    },

    general: {
        medications: [
            { id: 'med-g1', name: 'НПВС', template: 'Ибупрофен 400 мг при болях' },
            { id: 'med-g2', name: 'Антибиотик', template: 'Амоксициллин 500 мг 3 р/д 7 дней' },
            { id: 'med-g3', name: 'Антигистаминный', template: 'Цетиризин 10 мг вечером' },
            { id: 'med-g4', name: 'ИПП', template: 'Омепразол 20 мг утром натощак' },
            { id: 'med-g5', name: 'Витамин D', template: 'Колекальциферол 2000 МЕ/день' },
        ],
        examinations: [
            { id: 'exam-g1', name: 'ОАК', template: 'Общий анализ крови' },
            { id: 'exam-g2', name: 'ОАМ', template: 'Общий анализ мочи' },
            { id: 'exam-g3', name: 'Биохимия', template: 'Биохимический анализ крови' },
            { id: 'exam-g4', name: 'ФЛГ', template: 'Флюорография грудной клетки' },
            { id: 'exam-g5', name: 'УЗИ ОБП', template: 'УЗИ органов брюшной полости' },
        ],
        labs: [
            { id: 'lab-g1', name: 'Глюкоза', template: 'Глюкоза крови натощак' },
            { id: 'lab-g2', name: 'HbA1c', template: 'Гликированный гемоглобин' },
            { id: 'lab-g3', name: 'Щитовидная железа', template: 'ТТГ, Т4 свободный' },
            { id: 'lab-g4', name: 'Ферритин', template: 'Ферритин, сывороточное железо' },
        ],
        followup: [
            { id: 'follow-g1', name: 'Через неделю', template: 'Контроль через 7 дней' },
            { id: 'follow-g2', name: 'По результатам', template: 'Повторный прием по результатам обследования' },
        ]
    },

    neurology: {
        medications: [
            { id: 'med-n1', name: 'Триптан', template: 'Суматриптан 50 мг при приступе' },
            { id: 'med-n2', name: 'Противосудорожное', template: 'Топирамат 25 мг вечером' },
            { id: 'med-n3', name: 'Ноотроп', template: 'Пирацетам 800 мг 2 р/д' },
            { id: 'med-n4', name: 'Миорелаксант', template: 'Толперизон 150 мг 2 р/д' },
        ],
        examinations: [
            { id: 'exam-n1', name: 'МРТ головы', template: 'МРТ головного мозга' },
            { id: 'exam-n2', name: 'ЭЭГ', template: 'Электроэнцефалография' },
            { id: 'exam-n3', name: 'УЗДГ БЦА', template: 'УЗДГ брахиоцефальных артерий' },
        ],
        labs: [
            { id: 'lab-n1', name: 'СРБ', template: 'С-реактивный белок' },
            { id: 'lab-n2', name: 'Витамин B12', template: 'Витамин B12, фолиевая кислота' },
        ],
        followup: [
            { id: 'follow-n1', name: 'Через месяц', template: 'Контроль через 1 месяц с дневником головной боли' },
        ]
    },

    // ============================================
    // ДЕРМАТОЛОГИЯ
    // ============================================
    dermatology: {
        medications: [
            { id: 'med-d1', name: 'Топический ГКС (слабый)', template: 'Гидрокортизон 1% крем 2 р/д 7-10 дней' },
            { id: 'med-d2', name: 'Топический ГКС (средний)', template: 'Мометазон 0.1% крем 1 р/д 7-14 дней' },
            { id: 'med-d3', name: 'Топический ГКС (сильный)', template: 'Бетаметазон 0.05% мазь 1-2 р/д 5-7 дней' },
            { id: 'med-d4', name: 'Антигистаминный', template: 'Цетиризин 10 мг вечером 14 дней' },
            { id: 'med-d5', name: 'Противогрибковый (местно)', template: 'Клотримазол 1% крем 2 р/д 2-4 недели' },
            { id: 'med-d6', name: 'Противогрибковый (системно)', template: 'Флуконазол 150 мг 1 р/нед 2-4 недели' },
            { id: 'med-d7', name: 'Антибиотик (местно)', template: 'Мупироцин 2% мазь 2 р/д 5-7 дней' },
            { id: 'med-d8', name: 'Ретиноид (местно)', template: 'Адапален 0.1% гель 1 р/д на ночь' },
            { id: 'med-d9', name: 'Эмолент', template: 'Эмолент (Локобейз, Липикар) 2 р/д постоянно' },
            { id: 'med-d10', name: 'Антибиотик при акне', template: 'Доксициклин 100 мг 1 р/д 2-3 месяца' },
        ],
        examinations: [
            { id: 'exam-d1', name: 'Дерматоскопия', template: 'Дерматоскопия образований' },
            { id: 'exam-d2', name: 'Соскоб на грибы', template: 'Соскоб с кожи/ногтей на грибы (КОН-тест)' },
            { id: 'exam-d3', name: 'Лампа Вуда', template: 'Осмотр под лампой Вуда' },
            { id: 'exam-d4', name: 'Биопсия кожи', template: 'Биопсия кожи с гистологией' },
            { id: 'exam-d5', name: 'Аллергопробы', template: 'Кожные аллергопробы (прик-тест)' },
            { id: 'exam-d6', name: 'Patch-тест', template: 'Патч-тест (контактная аллергия)' },
        ],
        labs: [
            { id: 'lab-d1', name: 'IgE общий', template: 'Общий IgE (атопия)' },
            { id: 'lab-d2', name: 'Специфические IgE', template: 'Специфические IgE к аллергенам' },
            { id: 'lab-d3', name: 'Посев на флору', template: 'Посев отделяемого на флору и чувствительность' },
            { id: 'lab-d4', name: 'Антитела к ВПГ', template: 'IgM, IgG к вирусу простого герпеса 1,2 типа' },
            { id: 'lab-d5', name: 'ОАК + СОЭ', template: 'Общий анализ крови с СОЭ' },
            { id: 'lab-d6', name: 'Глюкоза', template: 'Глюкоза крови натощак' },
        ],
        followup: [
            { id: 'follow-d1', name: 'Через 2 недели', template: 'Контроль эффективности терапии через 2 недели' },
            { id: 'follow-d2', name: 'Через месяц', template: 'Контроль через 1 месяц' },
            { id: 'follow-d3', name: 'Динамика образований', template: 'Контроль динамики образований через 3 месяца' },
            { id: 'follow-d4', name: 'Ежегодный осмотр', template: 'Ежегодный осмотр родинок (картирование)' },
        ]
    },

    // ============================================
    // СТОМАТОЛОГИЯ
    // ============================================
    dentistry: {
        medications: [
            { id: 'med-t1', name: 'Анестетик', template: 'Артикаин 4% + эпинефрин 1:100000' },
            { id: 'med-t2', name: 'Антибиотик (стандарт)', template: 'Амоксициллин 500 мг 3 р/д 5-7 дней' },
            { id: 'med-t3', name: 'Антибиотик + клавуланат', template: 'Амоксиклав 625 мг 2 р/д 5-7 дней' },
            { id: 'med-t4', name: 'Антибиотик (аллергия на пенициллины)', template: 'Азитромицин 500 мг 1 р/д 3 дня' },
            { id: 'med-t5', name: 'НПВС', template: 'Кетопрофен 100 мг при болях, max 200 мг/сут' },
            { id: 'med-t6', name: 'Парацетамол', template: 'Парацетамол 500 мг при болях, max 4 г/сут' },
            { id: 'med-t7', name: 'Полоскание антисептик', template: 'Хлоргексидин 0.05% полоскание 3 р/д после еды' },
            { id: 'med-t8', name: 'Полоскание содо-солевое', template: 'Содо-солевые ванночки (по 1 ч.л. на стакан) 4-5 р/д' },
            { id: 'med-t9', name: 'Гемостатик', template: 'Транексамовая кислота 500 мг 3 р/д 3 дня' },
            { id: 'med-t10', name: 'Гель для десен', template: 'Метрогил Дента гель 2 р/д 7-10 дней' },
        ],
        examinations: [
            { id: 'exam-t1', name: 'ОПТГ', template: 'Ортопантомограмма (панорамный снимок)' },
            { id: 'exam-t2', name: 'Прицельный снимок', template: 'Прицельный рентген зуба' },
            { id: 'exam-t3', name: 'КЛКТ', template: 'Конусно-лучевая КТ (3D)' },
            { id: 'exam-t4', name: 'ТРГ', template: 'Телерентгенограмма в боковой проекции' },
            { id: 'exam-t5', name: 'Слепки', template: 'Снятие слепков для моделей' },
            { id: 'exam-t6', name: 'ЭОД', template: 'Электроодонтодиагностика' },
        ],
        labs: [
            { id: 'lab-t1', name: 'ОАК', template: 'Общий анализ крови' },
            { id: 'lab-t2', name: 'Коагулограмма', template: 'МНО, ПТИ, время свертывания' },
            { id: 'lab-t3', name: 'Глюкоза', template: 'Глюкоза крови натощак' },
            { id: 'lab-t4', name: 'Инфекции', template: 'ВИЧ, гепатит B, C, сифилис' },
            { id: 'lab-t5', name: 'Посев из зубодесневого кармана', template: 'Посев на флору из ЗДК' },
        ],
        followup: [
            { id: 'follow-t1', name: 'На следующий день', template: 'Осмотр на следующий день после удаления' },
            { id: 'follow-t2', name: 'Снятие швов', template: 'Снятие швов через 7-10 дней' },
            { id: 'follow-t3', name: 'Контроль пломбы', template: 'Контроль пломбы через 6 месяцев' },
            { id: 'follow-t4', name: 'Проф. осмотр', template: 'Профилактический осмотр через 6 месяцев' },
            { id: 'follow-t5', name: 'Профгигиена', template: 'Профессиональная гигиена полости рта' },
        ]
    }
};

// ============================================
// CATEGORY ICONS
// ============================================
const CATEGORY_META = {
    medications: { icon: '💊', label: 'Медикаменты' },
    examinations: { icon: '🔬', label: 'Обследования' },
    labs: { icon: '🧪', label: 'Анализы' },
    followup: { icon: '📅', label: 'Контроль' }
};

// ============================================
// MAIN COMPONENT
// ============================================
const TreatmentTemplates = ({
    specialty = 'general',
    onSelect,                    // (template, category, field) => void
    targetField = 'treatment',   // 'treatment' | 'examinations' | 'consultations'
    disabled = false,
    recentTemplates = [],        // Недавно использованные
    onRecentUpdate,
}) => {
    const [activeCategory, setActiveCategory] = useState('medications');
    const [searchQuery, setSearchQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);

    // Получаем шаблоны для специальности
    const templates = useMemo(() => {
        return TEMPLATES[specialty] || TEMPLATES.general;
    }, [specialty]);

    // Фильтрация по поиску
    const filteredTemplates = useMemo(() => {
        const categoryTemplates = templates[activeCategory] || [];

        if (!searchQuery) return categoryTemplates;

        const query = searchQuery.toLowerCase();
        return categoryTemplates.filter(t =>
            t.name.toLowerCase().includes(query) ||
            t.template.toLowerCase().includes(query)
        );
    }, [templates, activeCategory, searchQuery]);

    // Обработчик выбора
    const handleSelect = useCallback((item) => {
        onSelect?.(item.template, activeCategory, targetField);

        // Добавляем в недавние
        if (onRecentUpdate) {
            const newRecent = [item.id, ...recentTemplates.filter(id => id !== item.id)].slice(0, 5);
            onRecentUpdate(newRecent);
        }

        setIsOpen(false);
        setSearchQuery('');
    }, [onSelect, activeCategory, targetField, recentTemplates, onRecentUpdate]);

    // Недавние шаблоны
    const recentItems = useMemo(() => {
        const allTemplates = Object.values(templates).flat();
        return recentTemplates
            .map(id => allTemplates.find(t => t.id === id))
            .filter(Boolean)
            .slice(0, 3);
    }, [templates, recentTemplates]);

    if (disabled) return null;

    return (
        <div className="treatment-templates">
            {/* Trigger Button */}
            <button
                className="treatment-templates__trigger"
                onClick={() => setIsOpen(!isOpen)}
                type="button"
            >
                📋 Шаблоны
            </button>

            {/* Dropdown Panel */}
            {isOpen && (
                <div className="treatment-templates__panel">
                    {/* Search */}
                    <div className="treatment-templates__search">
                        <input
                            type="text"
                            placeholder="Поиск шаблона..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            autoFocus
                        />
                    </div>

                    {/* Recent */}
                    {recentItems.length > 0 && !searchQuery && (
                        <div className="treatment-templates__recent">
                            <div className="treatment-templates__recent-label">⭐ Недавние</div>
                            {recentItems.map(item => (
                                <button
                                    key={item.id}
                                    className="treatment-templates__item treatment-templates__item--recent"
                                    onClick={() => handleSelect(item)}
                                >
                                    {item.template}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Categories */}
                    <div className="treatment-templates__categories">
                        {Object.entries(CATEGORY_META).map(([key, meta]) => (
                            <button
                                key={key}
                                className={`treatment-templates__category ${activeCategory === key ? 'treatment-templates__category--active' : ''}`}
                                onClick={() => setActiveCategory(key)}
                            >
                                <span className="treatment-templates__category-icon">{meta.icon}</span>
                                <span className="treatment-templates__category-label">{meta.label}</span>
                            </button>
                        ))}
                    </div>

                    {/* Items */}
                    <div className="treatment-templates__list">
                        {filteredTemplates.length > 0 ? (
                            filteredTemplates.map(item => (
                                <button
                                    key={item.id}
                                    className="treatment-templates__item"
                                    onClick={() => handleSelect(item)}
                                >
                                    <span className="treatment-templates__item-name">{item.name}</span>
                                    <span className="treatment-templates__item-template">{item.template}</span>
                                </button>
                            ))
                        ) : (
                            <div className="treatment-templates__empty">
                                Шаблоны не найдены
                            </div>
                        )}
                    </div>

                    {/* Footer hint */}
                    <div className="treatment-templates__footer">
                        Клик для вставки в поле
                    </div>
                </div>
            )}

            {/* Backdrop */}
            {isOpen && (
                <div
                    className="treatment-templates__backdrop"
                    onClick={() => setIsOpen(false)}
                />
            )}
        </div>
    );
};

export default TreatmentTemplates;

// Экспорт шаблонов для использования в других местах
export { TEMPLATES, CATEGORY_META };
