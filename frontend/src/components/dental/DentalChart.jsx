import React, { useState, useCallback, useRef, useEffect } from 'react';
import { 
  Save, 
  RotateCcw, 
  ZoomIn, 
  ZoomOut, 
  Download, 
  Upload,
  Trash2,
  Edit3,
  CheckCircle,
  AlertCircle,
  XCircle,
  Plus,
  Minus
} from 'lucide-react';

/**
 * Компонент схемы зубов для стоматологической панели
 * Поддерживает:
 * - Интерактивную схему зубов (верхняя и нижняя челюсти)
 * - Различные состояния зубов (здоровый, кариес, пломба, коронка, удален и т.д.)
 * - Планирование лечения
 * - Сохранение и загрузку схем
 * - Масштабирование и навигацию
 */
const DentalChart = ({ 
  patientId, 
  initialData = null, 
  onSave, 
  onTreatmentPlan,
  readOnly = false 
}) => {
  const [teeth, setTeeth] = useState({});
  const [selectedTooth, setSelectedTooth] = useState(null);
  const [showToothModal, setShowToothModal] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [treatmentPlan, setTreatmentPlan] = useState([]);
  const [showTreatmentModal, setShowTreatmentModal] = useState(false);
  
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Инициализация схемы зубов
  useEffect(() => {
    if (initialData) {
      setTeeth(initialData.teeth || {});
      setTreatmentPlan(initialData.treatmentPlan || []);
    } else {
      initializeTeeth();
    }
  }, [initialData]);

  // Инициализация зубов (32 зуба)
  const initializeTeeth = () => {
    const teethData = {};
    
    // Верхняя челюсть (11-18, 21-28)
    for (let i = 11; i <= 18; i++) {
      teethData[i] = { 
        id: i, 
        position: 'upper', 
        status: 'healthy', 
        condition: '', 
        treatment: '', 
        notes: '',
        x: 0, y: 0
      };
    }
    for (let i = 21; i <= 28; i++) {
      teethData[i] = { 
        id: i, 
        position: 'upper', 
        status: 'healthy', 
        condition: '', 
        treatment: '', 
        notes: '',
        x: 0, y: 0
      };
    }
    
    // Нижняя челюсть (31-38, 41-48)
    for (let i = 31; i <= 38; i++) {
      teethData[i] = { 
        id: i, 
        position: 'lower', 
        status: 'healthy', 
        condition: '', 
        treatment: '', 
        notes: '',
        x: 0, y: 0
      };
    }
    for (let i = 41; i <= 48; i++) {
      teethData[i] = { 
        id: i, 
        position: 'lower', 
        status: 'healthy', 
        condition: '', 
        treatment: '', 
        notes: '',
        x: 0, y: 0
      };
    }
    
    setTeeth(teethData);
  };

  // Состояния зубов и их цвета
  const toothStatuses = {
    healthy: { color: '#10b981', label: 'Здоровый', icon: '🦷' },
    caries: { color: '#f59e0b', label: 'Кариес', icon: '🦷' },
    filling: { color: '#3b82f6', label: 'Пломба', icon: '🦷' },
    crown: { color: '#8b5cf6', label: 'Коронка', icon: '👑' },
    bridge: { color: '#06b6d4', label: 'Мост', icon: '🌉' },
    implant: { color: '#84cc16', label: 'Имплант', icon: '🔩' },
    missing: { color: '#6b7280', label: 'Отсутствует', icon: '❌' },
    root_canal: { color: '#dc2626', label: 'Лечение каналов', icon: '🔧' },
    extraction: { color: '#ef4444', label: 'К удалению', icon: '⚠️' },
    planned: { color: '#f97316', label: 'Запланировано', icon: '📋' }
  };

  // Обработка клика по зубу
  const handleToothClick = (toothId) => {
    if (readOnly) return;
    
    setSelectedTooth(toothId);
    setShowToothModal(true);
  };

  // Обновление состояния зуба
  const updateTooth = (toothId, updates) => {
    setTeeth(prev => ({
      ...prev,
      [toothId]: { ...prev[toothId], ...updates }
    }));
  };

  // Сохранение схемы
  const handleSave = () => {
    const data = {
      teeth,
      treatmentPlan,
      patientId,
      timestamp: new Date().toISOString()
    };
    
    if (onSave) {
      onSave(data);
    }
  };

  // Добавление в план лечения
  const addToTreatmentPlan = (toothId, treatment) => {
    const tooth = teeth[toothId];
    const newItem = {
      id: Date.now(),
      toothId,
      toothNumber: toothId,
      treatment,
      status: 'planned',
      priority: 'medium',
      estimatedCost: 0,
      estimatedTime: 0,
      notes: ''
    };
    
    setTreatmentPlan(prev => [...prev, newItem]);
  };

  // Обработка масштабирования
  const handleZoom = (direction) => {
    const newZoom = direction === 'in' ? zoom * 1.2 : zoom / 1.2;
    setZoom(Math.max(0.5, Math.min(3, newZoom)));
  };

  // Обработка перетаскивания
  const handleMouseDown = (e) => {
    if (e.target === canvasRef.current) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Отрисовка зуба
  const renderTooth = (toothId, tooth) => {
    const status = toothStatuses[tooth.status] || toothStatuses.healthy;
    const isSelected = selectedTooth === toothId;
    
    return (
      <div
        key={toothId}
        className={`tooth ${isSelected ? 'selected' : ''}`}
        style={{
          position: 'absolute',
          left: tooth.x,
          top: tooth.y,
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          backgroundColor: status.color,
          border: isSelected ? '3px solid #000' : '2px solid #fff',
          cursor: readOnly ? 'default' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '16px',
          fontWeight: 'bold',
          color: '#fff',
          textShadow: '1px 1px 2px rgba(0,0,0,0.5)',
          transition: 'all 0.2s ease',
          transform: `scale(${zoom})`,
          zIndex: isSelected ? 10 : 1
        }}
        onClick={() => handleToothClick(toothId)}
        title={`Зуб ${toothId}: ${status.label}`}
      >
        {toothId}
      </div>
    );
  };

  // Отрисовка челюсти
  const renderJaw = (isUpper = true) => {
    const jawTeeth = Object.values(teeth).filter(tooth => 
      tooth.position === (isUpper ? 'upper' : 'lower')
    );
    
    return (
      <div 
        className={`jaw ${isUpper ? 'upper' : 'lower'}`}
        style={{
          position: 'relative',
          width: '100%',
          height: '120px',
          marginBottom: '20px',
          border: '2px solid #e5e7eb',
          borderRadius: '8px',
          backgroundColor: '#f9fafb'
        }}
      >
        {jawTeeth.map(tooth => renderTooth(tooth.id, tooth))}
      </div>
    );
  };

  return (
    <div className="dental-chart-container" style={{ width: '100%', height: '100%' }}>
      {/* Панель инструментов */}
      <div className="toolbar" style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px',
        backgroundColor: '#f3f4f6',
        borderBottom: '1px solid #d1d5db',
        marginBottom: '20px'
      }}>
        <div className="toolbar-left" style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => handleZoom('in')}
            className="btn btn-sm"
            title="Увеличить"
          >
            <ZoomIn size={16} />
          </button>
          <button
            onClick={() => handleZoom('out')}
            className="btn btn-sm"
            title="Уменьшить"
          >
            <ZoomOut size={16} />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="btn btn-sm"
            title="Сбросить масштаб"
          >
            <RotateCcw size={16} />
          </button>
        </div>

        <div className="toolbar-center" style={{ display: 'flex', gap: '10px' }}>
          <span style={{ fontSize: '14px', fontWeight: '500' }}>
            Масштаб: {Math.round(zoom * 100)}%
          </span>
        </div>

        <div className="toolbar-right" style={{ display: 'flex', gap: '10px' }}>
          {!readOnly && (
            <>
              <button
                onClick={() => setShowTreatmentModal(true)}
                className="btn btn-primary btn-sm"
                title="План лечения"
              >
                <Plus size={16} />
                План лечения
              </button>
              <button
                onClick={handleSave}
                className="btn btn-success btn-sm"
                title="Сохранить"
              >
                <Save size={16} />
                Сохранить
              </button>
            </>
          )}
        </div>
      </div>

      {/* Схема зубов */}
      <div 
        ref={containerRef}
        className="dental-chart"
        style={{
          position: 'relative',
          width: '100%',
          height: '300px',
          overflow: 'hidden',
          border: '1px solid #d1d5db',
          borderRadius: '8px',
          backgroundColor: '#fff',
          transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
          transformOrigin: 'top left'
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Верхняя челюсть */}
        <div style={{ textAlign: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', color: '#374151' }}>Верхняя челюсть</h3>
        </div>
        {renderJaw(true)}
        
        {/* Нижняя челюсть */}
        <div style={{ textAlign: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', color: '#374151' }}>Нижняя челюсть</h3>
        </div>
        {renderJaw(false)}
      </div>

      {/* Легенда состояний зубов */}
      <div className="tooth-legend" style={{
        marginTop: '20px',
        padding: '15px',
        backgroundColor: '#f9fafb',
        borderRadius: '8px',
        border: '1px solid #e5e7eb'
      }}>
        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: '600' }}>
          Состояния зубов:
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
          {Object.entries(toothStatuses).map(([key, status]) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: status.color,
                border: '1px solid #d1d5db'
              }} />
              <span style={{ fontSize: '12px' }}>{status.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Модальное окно зуба */}
      {showToothModal && selectedTooth && (
        <ToothModal
          tooth={teeth[selectedTooth]}
          toothId={selectedTooth}
          onUpdate={(updates) => updateTooth(selectedTooth, updates)}
          onClose={() => setShowToothModal(false)}
          onAddToTreatment={addToTreatmentPlan}
        />
      )}

      {/* Модальное окно плана лечения */}
      {showTreatmentModal && (
        <TreatmentPlanModal
          treatmentPlan={treatmentPlan}
          onUpdate={setTreatmentPlan}
          onClose={() => setShowTreatmentModal(false)}
          teeth={teeth}
        />
      )}
    </div>
  );
};

// Модальное окно для редактирования зуба
const ToothModal = ({ tooth, toothId, onUpdate, onClose, onAddToTreatment }) => {
  const [formData, setFormData] = useState({
    status: tooth.status || 'healthy',
    condition: tooth.condition || '',
    treatment: tooth.treatment || '',
    notes: tooth.notes || ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onUpdate(formData);
    onClose();
  };

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div className="modal-content" style={{
        backgroundColor: '#fff',
        borderRadius: '8px',
        padding: '20px',
        width: '400px',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h3 style={{ margin: '0 0 20px 0' }}>Зуб {toothId}</h3>
        
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Состояние:
            </label>
            <select
              value={formData.status}
              onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px'
              }}
            >
              <option value="healthy">Здоровый</option>
              <option value="caries">Кариес</option>
              <option value="filling">Пломба</option>
              <option value="crown">Коронка</option>
              <option value="bridge">Мост</option>
              <option value="implant">Имплант</option>
              <option value="missing">Отсутствует</option>
              <option value="root_canal">Лечение каналов</option>
              <option value="extraction">К удалению</option>
              <option value="planned">Запланировано</option>
            </select>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Диагноз:
            </label>
            <input
              type="text"
              value={formData.condition}
              onChange={(e) => setFormData({ ...formData, condition: e.target.value })}
              placeholder="Введите диагноз"
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Лечение:
            </label>
            <input
              type="text"
              value={formData.treatment}
              onChange={(e) => setFormData({ ...formData, treatment: e.target.value })}
              placeholder="Введите план лечения"
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Примечания:
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Дополнительные заметки"
              rows={3}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                resize: 'vertical'
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                backgroundColor: '#fff',
                cursor: 'pointer'
              }}
            >
              Отмена
            </button>
            <button
              type="submit"
              style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: '4px',
                backgroundColor: '#3b82f6',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Модальное окно плана лечения
const TreatmentPlanModal = ({ treatmentPlan, onUpdate, onClose, teeth }) => {
  const [newItem, setNewItem] = useState({
    toothId: '',
    treatment: '',
    priority: 'medium',
    estimatedCost: 0,
    estimatedTime: 0,
    notes: ''
  });

  const addItem = () => {
    if (newItem.toothId && newItem.treatment) {
      const item = {
        id: Date.now(),
        ...newItem,
        status: 'planned'
      };
      onUpdate([...treatmentPlan, item]);
      setNewItem({
        toothId: '',
        treatment: '',
        priority: 'medium',
        estimatedCost: 0,
        estimatedTime: 0,
        notes: ''
      });
    }
  };

  const removeItem = (id) => {
    onUpdate(treatmentPlan.filter(item => item.id !== id));
  };

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div className="modal-content" style={{
        backgroundColor: '#fff',
        borderRadius: '8px',
        padding: '20px',
        width: '600px',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h3 style={{ margin: '0 0 20px 0' }}>План лечения</h3>
        
        {/* Добавление нового элемента */}
        <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
          <h4 style={{ margin: '0 0 15px 0' }}>Добавить лечение</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
            <select
              value={newItem.toothId}
              onChange={(e) => setNewItem({ ...newItem, toothId: e.target.value })}
              style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            >
              <option value="">Выберите зуб</option>
              {Object.keys(teeth).map(toothId => (
                <option key={toothId} value={toothId}>Зуб {toothId}</option>
              ))}
            </select>
            <input
              type="text"
              value={newItem.treatment}
              onChange={(e) => setNewItem({ ...newItem, treatment: e.target.value })}
              placeholder="Описание лечения"
              style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>
            <select
              value={newItem.priority}
              onChange={(e) => setNewItem({ ...newItem, priority: e.target.value })}
              style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            >
              <option value="low">Низкий</option>
              <option value="medium">Средний</option>
              <option value="high">Высокий</option>
            </select>
            <input
              type="number"
              value={newItem.estimatedCost}
              onChange={(e) => setNewItem({ ...newItem, estimatedCost: e.target.value })}
              placeholder="Стоимость"
              style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
            <input
              type="number"
              value={newItem.estimatedTime}
              onChange={(e) => setNewItem({ ...newItem, estimatedTime: e.target.value })}
              placeholder="Время (мин)"
              style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
            />
          </div>
          <button
            onClick={addItem}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: '#10b981',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            Добавить
          </button>
        </div>

        {/* Список планов лечения */}
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 15px 0' }}>Текущий план</h4>
          {treatmentPlan.length === 0 ? (
            <p style={{ color: '#6b7280', fontStyle: 'italic' }}>План лечения пуст</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {treatmentPlan.map(item => (
                <div key={item.id} style={{
                  padding: '15px',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  backgroundColor: '#fff'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: '600', marginBottom: '5px' }}>
                        Зуб {item.toothId}: {item.treatment}
                      </div>
                      <div style={{ fontSize: '14px', color: '#6b7280', marginBottom: '5px' }}>
                        Приоритет: {item.priority} | Стоимость: {item.estimatedCost} | Время: {item.estimatedTime} мин
                      </div>
                      {item.notes && (
                        <div style={{ fontSize: '14px', color: '#374151' }}>
                          {item.notes}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => removeItem(item.id)}
                      style={{
                        padding: '4px 8px',
                        border: 'none',
                        borderRadius: '4px',
                        backgroundColor: '#ef4444',
                        color: '#fff',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: '#fff',
              cursor: 'pointer'
            }}
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
};

export default DentalChart;
