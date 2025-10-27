import React, { useState, useEffect, useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useTheme } from '../../contexts/ThemeContext';
import ModernDialog from '../dialogs/ModernDialog';
import { toast } from 'react-toastify';
import { Button, Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Icon, Input } from '../ui/macos';

const ModernQueueManager = ({
  selectedDate = new Date().toISOString().split('T')[0],
  selectedDoctor = '',
  searchQuery = '',
  onQueueUpdate,
  language = 'ru',
  theme = 'light',
  doctors = [],
  onDoctorChange,
  onDateChange,
  ...props
}) => {
  const { theme: themeContext } = useTheme();
  const [loading, setLoading] = useState(false);
  const [queueData, setQueueData] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [internalDoctor, setInternalDoctor] = useState('');
  const [internalDate, setInternalDate] = useState(new Date().toISOString().split('T')[0]);
  const effectiveDoctor = selectedDoctor || internalDoctor;
  const effectiveDate = selectedDate || internalDate;
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
    if (autoRefresh && effectiveDoctor) {
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
  }, [autoRefresh, effectiveDoctor]);

  // Загрузка данных очереди
  const loadQueue = async () => {
    if (!effectiveDoctor) return;
    
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/queue/status/${effectiveDoctor}?target_date=${effectiveDate}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки статуса очереди');
      }

      const queueStatus = await response.json();
      
      const queueData = {
        id: effectiveDoctor,
        is_open: queueStatus.active,
        total_entries: queueStatus.entries.length,
        waiting_entries: queueStatus.queue_length,
        current_number: queueStatus.current_number,
        online_start_time: queueStatus.online_start_time || '07:00',
        online_end_time: queueStatus.online_end_time || '09:00',
        current_time: queueStatus.current_time,
        online_available: queueStatus.online_available,
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
    if (!effectiveDoctor) return;
    
    try {
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
    if (!effectiveDoctor || !effectiveDate) {
      toast.error('Выберите врача и дату');
      return;
    }
    
    setLoading(true);
    try {
      const doctor = doctors.find(d => String(d.id) === String(effectiveDoctor));
      
      const response = await fetch('/api/v1/admin/qr-tokens/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          specialist_id: parseInt(effectiveDoctor),
          department: doctor?.department || 'general',
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
        day: effectiveDate,
        expires_at: qrTokenData.expires_at,
        qr_url: qrTokenData.qr_url,
        online_start_time: '07:00',
        online_end_time: '09:00'
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
    if (!effectiveDoctor) {
      toast.error('Выберите врача');
      return;
    }
    
    setLoading(true);
    try {
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
      const response = await fetch(`/api/v1/queue/${effectiveDoctor}/call-next`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ошибка вызова пациента');
      }

      const result = await response.json();
      
      if (result.success) {
        toast.success(`Вызван пациент: ${result.patient.name} (№${result.patient.number})`);
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

  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'waiting': return 'var(--mac-warning)';
      case 'called': return 'var(--mac-accent-blue)';
      case 'completed': return 'var(--mac-success)';
      case 'cancelled': return 'var(--mac-danger)';
      default: return 'var(--mac-text-secondary)';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'waiting': return 'Ожидает';
      case 'called': return 'Вызван';
      case 'completed': return 'Завершен';
      case 'cancelled': return 'Отменен';
      default: return status;
    }
  };

  const downloadQR = () => {
    if (!qrData || !qrData.qr_url) {
      toast.error('QR данные недоступны');
      return;
    }
    
    const qrInfo = `
QR код для онлайн-очереди

Специалист: ${qrData.specialist_name}
Дата приёма: ${new Date(qrData.day).toLocaleDateString('ru-RU')}
Окно онлайн-записи: ${qrData.online_start_time} - ${qrData.online_end_time}

Ссылка для записи:
${window.location.origin}${qrData.qr_url}

Токен: ${qrData.token}

⏰ QR код действует с ${qrData.online_start_time} до момента открытия приёма в регистратуре
📅 Токен истекает: ${new Date(qrData.expires_at).toLocaleString('ru-RU')}
    `.trim();
    
    const blob = new Blob([qrInfo], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    link.download = `qr-queue-${selectedDate}-${qrData.specialist_name.replace(/\s+/g, '_')}.txt`;
    link.href = URL.createObjectURL(blob);
    link.click();
    URL.revokeObjectURL(link.href);
    
    toast.success('Информация о QR коде скачана');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-5)' }}>
      {/* Статистические карточки */}
      {statistics && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
          <Card style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-4)',
            padding: 'var(--mac-spacing-4)',
            backgroundColor: 'var(--mac-bg-toolbar)',
            border: '1px solid var(--mac-separator)'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-accent-blue)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <Icon name="person" size="large" style={{ color: 'white' }} />
            </div>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                lineHeight: 1
              }}>
                {statistics.total_entries}
              </div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                {t.totalEntries}
              </div>
            </div>
          </Card>

          <Card style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-4)',
            padding: 'var(--mac-spacing-4)',
            backgroundColor: 'var(--mac-bg-toolbar)',
            border: '1px solid var(--mac-separator)'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-warning)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <Icon name="magnifyingglass" size="large" style={{ color: 'white' }} />
            </div>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                lineHeight: 1
              }}>
                {statistics.waiting}
              </div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                {t.waiting}
              </div>
            </div>
          </Card>

          <Card style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-4)',
            padding: 'var(--mac-spacing-4)',
            backgroundColor: 'var(--mac-bg-toolbar)',
            border: '1px solid var(--mac-separator)'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-success)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <Icon name="checkmark.circle" size="large" style={{ color: 'white' }} />
            </div>
            <div>
              <div style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                lineHeight: 1
              }}>
                {statistics.completed}
              </div>
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                {t.completed}
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Панель управления */}
      <Card style={{
        padding: 'var(--mac-spacing-5)',
        backgroundColor: 'var(--mac-bg-toolbar)',
        border: '1px solid var(--mac-separator)'
      }}>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-4)'
        }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Управление очередью
          </h3>
          
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--mac-spacing-3)',
            alignItems: 'end'
          }}>
            <Input
              type="date"
              label="Дата"
              value={effectiveDate}
              onChange={(e) => {
                setInternalDate(e.target.value);
                onDateChange && onDateChange(e.target.value);
              }}
            />

            <select
              value={effectiveDoctor}
              onChange={(e) => {
                setInternalDoctor(e.target.value);
                onDoctorChange && onDoctorChange(e.target.value);
              }}
              style={{
                fontSize: 'var(--mac-font-size-base)',
                padding: 'var(--mac-spacing-3)',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-md)',
                minWidth: '200px',
                fontFamily: 'inherit'
              }}
            >
              <option value="">Выберите врача</option>
              {doctors.map(d => (
                <option key={d.id} value={d.id}>
                  {d.full_name || d.name || d.username || `ID ${d.id}`}
                </option>
              ))}
            </select>

            <Button
              variant="primary"
              size="default"
              onClick={generateQR}
              disabled={!effectiveDoctor || loading}
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
            >
              <Icon name="magnifyingglass" size="small" style={{ color: 'white' }} />
              {t.generateQr}
            </Button>

            <Button
              variant="outline"
              size="default"
              onClick={loadQueue}
              disabled={!effectiveDoctor || loading}
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
            >
              <Icon name="gear" size="small" style={{ color: 'var(--mac-text-primary)' }} />
              {t.refreshQueue}
            </Button>
          </div>
        </div>
      </Card>

      {/* Текущая очередь */}
      <Card style={{
        backgroundColor: 'var(--mac-bg-toolbar)',
        border: '1px solid var(--mac-separator)'
      }}>
        <CardContent style={{ padding: 'var(--mac-spacing-5)' }}>
          <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
              marginBottom: 'var(--mac-spacing-3)'
            }}>
              {t.currentQueue}
              {queueData && (
                <Badge variant={queueData.is_open ? 'success' : 'secondary'} style={{ marginLeft: 'var(--mac-spacing-2)' }}>
                  {queueData.is_open ? t.receptionOpen : `Откроется в ${queueData.online_start_time}`}
                </Badge>
              )}
            </h3>
          </div>

          {!effectiveDoctor ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--mac-spacing-8)',
              textAlign: 'center',
              color: 'var(--mac-text-secondary)'
            }}>
              <Icon name="magnifyingglass" size="xlarge" style={{ color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-4)' }} />
              <p>{t.selectDoctor}</p>
            </div>
          ) : !queueData ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--mac-spacing-8)',
              textAlign: 'center',
              color: 'var(--mac-text-secondary)'
            }}>
              <Icon name="magnifyingglass" size="xlarge" style={{ color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-4)' }} />
              <p>{t.queueNotFound}</p>
              <Button variant="primary" onClick={generateQR} style={{ marginTop: 'var(--mac-spacing-4)' }}>
                {t.generateQr}
              </Button>
            </div>
          ) : queueData.entries.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--mac-spacing-8)',
              textAlign: 'center',
              color: 'var(--mac-text-secondary)'
            }}>
              <Icon name="person" size="xlarge" style={{ color: 'var(--mac-text-tertiary)', marginBottom: 'var(--mac-spacing-4)' }} />
              <p>{t.queueEmpty}</p>
            </div>
          ) : (
            <div style={{
              display: 'table',
              width: '100%',
              borderCollapse: 'separate',
              borderSpacing: 0
            }}>
              <div style={{
                display: 'table-header-group'
              }}>
                <div style={{
                  display: 'table-row',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-sm)',
                  textTransform: 'uppercase'
                }}>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>№</div>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>{t.patient}</div>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>{t.phone}</div>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>{t.time}</div>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>{t.status}</div>
                  <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>{t.actions}</div>
                </div>
              </div>
              
              <div style={{ display: 'table-row-group' }}>
                {queueData.entries.map((entry) => (
                  <div
                    key={entry.id}
                    style={{
                      display: 'table-row',
                      backgroundColor: entry.status === 'called' ? 'var(--mac-accent-blue-50)' : 'transparent',
                      transition: 'background var(--mac-duration-normal)'
                    }}
                  >
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      <Badge variant={entry.status === 'called' ? 'warning' : 'primary'}>
                        {entry.number}
                      </Badge>
                    </div>
                    
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                        <Icon name="person" size="small" style={{ color: 'var(--mac-text-secondary)' }} />
                        <span style={{ color: 'var(--mac-text-primary)' }}>
                          {entry.patient_name || 'Не указано'}
                        </span>
                      </div>
                    </div>
                    
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                        <Icon name="phone" size="small" style={{ color: 'var(--mac-text-secondary)' }} />
                        <span style={{ color: 'var(--mac-text-secondary)' }}>
                          {entry.phone || 'Не указан'}
                        </span>
                      </div>
                    </div>
                    
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                        <Icon name="magnifyingglass" size="small" style={{ color: 'var(--mac-text-secondary)' }} />
                        <span style={{ color: 'var(--mac-text-secondary)' }}>
                          {formatTime(entry.created_at)}
                        </span>
                      </div>
                    </div>
                    
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      <Badge variant={entry.status === 'waiting' ? 'warning' : entry.status === 'called' ? 'primary' : entry.status === 'completed' ? 'success' : 'danger'}>
                        {getStatusText(entry.status)}
                      </Badge>
                    </div>
                    
                    <div style={{ display: 'table-cell', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', borderBottom: '1px solid var(--mac-separator)' }}>
                      {entry.status === 'waiting' && (
                        <Button
                          variant="success"
                          size="small"
                          onClick={() => callPatient(entry.id)}
                          disabled={loading}
                          title={t.call}
                        >
                          <Icon name="checkmark" size="small" style={{ color: 'white' }} />
                        </Button>
                      )}
                      {entry.status === 'called' && (
                        <Badge variant="warning">
                          {t.called}
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Диалог QR кода */}
      <ModernDialog
        isOpen={showQrDialog}
        onClose={() => setShowQrDialog(false)}
        title="QR код для онлайн-очереди"
        maxWidth="32rem"
      >
        {qrData && (
          <div>
            <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
              <p style={{ marginBottom: 'var(--mac-spacing-2)' }}>
                <strong>Специалист:</strong> {qrData.specialist_name}
              </p>
              <p style={{ marginBottom: 'var(--mac-spacing-2)' }}>
                <strong>Дата приёма:</strong> {new Date(qrData.day).toLocaleDateString('ru-RU')}
              </p>
              <p style={{ marginBottom: 'var(--mac-spacing-2)' }}>
                <strong>Окно онлайн-записи:</strong> {qrData.online_start_time} - {qrData.online_end_time}
              </p>
            </div>
            
            <div style={{
              textAlign: 'center',
              padding: 'var(--mac-spacing-5)',
              backgroundColor: 'var(--mac-bg-primary)',
              borderRadius: 'var(--mac-radius-md)',
              marginBottom: 'var(--mac-spacing-4)'
            }}>
              <QRCodeSVG
                value={`${window.location.origin}${qrData.qr_url}`}
                size={200}
                level="M"
                includeMargin={true}
              />
            </div>
            
            <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)' }}>
              <Button variant="outline" onClick={downloadQR} style={{ flex: 1 }}>
                <Icon name="square.and.arrow.up" size="small" style={{ color: 'var(--mac-text-primary)' }} />
                {t.download}
              </Button>
              <Button variant="primary" onClick={() => window.print()} style={{ flex: 1 }}>
                <Icon name="gear" size="small" style={{ color: 'white' }} />
                {t.print}
              </Button>
            </div>
          </div>
        )}
      </ModernDialog>
    </div>
  );
};

export default ModernQueueManager;
