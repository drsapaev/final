/**
 * ExaminationMatrix - Быстрый ввод объективного статуса
 * 
 * Концепция:
 * - Сетка параметров для конкретной специальности
 * - Три состояния: Не выбрано (серый), Норма (зеленый), Патология (красный)
 * - При клике генерирует текст и добавляет в поле "Объективно"
 */

import React, { useState, useEffect } from 'react';
import { Check, AlertCircle, X } from 'lucide-react';
import './ExaminationMatrix.css';

// Конфигурация матриц для разных специальностей
const MATRICES = {
    general: {
        'Общее': ['Состояние', 'Сознание', 'Кожные покровы', 'Лимфоузлы'],
        'Дыхание': ['ЧДД', 'Дыхание', 'Хрипы'],
        'Сердце': ['Тоны', 'Ритм', 'АД', 'Шумы'],
        'Живот': ['Форма', 'Пальпация', 'Печень', 'Селезенка'],
        'Физио': ['Мочеиспускание', 'Стул']
    },
    cardiology: {
        'Осмотр': ['Окраска кожи', 'Отеки', 'Вены шеи'],
        'Сердце': ['Верхушечный толчок', 'Границы', 'Тоны', 'Ритм', 'Шумы'],
        'Легкие': ['Дыхание', 'Хрипы', 'Застойные явления'],
        'Пульс': ['Наполнение', 'Напряжение', 'Дефицит']
    }
};

// Текстовые шаблоны для генерации
const TEMPLATES = {
    'Состояние': { norm: 'состояние удовлетворительное', path: 'состояние средней тяжести' },
    'Сознание': { norm: 'сознание ясное', path: 'сознание угнетено' },
    'Кожные покровы': { norm: 'кожные покровы обычной окраски, чистые', path: 'кожные покровы бледные' },
    'Отеки': { norm: 'отеков нет', path: 'отеки нижних конечностей' },
    'Тоны': { norm: 'тоны сердца звучные, ясные', path: 'тоны сердца приглушены' },
    'Ритм': { norm: 'ритм правильный', path: 'аритмия' },
    'Дыхание': { norm: 'дыхание везикулярное', path: 'дыхание жесткое' },
    'Хрипы': { norm: 'хрипов нет', path: 'сухие хрипы' },
    'Живот': { norm: 'живот мягкий, безболезненный', path: 'живот болезненный при пальпации' }
};

const ExaminationMatrix = ({
    specialty = 'general',
    onGenerateText,
    isEditable = true
}) => {
    const [activeCategory, setActiveCategory] = useState(Object.keys(MATRICES[specialty] || MATRICES.general)[0]);
    const [status, setStatus] = useState({}); // { 'Тоны': 'norm' | 'path' }

    // Update categories if specialty changes
    useEffect(() => {
        const matrix = MATRICES[specialty] || MATRICES.general;
        setActiveCategory(Object.keys(matrix)[0]);
    }, [specialty]);

    const handleToggle = (item, type) => {
        if (!isEditable) return;

        const current = status[item];
        let newType = type;

        // Toggle off if clicking same
        if (current === type) {
            newType = null;
        }

        const newStatus = { ...status, [item]: newType };

        // Remove key if null
        if (!newType) delete newStatus[item];

        setStatus(newStatus);
        generateText(newStatus);
    };

    const generateText = (currentStatus) => {
        const phrases = [];

        Object.entries(currentStatus).forEach(([item, type]) => {
            const template = TEMPLATES[item];
            if (template && template[type]) {
                phrases.push(template[type]);
            } else {
                // Fallback for missing templates
                const prefix = type === 'norm' ? 'N: ' : 'Path: ';
                phrases.push(`${prefix}${item}`);
            }
        });

        const text = phrases.length > 0
            ? phrases.join('. ') + '.'
            : '';

        onGenerateText?.(text);
    };

    const matrix = MATRICES[specialty] || MATRICES.general;
    const items = matrix[activeCategory] || [];

    return (
        <div className={`ex-matrix ${!isEditable ? 'ex-matrix--readonly' : ''}`}>
            {/* Categories */}
            <div className="ex-matrix__categories">
                {Object.keys(matrix).map(cat => (
                    <button
                        key={cat}
                        className={`ex-matrix__cat-btn ${activeCategory === cat ? 'ex-matrix__cat-btn--active' : ''}`}
                        onClick={() => setActiveCategory(cat)}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Grid */}
            <div className="ex-matrix__grid">
                {items.map(item => {
                    const currentStatus = status[item];
                    return (
                        <div
                            key={item}
                            className={`ex-matrix__item ${currentStatus ? `ex-matrix__item--${currentStatus}` : 'ex-matrix__item--normal'}`}
                        >
                            <span className="ex-matrix__label">{item}</span>
                            <div className="ex-matrix__actions">
                                {/* Button: Norm */}
                                <button
                                    className={`ex-matrix__action-btn ex-matrix__action-btn--norm`}
                                    onClick={() => handleToggle(item, 'norm')}
                                    title="Норма"
                                >
                                    <Check size={14} />
                                </button>
                                {/* Button: Path */}
                                <button
                                    className={`ex-matrix__action-btn ex-matrix__action-btn--path`}
                                    onClick={() => handleToggle(item, 'path')}
                                    title="Патология"
                                >
                                    <AlertCircle size={14} />
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default ExaminationMatrix;
