/**
 * ExaminationMatrix - Быстрый ввод объективного статуса
 * 
 * Концепция:
 * - Сетка параметров для конкретной специальности
 * - Три состояния: Не выбрано (серый), Норма (зеленый), Патология (красный)
 * - При клике генерирует текст и добавляет в поле "Объективно"
 */

import { useState, useEffect } from 'react';
import { Check, AlertCircle } from 'lucide-react';
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
    'Осмотр': ['Окраска кожи', 'Отеки', 'Вены шеи', 'Пульсация'],
    'Сердце': ['Верхушечный толчок', 'Границы', 'Тоны', 'Ритм', 'Шумы', 'Галоп'],
    'Легкие': ['Дыхание', 'Хрипы', 'Застойные явления', 'Плевральный выпот'],
    'Пульс': ['Наполнение', 'Напряжение', 'Дефицит', 'Аритмия'],
    'АД': ['Систолическое', 'Диастолическое', 'Пульсовое давление']
  },
  dermatology: {
    'Тип кожи': ['Нормальная', 'Сухая', 'Жирная', 'Комбинированная', 'Чувствительная'],
    'Состояние': ['Акне', 'Розацеа', 'Экзема', 'Псориаз', 'Пигментация', 'Морщины'],
    'Локализация': ['Лицо', 'Шея', 'Декольте', 'Руки', 'Тело'],
    'Характеристики': ['Размер', 'Цвет', 'Текстура', 'Границы', 'Симметрия']
  },
  dentist: {
    'Общий осмотр': ['Состояние слизистой', 'Язык', 'Губы', 'Щеки'],
    'Пародонт': ['Кровоточивость', 'Карманы', 'Подвижность', 'Рецессия'],
    'Прикус': ['Ортогнатический', 'Прогнатия', 'Прогения', 'Открытый', 'Глубокий'],
    'Гигиена': ['Хорошая', 'Удовлетворительная', 'Плохая', 'Очень плохая']
  },
  dentistry: {
    'Общий осмотр': ['Состояние слизистой', 'Язык', 'Губы', 'Щеки'],
    'Пародонт': ['Кровоточивость', 'Карманы', 'Подвижность', 'Рецессия'],
    'Прикус': ['Ортогнатический', 'Прогнатия', 'Прогения', 'Открытый', 'Глубокий'],
    'Гигиена': ['Хорошая', 'Удовлетворительная', 'Плохая', 'Очень плохая']
  }
};

// Текстовые шаблоны для генерации
const TEMPLATES = {
  // General
  'Состояние': { norm: 'состояние удовлетворительное', path: 'состояние средней тяжести' },
  'Сознание': { norm: 'сознание ясное', path: 'сознание угнетено' },
  'Кожные покровы': { norm: 'кожные покровы обычной окраски, чистые', path: 'кожные покровы бледные' },
  'Отеки': { norm: 'отеков нет', path: 'отеки нижних конечностей' },
  'Тоны': { norm: 'тоны сердца звучные, ясные', path: 'тоны сердца приглушены' },
  'Ритм': { norm: 'ритм правильный', path: 'аритмия' },
  'Дыхание': { norm: 'дыхание везикулярное', path: 'дыхание жесткое' },
  'Хрипы': { norm: 'хрипов нет', path: 'сухие хрипы' },
  'Живот': { norm: 'живот мягкий, безболезненный', path: 'живот болезненный при пальпации' },
  // Cardiology
  'Окраска кожи': { norm: 'кожные покровы обычной окраски', path: 'кожные покровы бледные, цианотичные' },
  'Вены шеи': { norm: 'вены шеи не набухшие', path: 'набухание вен шеи' },
  'Верхушечный толчок': { norm: 'верхушечный толчок в пределах нормы', path: 'верхушечный толчок смещен' },
  'Границы': { norm: 'границы сердца в пределах нормы', path: 'расширение границ сердца' },
  'Галоп': { norm: 'галопа нет', path: 'ритм галопа' },
  'Застойные явления': { norm: 'застойных явлений нет', path: 'застойные явления в легких' },
  'Плевральный выпот': { norm: 'плеврального выпота нет', path: 'признаки плеврального выпота' },
  'Аритмия': { norm: 'аритмии нет', path: 'аритмия' },
  // Dermatology
  'Нормальная': { norm: 'тип кожи нормальный', path: null },
  'Сухая': { norm: 'кожа сухая', path: null },
  'Жирная': { norm: 'кожа жирная', path: null },
  'Комбинированная': { norm: 'кожа комбинированного типа', path: null },
  'Чувствительная': { norm: 'кожа чувствительная', path: null },
  'Акне': { norm: 'акне отсутствует', path: 'акне различной степени выраженности' },
  'Розацеа': { norm: 'розацеа отсутствует', path: 'признаки розацеа' },
  'Экзема': { norm: 'экземы нет', path: 'экзематозные изменения' },
  'Псориаз': { norm: 'псориаза нет', path: 'псориатические бляшки' },
  'Пигментация': { norm: 'пигментация в пределах нормы', path: 'нарушения пигментации' },
  'Морщины': { norm: 'морщины минимальные', path: 'выраженные морщины' },
  // Dentistry
  'Состояние слизистой': { norm: 'слизистая оболочка полости рта без патологии', path: 'изменения слизистой оболочки' },
  'Язык': { norm: 'язык без патологии', path: 'изменения языка' },
  'Губы': { norm: 'губы без патологии', path: 'изменения губ' },
  'Щеки': { norm: 'слизистая щек без патологии', path: 'изменения слизистой щек' },
  'Кровоточивость': { norm: 'кровоточивости нет', path: 'кровоточивость десен' },
  'Карманы': { norm: 'пародонтальных карманов нет', path: 'пародонтальные карманы' },
  'Подвижность': { norm: 'подвижности зубов нет', path: 'повышенная подвижность зубов' },
  'Рецессия': { norm: 'рецессии десны нет', path: 'рецессия десны' },
  'Ортогнатический': { norm: 'ортогнатический прикус', path: null },
  'Прогнатия': { norm: 'прогнатия', path: null },
  'Прогения': { norm: 'прогения', path: null },
  'Открытый': { norm: 'открытый прикус', path: null },
  'Глубокий': { norm: 'глубокий прикус', path: null },
  'Хорошая': { norm: 'гигиена полости рта хорошая', path: null },
  'Удовлетворительная': { norm: 'гигиена полости рта удовлетворительная', path: null },
  'Плохая': { norm: 'гигиена полости рта плохая', path: null },
  'Очень плохая': { norm: 'гигиена полости рта очень плохая', path: null }
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

    const text = phrases.length > 0 ?
    phrases.join('. ') + '.' :
    '';

    onGenerateText?.(text);
  };

  const matrix = MATRICES[specialty] || MATRICES.general;
  const items = matrix[activeCategory] || [];

  return (
    <div className={`ex-matrix ${!isEditable ? 'ex-matrix--readonly' : ''}`}>
            {/* Categories */}
            <div className="ex-matrix__categories">
                {Object.keys(matrix).map((cat) =>
        <button
          key={cat}
          className={`ex-matrix__cat-btn ${activeCategory === cat ? 'ex-matrix__cat-btn--active' : ''}`}
          onClick={() => setActiveCategory(cat)}>
          
                        {cat}
                    </button>
        )}
            </div>

            {/* Grid */}
            <div className="ex-matrix__grid">
                {items.map((item) => {
          const currentStatus = status[item];
          return (
            <div
              key={item}
              className={`ex-matrix__item ${currentStatus ? `ex-matrix__item--${currentStatus}` : 'ex-matrix__item--normal'}`}>
              
                            <span className="ex-matrix__label">{item}</span>
                            <div className="ex-matrix__actions">
                                {/* Button: Norm */}
                                <button
                  className={'ex-matrix__action-btn ex-matrix__action-btn--norm'}
                  onClick={() => handleToggle(item, 'norm')}
                  title="Норма">
                  
                                    <Check size={14} />
                                </button>
                                {/* Button: Path */}
                                <button
                  className={'ex-matrix__action-btn ex-matrix__action-btn--path'}
                  onClick={() => handleToggle(item, 'path')}
                  title="Патология">
                  
                                    <AlertCircle size={14} />
                                </button>
                            </div>
                        </div>);

        })}
            </div>
        </div>);

};

export default ExaminationMatrix;