import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  BarChart3,
  Clock,
  Download,
  Phone,
  Play,
  Printer,
  QrCode,
  RefreshCw,
  Square,
  User,
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Select,
  Tooltip,
  Typography,
} from '../ui/macos';
import Table, {
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from '../ui/macos/Table';
import { useQueueManager } from '../../hooks/useQueueManager';
import { openPrintableWindow } from '../../utils/printWindow';

const iconSize = 16;

const iconStyle = {
  width: iconSize,
  height: iconSize,
  flex: '0 0 auto',
};

const iconButtonStyle = {
  width: 32,
  height: 32,
  padding: 0,
  borderRadius: 999,
};

const panelCardStyle = {
  height: '100%',
};

const headerRowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  flexWrap: 'wrap',
  marginBottom: 16,
};

const compactRowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  minWidth: 0,
};

const actionStackStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  marginTop: 16,
};

const qrFrameStyle = {
  display: 'inline-block',
  padding: 16,
  border: '1px solid var(--mac-border)',
  borderRadius: 10,
  background: 'var(--mac-bg-primary)',
};

const statusVariantMap = {
  primary: 'primary',
  warning: 'warning',
  success: 'success',
  error: 'danger',
  default: 'outline',
};

const StatTile = ({ value, label, variant }) => (
  <div className={`online-queue-stat online-queue-stat--${variant}`}>
    <div className="online-queue-stat-value">{value}</div>
    <div className="online-queue-stat-label">{label}</div>
  </div>
);

const DismissibleAlert = ({ severity, children, onClose }) => (
  <Alert severity={severity} role="status" style={{ marginBottom: 16 }}>
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
      <span>{children}</span>
      {onClose && (
        <button
          type="button"
          className="online-queue-alert-close"
          onClick={onClose}
          aria-label="Закрыть уведомление"
        >
          ×
        </button>
      )}
    </div>
  </Alert>
);

const IconText = ({ icon: Icon, children }) => (
  <span style={compactRowStyle}>
    <Icon style={iconStyle} aria-hidden="true" />
    <span>{children}</span>
  </span>
);

StatTile.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  label: PropTypes.node,
  variant: PropTypes.string,
};

DismissibleAlert.propTypes = {
  severity: PropTypes.string,
  children: PropTypes.node,
  onClose: PropTypes.func,
};

IconText.propTypes = {
  icon: PropTypes.elementType.isRequired,
  children: PropTypes.node,
};

const OnlineQueueManager = () => {
  // Используем кастомный хук вместо прямых API вызовов
  const {
    loading,
    error,
    success,
    statistics,
    specialists,
    queueData,
    qrData,
    generateQRCode,
    loadTodayQueue,
    loadStatistics,
    openQueue,
    callPatient,
    setError,
    setSuccess,
    setQueueData,
    setStatistics
  } = useQueueManager();

  // Локальные состояния для UI
  const [qrDialog, setQrDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedSpecialist, setSelectedSpecialist] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Автообновление очереди
  useEffect(() => {
    let interval;
    if (autoRefresh && selectedSpecialist) {
      interval = setInterval(() => {
        loadTodayQueue(selectedSpecialist);
        loadStatistics(selectedSpecialist, selectedDate);
      }, 10000); // Обновляем каждые 10 секунд
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, selectedSpecialist, selectedDate, loadTodayQueue, loadStatistics]);

  // Обработчики для UI - используют методы из хука
  const handleGenerateQR = async () => {
    await generateQRCode(selectedDate, selectedSpecialist);
  };

  const handleOpenQueue = async () => {
    const success = await openQueue(selectedSpecialist);
    if (success) {
      loadTodayQueue(selectedSpecialist);
    }
  };

  const handleCallPatient = async (entryId) => {
    const success = await callPatient(entryId);
    if (success) {
      loadTodayQueue(selectedSpecialist);
    }
  };

  const handleSpecialistChange = (value) => {
    setSelectedSpecialist(value);
    setQueueData(null);
    setStatistics(null);
    // Загружаем статистику для нового специалиста
    if (value) {
      setTimeout(() => loadStatistics(), 100);
    }
  };

  const downloadQR = () => {
    if (!qrData) return;

    const svg = document.querySelector('#qr-code-svg');
    if (!svg) return;

    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);

      const link = document.createElement('a');
      link.download = `qr-queue-${selectedDate}-${qrData.specialist_name}.png`;
      link.href = canvas.toDataURL();
      link.click();
    };

    img.src = 'data:image/svg+xml;base64,' + btoa(svgData);
  };

  const handlePrintQR = () => {
    if (!qrData) return;

    const svg = document.querySelector('#qr-code-svg');
    const svgMarkup = svg?.outerHTML || '';

    openPrintableWindow({
      features: 'width=900,height=700',
      html: `
      <!doctype html>
      <html lang="ru">
        <head>
          <title>QR код для очереди</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #111827; text-align: center; }
            h1 { margin-bottom: 12px; font-size: 24px; }
            .meta { color: #4b5563; margin-top: 16px; line-height: 1.6; }
            .qr { display: inline-block; padding: 16px; border: 1px solid #d1d5db; border-radius: 12px; }
          </style>
        </head>
        <body>
          <h1>QR код для записи в очередь</h1>
          <div class="qr">${svgMarkup}</div>
          <div class="meta">
            <div><strong>Специалист:</strong> ${qrData.specialist_name || ''}</div>
            <div><strong>Дата:</strong> ${new Date(qrData.day).toLocaleDateString('ru-RU')}</div>
            <div><strong>Действует до:</strong> ${formatTime(qrData.expires_at)}</div>
            <div><strong>Ссылка:</strong> ${window.location.origin}/queue/join?token=${qrData.token}</div>
          </div>
        </body>
      </html>
    `
    });
  };

  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'waiting': return 'primary';
      case 'called': return 'warning';
      case 'completed': return 'success';
      case 'cancelled': return 'error';
      default: return 'default';
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

  const specialistOptions = specialists.map((specialist) => ({
    value: specialist.id,
    label: specialist.full_name || specialist.username,
  }));

  return (
    <div className="online-queue-manager">
      <Typography variant="h4" gutterBottom>
        Управление онлайн-очередью
      </Typography>

      {error && (
        <DismissibleAlert severity="error" onClose={() => setError('')}>
          {error}
        </DismissibleAlert>
      )}

      {success && (
        <DismissibleAlert severity="success" onClose={() => setSuccess('')}>
          {success}
        </DismissibleAlert>
      )}

      {statistics && (
        <Card style={{ marginBottom: 20 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom style={compactRowStyle}>
              <BarChart3 style={iconStyle} aria-hidden="true" />
              Статистика очереди
            </Typography>
            <div className="online-queue-stats">
              <StatTile value={statistics.total_entries} label="Всего записей" variant="primary" />
              <StatTile value={statistics.waiting} label="Ожидают" variant="warning" />
              <StatTile value={statistics.completed} label="Завершено" variant="success" />
              <StatTile value={statistics.available_slots} label="Свободных мест" variant="info" />
            </div>
          </CardContent>
        </Card>
      )}

      <div className="online-queue-layout">
        <Card style={panelCardStyle}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Панель управления
            </Typography>

            <div className="online-queue-field-stack">
              <Select
                label="Специалист"
                value={selectedSpecialist}
                onChange={handleSpecialistChange}
                options={specialistOptions}
                placeholder="Выберите специалиста"
              />

              <Input
                type="date"
                label="Дата"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            <div style={actionStackStyle}>
              <Button
                variant="primary"
                onClick={() => setQrDialog(true)}
                disabled={!selectedSpecialist || loading}
                fullWidth
              >
                <IconText icon={QrCode}>Генерировать QR код</IconText>
              </Button>

              <Button
                variant="outline"
                onClick={loadTodayQueue}
                disabled={!selectedSpecialist || loading}
                fullWidth
              >
                <IconText icon={RefreshCw}>Обновить очередь</IconText>
              </Button>

              <Button
                variant="success"
                onClick={handleOpenQueue}
                disabled={!selectedSpecialist || loading || queueData?.is_open}
                fullWidth
              >
                <IconText icon={Play}>
                  {queueData?.is_open ? 'Прием открыт' : 'Открыть прием'}
                </IconText>
              </Button>
            </div>

            <div style={{ marginTop: 16 }}>
              <Button
                variant={autoRefresh ? 'primary' : 'outline'}
                size="small"
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                <IconText icon={autoRefresh ? Square : Play}>
                  {autoRefresh ? 'Остановить' : 'Автообновление'}
                </IconText>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card style={panelCardStyle}>
          <CardContent>
            <div style={headerRowStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Typography variant="h6">
                  Текущая очередь
                </Typography>
                {queueData && (
                  <Badge variant={queueData.is_open ? 'success' : 'primary'} size="small">
                    {queueData.is_open ? 'Прием открыт' : 'Онлайн-запись'}
                  </Badge>
                )}
              </div>

              {queueData && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Badge variant="outline" size="small">
                    {`Всего: ${queueData.total_entries}`}
                  </Badge>
                  <Badge variant="primary" size="small">
                    {`Ожидают: ${queueData.waiting_entries}`}
                  </Badge>
                </div>
              )}
            </div>

            {!selectedSpecialist ? (
              <Alert severity="info">
                Выберите специалиста для просмотра очереди
              </Alert>
            ) : !queueData ? (
              <Alert severity="warning">
                Очередь не найдена. Создайте QR код для начала записи.
              </Alert>
            ) : queueData.entries.length === 0 ? (
              <Alert severity="info">
                Очередь пуста
              </Alert>
            ) : (
              <div className="online-queue-table-wrap">
                <Table aria-label="Текущая очередь">
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>№</TableHeaderCell>
                      <TableHeaderCell>Пациент</TableHeaderCell>
                      <TableHeaderCell>Телефон</TableHeaderCell>
                      <TableHeaderCell>Время записи</TableHeaderCell>
                      <TableHeaderCell>Статус</TableHeaderCell>
                      <TableHeaderCell>Действия</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {queueData.entries.map((entry, index) => (
                      <TableRow
                        key={entry.id}
                        hover
                        className={entry.status === 'called' ? 'online-queue-row-called' : ''}
                        style={{ animationDelay: `${index * 0.1}s` }}
                      >
                        <TableCell>
                          <span className={`online-queue-number ${entry.status === 'called' ? 'online-queue-number--called' : ''}`}>
                            {entry.number}
                          </span>
                        </TableCell>
                        <TableCell>
                          <IconText icon={User}>
                            <span style={{ fontWeight: 500 }}>{entry.patient_name || 'Не указано'}</span>
                          </IconText>
                        </TableCell>
                        <TableCell>
                          <IconText icon={Phone}>{entry.phone || 'Не указан'}</IconText>
                        </TableCell>
                        <TableCell>
                          <IconText icon={Clock}>{formatTime(entry.created_at)}</IconText>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={statusVariantMap[getStatusColor(entry.status)] || 'outline'}
                            size="small"
                            className={entry.status === 'called' ? 'online-queue-status-called' : ''}
                          >
                            {getStatusText(entry.status)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {entry.status === 'waiting' && (
                            <Tooltip content="Вызвать пациента">
                              <Button
                                variant="success"
                                size="small"
                                onClick={() => handleCallPatient(entry.id)}
                                disabled={loading}
                                style={iconButtonStyle}
                                aria-label="Вызвать пациента"
                              >
                                <Play style={iconStyle} aria-hidden="true" />
                              </Button>
                            </Tooltip>
                          )}
                          {entry.status === 'called' && (
                            <Badge variant="warning" size="small">
                              <IconText icon={Play}>Вызван</IconText>
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={qrDialog} onClose={() => setQrDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Генерация QR кода для онлайн-очереди</DialogTitle>
        <DialogContent>
          <div className="online-queue-field-stack">
            <Input
              type="date"
              label="Дата"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            />

            <Select
              label="Специалист"
              value={selectedSpecialist}
              onChange={setSelectedSpecialist}
              options={specialistOptions}
              placeholder="Выберите специалиста"
            />
          </div>

          {qrData && (
            <div style={{ marginTop: 24, textAlign: 'center' }}>
              <Typography variant="h6" gutterBottom>
                QR код для записи в очередь
              </Typography>

              <div style={qrFrameStyle}>
                <QRCodeSVG
                  id="qr-code-svg"
                  value={`${window.location.origin}/queue/join?token=${qrData.token}`}
                  size={200}
                  level="M"
                  includeMargin={true}
                />
              </div>

              <Typography variant="body2" color="secondary" style={{ marginTop: 8 }}>
                Специалист: {qrData.specialist_name}
                <br />
                Дата: {new Date(qrData.day).toLocaleDateString('ru-RU')}
                <br />
                Действует до: {formatTime(qrData.expires_at)}
              </Typography>

              <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                <Button variant="outline" onClick={downloadQR}>
                  <IconText icon={Download}>Скачать</IconText>
                </Button>
                <Button variant="outline" onClick={handlePrintQR}>
                  <IconText icon={Printer}>Печать</IconText>
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
        <DialogActions>
          <Button variant="outline" onClick={() => setQrDialog(false)}>
            Отмена
          </Button>
          <Button
            onClick={handleGenerateQR}
            variant="primary"
            disabled={!selectedDate || !selectedSpecialist || loading}
          >
            {loading ? <CircularProgress size="small" /> : 'Генерировать'}
          </Button>
        </DialogActions>
      </Dialog>

      <style>{`
        .online-queue-manager {
          padding: 24px;
          color: var(--mac-text-primary);
        }

        .online-queue-layout {
          display: grid;
          grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
          gap: 24px;
          align-items: stretch;
        }

        .online-queue-stats {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
        }

        .online-queue-stat {
          border-radius: var(--mac-radius-md);
          padding: 16px;
          text-align: center;
          color: #fff;
          border: 1px solid transparent;
        }

        .online-queue-stat--primary { background: var(--mac-accent-blue); }
        .online-queue-stat--warning { background: var(--mac-warning); }
        .online-queue-stat--success { background: var(--mac-success); }
        .online-queue-stat--info { background: #5ac8fa; }

        .online-queue-stat-value {
          font-size: 28px;
          line-height: 1.1;
          font-weight: 700;
        }

        .online-queue-stat-label {
          margin-top: 4px;
          font-size: 13px;
          opacity: 0.95;
        }

        .online-queue-field-stack {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .online-queue-table-wrap {
          width: 100%;
          overflow-x: auto;
          border-radius: 10px;
        }

        .online-queue-table-wrap svg {
          color: var(--mac-text-secondary);
        }

        .online-queue-number {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border-radius: 999px;
          background: var(--mac-accent-blue);
          color: #fff;
          font-weight: 700;
          font-size: 17px;
        }

        .online-queue-number--called {
          background: var(--mac-warning);
          animation: online-queue-pulse 2s infinite;
        }

        .online-queue-row-called {
          background: color-mix(in srgb, var(--mac-warning), transparent 92%);
        }

        .online-queue-status-called {
          animation: online-queue-glow 2s infinite;
        }

        .online-queue-alert-close {
          border: 0;
          background: transparent;
          color: var(--mac-text-secondary);
          cursor: pointer;
          font-size: 18px;
          line-height: 1;
          padding: 0 2px;
        }

        .online-queue-alert-close:focus-visible {
          outline: 2px solid var(--mac-accent-blue);
          outline-offset: 2px;
          border-radius: 4px;
        }

        @keyframes online-queue-pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.08); }
          100% { transform: scale(1); }
        }

        @keyframes online-queue-glow {
          0%, 100% { box-shadow: 0 0 5px rgba(255, 149, 0, 0.45); }
          50% { box-shadow: 0 0 18px rgba(255, 149, 0, 0.7); }
        }

        @media (max-width: 900px) {
          .online-queue-manager {
            padding: 16px;
          }

          .online-queue-layout {
            grid-template-columns: 1fr;
          }

          .online-queue-stats {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 520px) {
          .online-queue-stats {
            grid-template-columns: 1fr;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .online-queue-number--called,
          .online-queue-status-called {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
};

export default OnlineQueueManager;
