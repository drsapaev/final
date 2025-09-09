import React, { useState, useEffect } from 'react';
import { 
  Calendar, 
  Clock, 
  DollarSign, 
  User, 
  Stethoscope, 
  FileText, 
  CheckCircle, 
  AlertCircle,
  Plus,
  Edit,
  Trash2,
  Download,
  Printer,
  Send
} from 'lucide-react';

/**
 * Компонент планирования лечения для стоматологической панели
 * Поддерживает:
 * - Создание и управление планами лечения
 * - Расчет стоимости и времени
 * - Планирование этапов лечения
 * - Экспорт и печать планов
 * - Отправка планов пациенту
 */
const TreatmentPlanner = ({ 
  patientId, 
  patientName, 
  initialPlan = null, 
  onSave, 
  onSendToPatient 
}) => {
  const [treatmentPlan, setTreatmentPlan] = useState(initialPlan || []);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [totalCost, setTotalCost] = useState(0);
  const [totalTime, setTotalTime] = useState(0);
  const [planStatus, setPlanStatus] = useState('draft'); // draft, approved, in_progress, completed

  // Обновление общей стоимости и времени
  useEffect(() => {
    const cost = treatmentPlan.reduce((sum, item) => sum + (item.estimatedCost || 0), 0);
    const time = treatmentPlan.reduce((sum, item) => sum + (item.estimatedTime || 0), 0);
    setTotalCost(cost);
    setTotalTime(time);
  }, [treatmentPlan]);

  // Добавление нового этапа лечения
  const addTreatmentStage = (stageData) => {
    const newStage = {
      id: Date.now(),
      ...stageData,
      status: 'planned',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    setTreatmentPlan(prev => [...prev, newStage]);
    setShowAddModal(false);
  };

  // Обновление этапа лечения
  const updateTreatmentStage = (id, updates) => {
    setTreatmentPlan(prev => prev.map(item => 
      item.id === id 
        ? { ...item, ...updates, updatedAt: new Date().toISOString() }
        : item
    ));
    setEditingItem(null);
  };

  // Удаление этапа лечения
  const removeTreatmentStage = (id) => {
    setTreatmentPlan(prev => prev.filter(item => item.id !== id));
  };

  // Изменение статуса этапа
  const updateStageStatus = (id, status) => {
    updateTreatmentStage(id, { status });
  };

  // Сохранение плана
  const handleSave = () => {
    const planData = {
      patientId,
      patientName,
      treatmentPlan,
      totalCost,
      totalTime,
      status: planStatus,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    
    if (onSave) {
      onSave(planData);
    }
  };

  // Экспорт плана в PDF
  const exportToPDF = () => {
    // Здесь будет логика экспорта в PDF
    console.log('Экспорт в PDF:', { treatmentPlan, totalCost, totalTime });
  };

  // Отправка плана пациенту
  const sendToPatient = () => {
    if (onSendToPatient) {
      onSendToPatient({
        patientId,
        patientName,
        treatmentPlan,
        totalCost,
        totalTime
      });
    }
  };

  // Получение цвета статуса
  const getStatusColor = (status) => {
    const colors = {
      planned: '#f59e0b',
      in_progress: '#3b82f6',
      completed: '#10b981',
      cancelled: '#ef4444',
      on_hold: '#6b7280'
    };
    return colors[status] || '#6b7280';
  };

  // Получение иконки статуса
  const getStatusIcon = (status) => {
    const icons = {
      planned: <Clock size={16} />,
      in_progress: <Stethoscope size={16} />,
      completed: <CheckCircle size={16} />,
      cancelled: <AlertCircle size={16} />,
      on_hold: <Clock size={16} />
    };
    return icons[status] || <Clock size={16} />;
  };

  return (
    <div className="treatment-planner" style={{ width: '100%' }}>
      {/* Заголовок и действия */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px',
        padding: '15px',
        backgroundColor: '#f9fafb',
        borderRadius: '8px',
        border: '1px solid #e5e7eb'
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>
            План лечения: {patientName}
          </h3>
          <p style={{ margin: '5px 0 0 0', color: '#6b7280', fontSize: '14px' }}>
            Общая стоимость: {totalCost.toLocaleString()} сум | Время: {totalTime} мин
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '10px' }}>
          <select
            value={planStatus}
            onChange={(e) => setPlanStatus(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: '#fff'
            }}
          >
            <option value="draft">Черновик</option>
            <option value="approved">Одобрен</option>
            <option value="in_progress">В процессе</option>
            <option value="completed">Завершен</option>
          </select>
          
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: '#3b82f6',
              color: '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}
          >
            <Plus size={16} />
            Добавить этап
          </button>
          
          <button
            onClick={handleSave}
            style={{
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}
          >
            <FileText size={16} />
            Сохранить
          </button>
        </div>
      </div>

      {/* Список этапов лечения */}
      <div style={{ marginBottom: '20px' }}>
        {treatmentPlan.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '40px',
            color: '#6b7280',
            backgroundColor: '#f9fafb',
            borderRadius: '8px',
            border: '2px dashed #d1d5db'
          }}>
            <Stethoscope size={48} style={{ marginBottom: '16px', opacity: 0.5 }} />
            <p style={{ margin: 0, fontSize: '16px' }}>План лечения пуст</p>
            <p style={{ margin: '5px 0 0 0', fontSize: '14px' }}>
              Нажмите "Добавить этап" для создания плана лечения
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {treatmentPlan.map((stage, index) => (
              <div key={stage.id} style={{
                padding: '20px',
                backgroundColor: '#fff',
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      width: '30px',
                      height: '30px',
                      borderRadius: '50%',
                      backgroundColor: '#3b82f6',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 'bold',
                      fontSize: '14px'
                    }}>
                      {index + 1}
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>
                        {stage.title}
                      </h4>
                      <p style={{ margin: '5px 0 0 0', color: '#6b7280', fontSize: '14px' }}>
                        Зубы: {stage.teethInvolved}
                      </p>
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      backgroundColor: getStatusColor(stage.status) + '20',
                      color: getStatusColor(stage.status)
                    }}>
                      {getStatusIcon(stage.status)}
                      <span style={{ fontSize: '12px', fontWeight: '500' }}>
                        {stage.status === 'planned' ? 'Запланировано' :
                         stage.status === 'in_progress' ? 'В процессе' :
                         stage.status === 'completed' ? 'Завершено' :
                         stage.status === 'cancelled' ? 'Отменено' : 'На удержании'}
                      </span>
                    </div>
                    
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button
                        onClick={() => setEditingItem(stage)}
                        style={{
                          padding: '4px 8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px',
                          backgroundColor: '#fff',
                          cursor: 'pointer'
                        }}
                        title="Редактировать"
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        onClick={() => removeTreatmentStage(stage.id)}
                        style={{
                          padding: '4px 8px',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px',
                          backgroundColor: '#fff',
                          cursor: 'pointer',
                          color: '#ef4444'
                        }}
                        title="Удалить"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
                
                <div style={{ marginBottom: '15px' }}>
                  <p style={{ margin: 0, color: '#374151', lineHeight: '1.5' }}>
                    {stage.description}
                  </p>
                </div>
                
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                  gap: '15px',
                  padding: '15px',
                  backgroundColor: '#f9fafb',
                  borderRadius: '6px'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', marginBottom: '5px' }}>
                      <DollarSign size={16} color="#10b981" />
                      <span style={{ fontWeight: '600', color: '#10b981' }}>
                        {stage.estimatedCost?.toLocaleString() || 0} сум
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>Стоимость</span>
                  </div>
                  
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', marginBottom: '5px' }}>
                      <Clock size={16} color="#3b82f6" />
                      <span style={{ fontWeight: '600', color: '#3b82f6' }}>
                        {stage.estimatedTime || 0} мин
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>Время</span>
                  </div>
                  
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', marginBottom: '5px' }}>
                      <Calendar size={16} color="#f59e0b" />
                      <span style={{ fontWeight: '600', color: '#f59e0b' }}>
                        {stage.scheduledDate ? new Date(stage.scheduledDate).toLocaleDateString('ru-RU') : 'Не назначено'}
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>Дата</span>
                  </div>
                  
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', marginBottom: '5px' }}>
                      <User size={16} color="#8b5cf6" />
                      <span style={{ fontWeight: '600', color: '#8b5cf6' }}>
                        {stage.doctor || 'Не назначен'}
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>Врач</span>
                  </div>
                </div>
                
                {stage.notes && (
                  <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#f3f4f6', borderRadius: '6px' }}>
                    <p style={{ margin: 0, fontSize: '14px', color: '#374151' }}>
                      <strong>Примечания:</strong> {stage.notes}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Действия с планом */}
      {treatmentPlan.length > 0 && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '15px',
          backgroundColor: '#f9fafb',
          borderRadius: '8px',
          border: '1px solid #e5e7eb'
        }}>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={exportToPDF}
              style={{
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Download size={16} />
              Экспорт PDF
            </button>
            
            <button
              onClick={() => window.print()}
              style={{
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Printer size={16} />
              Печать
            </button>
          </div>
          
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={sendToPatient}
              style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: '6px',
                backgroundColor: '#10b981',
                color: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <Send size={16} />
              Отправить пациенту
            </button>
          </div>
        </div>
      )}

      {/* Модальное окно добавления/редактирования этапа */}
      {(showAddModal || editingItem) && (
        <TreatmentStageModal
          stage={editingItem}
          onSave={editingItem ? updateTreatmentStage : addTreatmentStage}
          onClose={() => {
            setShowAddModal(false);
            setEditingItem(null);
          }}
        />
      )}
    </div>
  );
};

// Модальное окно для добавления/редактирования этапа лечения
const TreatmentStageModal = ({ stage, onSave, onClose }) => {
  const [formData, setFormData] = useState({
    title: stage?.title || '',
    description: stage?.description || '',
    teethInvolved: stage?.teethInvolved || '',
    estimatedCost: stage?.estimatedCost || 0,
    estimatedTime: stage?.estimatedTime || 0,
    scheduledDate: stage?.scheduledDate || '',
    doctor: stage?.doctor || '',
    notes: stage?.notes || '',
    priority: stage?.priority || 'medium'
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(stage?.id, formData);
  };

  return (
    <div style={{
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
      <div style={{
        backgroundColor: '#fff',
        borderRadius: '8px',
        padding: '20px',
        width: '500px',
        maxHeight: '80vh',
        overflow: 'auto'
      }}>
        <h3 style={{ margin: '0 0 20px 0' }}>
          {stage ? 'Редактировать этап' : 'Добавить этап лечения'}
        </h3>
        
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Название этапа:
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
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
              Описание:
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              required
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

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Зубы:
              </label>
              <input
                type="text"
                value={formData.teethInvolved}
                onChange={(e) => setFormData({ ...formData, teethInvolved: e.target.value })}
                placeholder="11, 12, 13..."
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              />
            </div>
            
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Приоритет:
              </label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              >
                <option value="low">Низкий</option>
                <option value="medium">Средний</option>
                <option value="high">Высокий</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Стоимость (сум):
              </label>
              <input
                type="number"
                value={formData.estimatedCost}
                onChange={(e) => setFormData({ ...formData, estimatedCost: parseInt(e.target.value) || 0 })}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              />
            </div>
            
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Время (мин):
              </label>
              <input
                type="number"
                value={formData.estimatedTime}
                onChange={(e) => setFormData({ ...formData, estimatedTime: parseInt(e.target.value) || 0 })}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Дата:
              </label>
              <input
                type="date"
                value={formData.scheduledDate}
                onChange={(e) => setFormData({ ...formData, scheduledDate: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              />
            </div>
            
            <div>
              <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
                Врач:
              </label>
              <input
                type="text"
                value={formData.doctor}
                onChange={(e) => setFormData({ ...formData, doctor: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px'
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>
              Примечания:
            </label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={2}
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
              {stage ? 'Обновить' : 'Добавить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TreatmentPlanner;
