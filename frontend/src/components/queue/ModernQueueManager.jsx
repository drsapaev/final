import React, { useState, useEffect, useRef } from 'react';
import { 
  QrCode, 
  RefreshCw, 
  Play, 
  Pause, 
  Users, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  Phone,
  Calendar,
  TrendingUp,
  Download,
  Printer,
  Eye,
  UserCheck,
  X,
  ChevronRight,
  Activity
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-hot-toast';
import './ModernQueueManager.css';

const ModernQueueManager = ({
  selectedDate = new Date().toISOString().split('T')[0],
  selectedDoctor = '',
  searchQuery = '',
  onQueueUpdate,
  language = 'ru',
  theme = 'light',
  doctors = [],
  ...props
}) => {
  const { getColor } = useTheme();
  const [loading, setLoading] = useState(false);
  const [queueData, setQueueData] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showQrDialog, setShowQrDialog] = useState(false);
  const [showStatsDialog, setShowStatsDialog] = useState(false);
  
  const refreshIntervalRef = useRef(null);

  // Переводы
  const t = {
    ru: {
      title: 'Управление онлайн-очередью',
      generateQr: 'Генерировать QR код',
      refreshQueue: 'Обновить очередь',
      openReception: 'Открыть прием',
      receptionOpen: 'Прием открыт',
      autoRefresh: 'Автообновление',
      statistics: 'Статистика',
      currentQueue: 'Текущая очередь',
      totalEntries: 'Всего записей',
      waiting: 'Ожидают',
      completed: 'Завершено',
      available: 'Свободно',
      selectDoctor: 'Выберите врача',
      queueEmpty: 'Очередь пуста',
      queueNotFound: 'Очередь не найдена',
      patient: 'Пациент',
      phone: 'Телефон',
      time: 'Время',
      status: 'Статус',
      actions: 'Действия',
      call: 'Вызвать',
      called: 'Вызван',
      cancel: 'Отмена',
      download: 'Скачать',
      print: 'Печать'
    }
  }[language] || {};

  // Автообновление
  useEffect(() => {
    if (autoRefresh && selectedDoctor) {
      refreshIntervalRef.current = setInterval(() => {
        loadQueue();
        loadStatistics();
      }, 10000);
    } else {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, selectedDoctor]);

  // Загрузка данных очереди
  const loadQueue = async () => {
    if (!selectedDoctor) return;
    
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/queue/status/${selectedDoctor}?target_date=${selectedDate}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки статуса очереди');
      }

      const queueStatus = await response.json();
      
      const queueData = {
        id: selectedDoctor,
        is_open: queueStatus.active,
        total_entries: queueStatus.entries.length,
        waiting_entries: queueStatus.queue_length,
        current_number: queueStatus.current_number,
        entries: queueStatus.entries.map(entry => ({
          id: entry.number,
          number: entry.number,
          patient_name: entry.patient_name,
          phone: entry.phone || '',
          status: entry.status,
          source: entry.source,
          created_at: entry.created_at
        }))
      };
      
      setQueueData(queueData);
    } catch (error) {
      console.error('Error loading queue:', error);
      toast.error(error.message || 'Ошибка загрузки очереди');
    } finally {
      setLoading(false);
    }
  };

  // Загрузка статистики
  const loadStatistics = async () => {
    if (!selectedDoctor) return;
    
    try {
      // Мок данных для демонстрации
      const mockStats = {
        total_entries: 8,
        waiting: 3,
        completed: 4,
        cancelled: 1,
        available_slots: 12,
        average_wait_time: 15,
        current_wait_time: 8
      };
      
      setStatistics(mockStats);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  // Генерация QR кода
  const generateQR = async () => {
    if (!selectedDoctor || !selectedDate) {
      toast.error('Выберите врача и дату');
      return;
    }
    
    setLoading(true);
    try {
      // Определяем отделение на основе врача
      const doctor = doctors.find(d => d.id == selectedDoctor);
      const department = doctor?.department || 'general';
      
      const response = await fetch('/api/v1/admin/qr-tokens/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          specialist_id: parseInt(selectedDoctor),
          department: department,
          expires_hours: 24
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка генерации QR токена');
      }

      const qrTokenData = await response.json();
      
      const qrData = {
        token: qrTokenData.token,
        specialist_name: doctor?.full_name || doctor?.name || 'Врач',
        department: qrTokenData.department,
        expires_at: qrTokenData.expires_at,
        qr_code_base64: qrTokenData.qr_code_base64,
        url: qrTokenData.qr_url
      };
      
      setQrData(qrData);
      setShowQrDialog(true);
      toast.success('QR код сгенерирован');
    } catch (error) {
      console.error('Error generating QR:', error);
      toast.error(error.message || 'Ошибка генерации QR кода');
    } finally {
      setLoading(false);
    }
  };

  // Открытие приема
  const openReception = async () => {
    if (!selectedDoctor) {
      toast.error('Выберите врача');
      return;
    }
    
    setLoading(true);
    try {
      // Мок для демонстрации
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setQueueData(prev => prev ? { ...prev, is_open: true } : null);
      toast.success('Прием открыт');
      
      if (onQueueUpdate) {
        onQueueUpdate();
      }
    } catch (error) {
      console.error('Error opening reception:', error);
      toast.error('Ошибка открытия приема');
    } finally {
      setLoading(false);
    }
  };

  // Вызов пациента
  const callPatient = async (entryId) => {
    if (!selectedDoctor) {
      toast.error('Выберите врача');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/api/v1/queue/${selectedDoctor}/call-next`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка вызова пациента');
      }

      const result = await response.json();
      
      if (result.success) {
        toast.success(`Вызван пациент: ${result.patient.name} (№${result.patient.number})`);
        // Обновляем данные очереди
        await loadQueue();
      } else {
        toast.info(result.message || 'Нет пациентов в очереди');
      }
    } catch (error) {
      console.error('Error calling patient:', error);
      toast.error(error.message || 'Ошибка вызова пациента');
    } finally {
      setLoading(false);
    }
  };

  // Форматирование времени
  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Получение цвета статуса
  const getStatusColor = (status) => {
    switch (status) {
      case 'waiting': return getColor('warning');
      case 'called': return getColor('primary');
      case 'completed': return getColor('success');
      case 'cancelled': return getColor('danger');
      default: return getColor('textSecondary');
    }
  };

  // Получение текста статуса
  const getStatusText = (status) => {
    switch (status) {
      case 'waiting': return 'Ожидает';
      case 'called': return 'Вызван';
      case 'completed': return 'Завершен';
      case 'cancelled': return 'Отменен';
      default: return status;
    }
  };

  // Скачивание QR кода
  const downloadQR = () => {
    if (!qrData || !qrData.qr_code_base64) return;
    
    // Создаем ссылку для скачивания изображения
    const link = document.createElement('a');
    link.download = `qr-queue-${selectedDate}-${qrData.specialist_name.replace(/\s+/g, '_')}.png`;
    link.href = qrData.qr_code_base64;
    link.click();
    
    toast.success('QR код скачан');
  };

  return (
    <div className={`modern-queue-manager ${props.className || ''}`} {...props}>
      {/* Заголовок */}
      <div className="queue-header">
        <h2 style={{ color: getColor('textPrimary') }}>
          {t.title}
        </h2>
        
        <div className="queue-actions">
          <button
            type="button"
            className="queue-btn queue-btn--primary"
            onClick={() => setShowStatsDialog(true)}
            disabled={!statistics}
            style={{
              backgroundColor: getColor('primary'),
              color: 'white'
            }}
          >
            <TrendingUp size={18} />
            <span>{t.statistics}</span>
          </button>
        </div>
      </div>

      {/* Статистические карточки */}
      {statistics && (
        <div className="stats-grid">
          <div className="stat-card" style={{ backgroundColor: getColor('cardBg') }}>
            <div className="stat-icon" style={{ backgroundColor: getColor('primary') }}>
              <Users size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value" style={{ color: getColor('textPrimary') }}>
                {statistics.total_entries}
              </div>
              <div className="stat-label" style={{ color: getColor('textSecondary') }}>
                {t.totalEntries}
              </div>
            </div>
          </div>

          <div className="stat-card" style={{ backgroundColor: getColor('cardBg') }}>
            <div className="stat-icon" style={{ backgroundColor: getColor('warning') }}>
              <Clock size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value" style={{ color: getColor('textPrimary') }}>
                {statistics.waiting}
              </div>
              <div className="stat-label" style={{ color: getColor('textSecondary') }}>
                {t.waiting}
              </div>
            </div>
          </div>

          <div className="stat-card" style={{ backgroundColor: getColor('cardBg') }}>
            <div className="stat-icon" style={{ backgroundColor: getColor('success') }}>
              <CheckCircle size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value" style={{ color: getColor('textPrimary') }}>
                {statistics.completed}
              </div>
              <div className="stat-label" style={{ color: getColor('textSecondary') }}>
                {t.completed}
              </div>
            </div>
          </div>

          <div className="stat-card" style={{ backgroundColor: getColor('cardBg') }}>
            <div className="stat-icon" style={{ backgroundColor: getColor('info') }}>
              <Activity size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-value" style={{ color: getColor('textPrimary') }}>
                {statistics.available_slots}
              </div>
              <div className="stat-label" style={{ color: getColor('textSecondary') }}>
                {t.available}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Панель управления */}
      <div className="queue-controls" style={{ backgroundColor: getColor('cardBg') }}>
        <div className="controls-section">
          <h3 style={{ color: getColor('textPrimary') }}>Управление очередью</h3>
          
          <div className="controls-grid">
            <button
              type="button"
              className="control-btn control-btn--primary"
              onClick={generateQR}
              disabled={!selectedDoctor || loading}
              style={{
                backgroundColor: getColor('primary'),
                color: 'white'
              }}
            >
              <QrCode size={20} />
              <span>{t.generateQr}</span>
              {loading && <div className="btn-spinner" />}
            </button>

            <button
              type="button"
              className="control-btn control-btn--secondary"
              onClick={loadQueue}
              disabled={!selectedDoctor || loading}
              style={{
                backgroundColor: getColor('cardBg'),
                color: getColor('textPrimary'),
                borderColor: getColor('border')
              }}
            >
              <RefreshCw size={20} className={loading ? 'spinning' : ''} />
              <span>{t.refreshQueue}</span>
            </button>

            <button
              type="button"
              className="control-btn control-btn--success"
              onClick={openReception}
              disabled={!selectedDoctor || loading || queueData?.is_open}
              style={{
                backgroundColor: queueData?.is_open ? getColor('success') : getColor('cardBg'),
                color: queueData?.is_open ? 'white' : getColor('textPrimary'),
                borderColor: getColor('success')
              }}
            >
              {queueData?.is_open ? <CheckCircle size={20} /> : <Play size={20} />}
              <span>{queueData?.is_open ? t.receptionOpen : t.openReception}</span>
            </button>

            <label className="auto-refresh-control">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                disabled={!selectedDoctor}
              />
              <div className="checkbox-custom" style={{ borderColor: getColor('border') }}>
                {autoRefresh && <CheckCircle size={14} style={{ color: getColor('primary') }} />}
              </div>
              <span style={{ color: getColor('textPrimary') }}>{t.autoRefresh}</span>
              {autoRefresh && <RefreshCw size={16} className="spinning" style={{ color: getColor('primary') }} />}
            </label>
          </div>
        </div>
      </div>

      {/* Текущая очередь */}
      <div className="queue-list" style={{ backgroundColor: getColor('cardBg') }}>
        <div className="queue-list-header">
          <h3 style={{ color: getColor('textPrimary') }}>
            {t.currentQueue}
            {queueData && (
              <span 
                className={`queue-status ${queueData.is_open ? 'open' : 'closed'}`}
                style={{ 
                  backgroundColor: queueData.is_open ? getColor('success') : getColor('warning'),
                  color: 'white'
                }}
              >
                {queueData.is_open ? t.receptionOpen : 'Онлайн-запись'}
              </span>
            )}
          </h3>
          
          {queueData && (
            <div className="queue-summary">
              <span style={{ color: getColor('textSecondary') }}>
                Всего: <strong style={{ color: getColor('textPrimary') }}>{queueData.total_entries}</strong>
              </span>
              <span style={{ color: getColor('textSecondary') }}>
                Ожидают: <strong style={{ color: getColor('warning') }}>{queueData.waiting_entries}</strong>
              </span>
            </div>
          )}
        </div>

        <div className="queue-content">
          {!selectedDoctor ? (
            <div className="queue-message" style={{ color: getColor('textSecondary') }}>
              <AlertCircle size={48} />
              <p>{t.selectDoctor}</p>
            </div>
          ) : !queueData ? (
            <div className="queue-message" style={{ color: getColor('textSecondary') }}>
              <QrCode size={48} />
              <p>{t.queueNotFound}</p>
              <button
                type="button"
                className="message-action-btn"
                onClick={generateQR}
                style={{
                  backgroundColor: getColor('primary'),
                  color: 'white'
                }}
              >
                {t.generateQr}
              </button>
            </div>
          ) : queueData.entries.length === 0 ? (
            <div className="queue-message" style={{ color: getColor('textSecondary') }}>
              <Users size={48} />
              <p>{t.queueEmpty}</p>
            </div>
          ) : (
            <div className="queue-table">
              <div className="queue-table-header">
                <div className="queue-col queue-col--number">№</div>
                <div className="queue-col queue-col--patient">{t.patient}</div>
                <div className="queue-col queue-col--phone">{t.phone}</div>
                <div className="queue-col queue-col--time">{t.time}</div>
                <div className="queue-col queue-col--status">{t.status}</div>
                <div className="queue-col queue-col--actions">{t.actions}</div>
              </div>
              
              <div className="queue-table-body">
                {queueData.entries.map((entry, index) => (
                  <div 
                    key={entry.id} 
                    className={`queue-row ${entry.status === 'called' ? 'called' : ''}`}
                    style={{ 
                      backgroundColor: getColor('cardBg'),
                      borderColor: getColor('border')
                    }}
                  >
                    <div className="queue-col queue-col--number">
                      <div 
                        className={`queue-number ${entry.status === 'called' ? 'pulsing' : ''}`}
                        style={{
                          backgroundColor: entry.status === 'called' ? getColor('warning') : getColor('primary'),
                          color: 'white'
                        }}
                      >
                        {entry.number}
                      </div>
                    </div>
                    
                    <div className="queue-col queue-col--patient">
                      <div className="patient-info">
                        <UserCheck size={16} style={{ color: getColor('textSecondary') }} />
                        <span style={{ color: getColor('textPrimary') }}>
                          {entry.patient_name || 'Не указано'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="queue-col queue-col--phone">
                      <div className="phone-info">
                        <Phone size={16} style={{ color: getColor('textSecondary') }} />
                        <span style={{ color: getColor('textSecondary') }}>
                          {entry.phone || 'Не указан'}
                        </span>
                      </div>
                    </div>
                    
                    <div className="queue-col queue-col--time">
                      <div className="time-info">
                        <Clock size={16} style={{ color: getColor('textSecondary') }} />
                        <span style={{ color: getColor('textSecondary') }}>
                          {formatTime(entry.created_at)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="queue-col queue-col--status">
                      <span 
                        className={`status-badge status-${entry.status}`}
                        style={{
                          backgroundColor: getStatusColor(entry.status),
                          color: 'white'
                        }}
                      >
                        {getStatusText(entry.status)}
                      </span>
                    </div>
                    
                    <div className="queue-col queue-col--actions">
                      {entry.status === 'waiting' && (
                        <button
                          type="button"
                          className="action-btn action-btn--call"
                          onClick={() => callPatient(entry.id)}
                          disabled={loading}
                          style={{
                            backgroundColor: getColor('success'),
                            color: 'white'
                          }}
                          title={t.call}
                        >
                          <Play size={16} />
                        </button>
                      )}
                      {entry.status === 'called' && (
                        <span 
                          className="called-indicator"
                          style={{ color: getColor('warning') }}
                        >
                          <Activity size={16} className="pulsing" />
                          {t.called}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Диалог QR кода */}
      <ModernDialog
        isOpen={showQrDialog}
        onClose={() => setShowQrDialog(false)}
        title="QR код для онлайн-очереди"
        maxWidth="32rem"
      >
        {qrData && (
          <div className="qr-dialog-content">
            <div className="qr-info">
              <p><strong>Специалист:</strong> {qrData.specialist_name}</p>
              <p><strong>Дата:</strong> {new Date(qrData.day).toLocaleDateString('ru-RU')}</p>
              <p><strong>Действует до:</strong> {formatTime(qrData.expires_at)}</p>
            </div>
            
            <div className="qr-code-container">
              {qrData.qr_code_base64 ? (
                <img 
                  src={qrData.qr_code_base64} 
                  alt="QR Code" 
                  style={{ 
                    width: '200px', 
                    height: '200px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                  }} 
                />
              ) : (
                <div className="qr-placeholder">
                  <QrCode size={200} style={{ color: getColor('textSecondary') }} />
                  <p style={{ color: getColor('textSecondary') }}>
                    QR код будет здесь
                  </p>
                </div>
              )}
            </div>
            
            <div className="qr-actions">
              <button
                type="button"
                className="qr-action-btn"
                onClick={downloadQR}
                style={{
                  backgroundColor: getColor('cardBg'),
                  color: getColor('textPrimary'),
                  borderColor: getColor('border')
                }}
              >
                <Download size={16} />
                {t.download}
              </button>
              <button
                type="button"
                className="qr-action-btn"
                onClick={() => window.print()}
                style={{
                  backgroundColor: getColor('primary'),
                  color: 'white'
                }}
              >
                <Printer size={16} />
                {t.print}
              </button>
            </div>
          </div>
        )}
      </ModernDialog>

      {/* Диалог статистики */}
      <ModernDialog
        isOpen={showStatsDialog}
        onClose={() => setShowStatsDialog(false)}
        title="Детальная статистика очереди"
        maxWidth="40rem"
      >
        {statistics && (
          <div className="stats-dialog-content">
            <div className="stats-detailed-grid">
              <div className="stats-card">
                <div className="stats-card-header">
                  <Users size={20} />
                  <span>Записи</span>
                </div>
                <div className="stats-card-body">
                  <div className="stats-item">
                    <span>Всего записей:</span>
                    <strong>{statistics.total_entries}</strong>
                  </div>
                  <div className="stats-item">
                    <span>Ожидают:</span>
                    <strong style={{ color: getColor('warning') }}>{statistics.waiting}</strong>
                  </div>
                  <div className="stats-item">
                    <span>Завершено:</span>
                    <strong style={{ color: getColor('success') }}>{statistics.completed}</strong>
                  </div>
                  <div className="stats-item">
                    <span>Отменено:</span>
                    <strong style={{ color: getColor('danger') }}>{statistics.cancelled}</strong>
                  </div>
                </div>
              </div>

              <div className="stats-card">
                <div className="stats-card-header">
                  <Clock size={20} />
                  <span>Время ожидания</span>
                </div>
                <div className="stats-card-body">
                  <div className="stats-item">
                    <span>Среднее время:</span>
                    <strong>{statistics.average_wait_time} мин</strong>
                  </div>
                  <div className="stats-item">
                    <span>Текущее ожидание:</span>
                    <strong style={{ color: getColor('primary') }}>{statistics.current_wait_time} мин</strong>
                  </div>
                  <div className="stats-item">
                    <span>Свободных мест:</span>
                    <strong style={{ color: getColor('info') }}>{statistics.available_slots}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </ModernDialog>
    </div>
  );
};

export default ModernQueueManager;

