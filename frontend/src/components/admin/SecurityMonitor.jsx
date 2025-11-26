import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Eye, 
  EyeOff, 
  RefreshCw,
  Download,
  Filter,
  Search,
  Calendar,
  Clock,
  User,
  Globe,
  Lock,
  Key,
  Activity,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import { MacOSCard, MacOSButton, MacOSBadge, MacOSInput, MacOSSelect, MacOSTab } from '../ui/macos';

const SecurityMonitor = ({ 
  data = {},
  loading = false,
  onRefresh
}) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');

  // Моковые данные для демонстрации
  const mockData = {
    overview: {
      totalThreats: 23,
      criticalThreats: 3,
      mediumThreats: 8,
      lowThreats: 12,
      blockedIPs: 15,
      activeSessions: 8,
      failedLogins: 45,
      securityScore: 85
    },
    threats: [
      {
        id: 1,
        type: 'Brute Force Attack',
        severity: 'critical',
        source: '203.0.113.1',
        target: 'admin@clinic.uz',
        timestamp: '2024-02-10T15:30:00Z',
        status: 'blocked',
        description: 'Множественные неудачные попытки входа',
        actions: ['IP заблокирован', 'Уведомление отправлено']
      },
      {
        id: 2,
        type: 'Suspicious Activity',
        severity: 'medium',
        source: '192.168.1.105',
        target: 'user@clinic.uz',
        timestamp: '2024-02-10T14:15:00Z',
        status: 'monitoring',
        description: 'Необычная активность в нерабочее время',
        actions: ['Мониторинг усилен']
      },
      {
        id: 3,
        type: 'Data Breach Attempt',
        severity: 'critical',
        source: '198.51.100.1',
        target: 'database',
        timestamp: '2024-02-10T13:45:00Z',
        status: 'blocked',
        description: 'Попытка несанкционированного доступа к базе данных',
        actions: ['IP заблокирован', 'Алерт отправлен', 'Логи сохранены']
      },
      {
        id: 4,
        type: 'Malware Detection',
        severity: 'high',
        source: '192.168.1.200',
        target: 'workstation-03',
        timestamp: '2024-02-10T12:30:00Z',
        status: 'quarantined',
        description: 'Обнаружен подозрительный файл',
        actions: ['Файл изолирован', 'Сканирование запущено']
      },
      {
        id: 5,
        type: 'Unauthorized Access',
        severity: 'medium',
        source: '10.0.0.50',
        target: 'patient-records',
        timestamp: '2024-02-10T11:20:00Z',
        status: 'investigating',
        description: 'Попытка доступа к медицинским записям',
        actions: ['Доступ ограничен', 'Расследование начато']
      }
    ],
    logs: [
      {
        id: 1,
        action: 'Login Success',
        user: 'admin@clinic.uz',
        ip: '192.168.1.100',
        timestamp: '2024-02-10T15:30:00Z',
        status: 'success',
        details: 'Успешный вход в систему'
      },
      {
        id: 2,
        action: 'Password Change',
        user: 'doctor@clinic.uz',
        ip: '192.168.1.101',
        timestamp: '2024-02-10T15:25:00Z',
        status: 'success',
        details: 'Пароль успешно изменен'
      },
      {
        id: 3,
        action: 'Failed Login',
        user: 'unknown@example.com',
        ip: '203.0.113.1',
        timestamp: '2024-02-10T15:20:00Z',
        status: 'failed',
        details: 'Неверный пароль - 3 попытки'
      },
      {
        id: 4,
        action: 'Data Export',
        user: 'admin@clinic.uz',
        ip: '192.168.1.100',
        timestamp: '2024-02-10T15:15:00Z',
        status: 'success',
        details: 'Экспорт данных пациентов'
      },
      {
        id: 5,
        action: 'Permission Denied',
        user: 'nurse@clinic.uz',
        ip: '192.168.1.102',
        timestamp: '2024-02-10T15:10:00Z',
        status: 'denied',
        details: 'Попытка доступа к административным функциям'
      }
    ],
    sessions: [
      {
        id: 1,
        user: 'admin@clinic.uz',
        device: 'Chrome на Windows',
        location: 'Ташкент, Узбекистан',
        ip: '192.168.1.100',
        loginTime: '2024-02-10T09:00:00Z',
        lastActivity: '2024-02-10T15:30:00Z',
        status: 'active',
        isCurrent: true
      },
      {
        id: 2,
        user: 'doctor@clinic.uz',
        device: 'Safari на iPhone',
        location: 'Ташкент, Узбекистан',
        ip: '192.168.1.101',
        loginTime: '2024-02-10T08:30:00Z',
        lastActivity: '2024-02-10T14:45:00Z',
        status: 'idle',
        isCurrent: false
      },
      {
        id: 3,
        user: 'nurse@clinic.uz',
        device: 'Firefox на Mac',
        location: 'Самарканд, Узбекистан',
        ip: '10.0.0.50',
        loginTime: '2024-02-10T10:15:00Z',
        lastActivity: '2024-02-10T13:20:00Z',
        status: 'expired',
        isCurrent: false
      }
    ],
    blockedIPs: [
      {
        id: 1,
        ip: '203.0.113.1',
        reason: 'Brute Force Attack',
        blockedAt: '2024-02-10T15:30:00Z',
        expiresAt: '2024-02-17T15:30:00Z',
        attempts: 15,
        status: 'active'
      },
      {
        id: 2,
        ip: '198.51.100.1',
        reason: 'Data Breach Attempt',
        blockedAt: '2024-02-10T13:45:00Z',
        expiresAt: '2024-02-24T13:45:00Z',
        attempts: 3,
        status: 'active'
      },
      {
        id: 3,
        ip: '192.0.2.1',
        reason: 'Suspicious Activity',
        blockedAt: '2024-02-09T16:20:00Z',
        expiresAt: '2024-02-16T16:20:00Z',
        attempts: 8,
        status: 'expired'
      }
    ]
  };

  const currentData = data.overview || mockData.overview;
  const threats = data.threats || mockData.threats;
  const logs = data.logs || mockData.logs;
  const sessions = data.sessions || mockData.sessions;
  const blockedIPs = data.blockedIPs || mockData.blockedIPs;

  const getSeverityIcon = (severity) => {
    const iconMap = {
      critical: XCircle,
      high: AlertTriangle,
      medium: AlertTriangle,
      low: CheckCircle
    };
    return iconMap[severity] || AlertTriangle;
  };

  const getSeverityColor = (severity) => {
    const colorMap = {
      critical: 'var(--mac-danger)',
      high: 'var(--mac-warning)',
      medium: 'var(--mac-info)',
      low: 'var(--mac-success)'
    };
    return colorMap[severity] || 'var(--mac-text-secondary)';
  };

  const getSeverityLabel = (severity) => {
    const labelMap = {
      critical: 'Критический',
      high: 'Высокий',
      medium: 'Средний',
      low: 'Низкий'
    };
    return labelMap[severity] || severity;
  };

  const getStatusIcon = (status) => {
    const iconMap = {
      success: CheckCircle,
      failed: XCircle,
      blocked: XCircle,
      monitoring: Eye,
      investigating: Search,
      quarantined: Lock,
      denied: XCircle,
      active: CheckCircle,
      idle: Clock,
      expired: XCircle
    };
    return iconMap[status] || AlertTriangle;
  };

  const getStatusColor = (status) => {
    const colorMap = {
      success: 'var(--mac-success)',
      failed: 'var(--mac-danger)',
      blocked: 'var(--mac-danger)',
      monitoring: 'var(--mac-info)',
      investigating: 'var(--mac-warning)',
      quarantined: 'var(--mac-warning)',
      denied: 'var(--mac-danger)',
      active: 'var(--mac-success)',
      idle: 'var(--mac-warning)',
      expired: 'var(--mac-text-tertiary)'
    };
    return colorMap[status] || 'var(--mac-text-secondary)';
  };

  const getStatusLabel = (status) => {
    const labelMap = {
      success: 'Успешно',
      failed: 'Ошибка',
      blocked: 'Заблокировано',
      monitoring: 'Мониторинг',
      investigating: 'Расследование',
      quarantined: 'Изолировано',
      denied: 'Отклонено',
      active: 'Активна',
      idle: 'Неактивна',
      expired: 'Истекла'
    };
    return labelMap[status] || status;
  };

  const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getTimeAgo = (dateString) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Только что';
    if (diffInMinutes < 60) return `${diffInMinutes} мин назад`;
    
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours} ч назад`;
    
    const diffInDays = Math.floor(diffInHours / 24);
    return `${diffInDays} дн назад`;
  };

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Shield },
    { id: 'threats', label: 'Угрозы', icon: AlertTriangle },
    { id: 'logs', label: 'Логи', icon: Activity },
    { id: 'sessions', label: 'Сессии', icon: User },
    { id: 'blocked', label: 'Заблокированные IP', icon: Globe }
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          {[...Array(4)].map((_, i) => (
            <MacOSCard key={i} style={{ padding: '16px' }}>
              <div style={{ 
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-sm)',
                height: '16px',
                width: '75%',
                marginBottom: '8px'
              }}></div>
              <div style={{ 
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-sm)',
                height: '32px',
                width: '50%'
              }}></div>
            </MacOSCard>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Вкладки */}
      <div style={{ display: 'flex', marginBottom: '24px' }}>
          {tabs.map((tab) => {
            const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                padding: '12px 20px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                position: 'relative',
                marginBottom: '-1px'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-secondary)';
                }
              }}
            >
              <Icon style={{ 
                width: '16px', 
                height: '16px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
              }} />
              {tab.label}
              {isActive && (
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  borderRadius: '2px 2px 0 0'
                }} />
              )}
              </button>
            );
          })}
      </div>
      
      {/* Разделительная линия */}
      <div style={{ 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }} />

      {/* Обзор безопасности */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Статистика */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px' 
          }}>
            <MacOSCard style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>Всего угроз</p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-2xl)', 
                    fontWeight: 'var(--mac-font-weight-bold)', 
                    color: 'var(--mac-text-primary)',
                    margin: '4px 0 0 0'
                  }}>{currentData.totalThreats}</p>
                </div>
                <AlertTriangle style={{ 
                  width: '32px', 
                  height: '32px', 
                  color: 'var(--mac-warning)' 
                }} />
              </div>
            </MacOSCard>

            <MacOSCard style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>Критические</p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-2xl)', 
                    fontWeight: 'var(--mac-font-weight-bold)', 
                    color: 'var(--mac-danger)',
                    margin: '4px 0 0 0'
                  }}>{currentData.criticalThreats}</p>
                </div>
                <XCircle style={{ 
                  width: '32px', 
                  height: '32px', 
                  color: 'var(--mac-danger)' 
                }} />
              </div>
            </MacOSCard>

            <MacOSCard style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>Заблокированные IP</p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-2xl)', 
                    fontWeight: 'var(--mac-font-weight-bold)', 
                    color: 'var(--mac-text-primary)',
                    margin: '4px 0 0 0'
                  }}>{currentData.blockedIPs}</p>
                </div>
                <Globe style={{ 
                  width: '32px', 
                  height: '32px', 
                  color: 'var(--mac-info)' 
                }} />
              </div>
            </MacOSCard>

            <MacOSCard style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>Оценка безопасности</p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-2xl)', 
                    fontWeight: 'var(--mac-font-weight-bold)', 
                    color: currentData.securityScore >= 80 ? 'var(--mac-success)' : 'var(--mac-warning)',
                    margin: '4px 0 0 0'
                  }}>
                    {currentData.securityScore}%
                  </p>
                </div>
                <Shield style={{ 
                  width: '32px', 
                  height: '32px', 
                  color: currentData.securityScore >= 80 ? 'var(--mac-success)' : 'var(--mac-warning)' 
                }} />
              </div>
            </MacOSCard>
          </div>

          {/* Последние угрозы */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '16px',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Последние угрозы
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {threats.slice(0, 5).map((threat) => {
                const SeverityIcon = getSeverityIcon(threat.severity);
                return (
                  <div key={threat.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '12px', 
                    borderRadius: 'var(--mac-radius-md)', 
                    border: '1px solid var(--mac-border)', 
                    backgroundColor: 'var(--mac-bg-secondary)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <SeverityIcon style={{ 
                        width: '20px', 
                        height: '20px', 
                        color: getSeverityColor(threat.severity) 
                      }} />
                      <div>
                        <p style={{ 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          color: 'var(--mac-text-primary)',
                          margin: 0
                        }}>{threat.type}</p>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          color: 'var(--mac-text-secondary)',
                          margin: '4px 0 0 0'
                        }}>{threat.description}</p>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-xs)', 
                          color: 'var(--mac-text-tertiary)',
                          margin: '4px 0 0 0'
                        }}>
                          {threat.source} • {getTimeAgo(threat.timestamp)}
                        </p>
                      </div>
                    </div>
                    <MacOSBadge variant={threat.severity === 'critical' ? 'error' : threat.severity === 'high' ? 'warning' : 'info'}>
                      {getSeverityLabel(threat.severity)}
                    </MacOSBadge>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Угрозы */}
      {activeTab === 'threats' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                Угрозы безопасности
              </h3>
              <MacOSButton onClick={onRefresh}>
                <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Обновить
              </MacOSButton>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {threats.map((threat) => {
                const SeverityIcon = getSeverityIcon(threat.severity);
                const StatusIcon = getStatusIcon(threat.status);
                return (
                  <div key={threat.id} style={{ 
                    padding: '16px', 
                    borderRadius: 'var(--mac-radius-md)', 
                    border: '1px solid var(--mac-border)', 
                    backgroundColor: 'var(--mac-bg-secondary)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                        <SeverityIcon style={{ 
                          width: '24px', 
                          height: '24px', 
                          marginTop: '4px', 
                          color: getSeverityColor(threat.severity) 
                        }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                            <h4 style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>{threat.type}</h4>
                            <MacOSBadge variant={threat.severity === 'critical' ? 'error' : threat.severity === 'high' ? 'warning' : 'info'}>
                              {getSeverityLabel(threat.severity)}
                            </MacOSBadge>
                            <MacOSBadge variant={threat.status === 'blocked' ? 'success' : 'warning'}>
                              {getStatusLabel(threat.status)}
                            </MacOSBadge>
                          </div>
                          <p style={{ fontSize: 'var(--mac-font-size-sm)', marginBottom: '8px', color: 'var(--mac-text-secondary)', margin: '0 0 8px 0' }}>{threat.description}</p>
                          <div style={{ fontSize: 'var(--mac-font-size-xs)', display: 'flex', flexDirection: 'column', gap: '4px', color: 'var(--mac-text-tertiary)' }}>
                            <p>Источник: {threat.source}</p>
                            <p>Цель: {threat.target}</p>
                            <p>Время: {formatDateTime(threat.timestamp)}</p>
                          </div>
                          {threat.actions && threat.actions.length > 0 && (
                            <div style={{ marginTop: '8px' }}>
                              <p style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-medium)', marginBottom: '4px', color: 'var(--mac-text-secondary)', margin: '0 0 4px 0' }}>Действия:</p>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {threat.actions.map((action, index) => (
                                  <MacOSBadge key={index} variant="secondary" style={{ fontSize: '12px' }}>
                                    {action}
                                  </MacOSBadge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Логи безопасности */}
      {activeTab === 'logs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                Логи безопасности
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ position: 'relative' }}>
                  <Search style={{ 
                    position: 'absolute', 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)', 
                    width: '16px', 
                    height: '16px', 
                    color: 'var(--mac-text-tertiary)' 
                  }} />
                  <MacOSInput
                    type="text"
                    placeholder="Поиск в логах..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{ 
                      width: '256px',
                      paddingLeft: '40px',
                      paddingRight: '12px',
                      paddingTop: '8px',
                      paddingBottom: '8px'
                    }}
                  />
                </div>
                <MacOSSelect
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  options={[
                    { value: '', label: 'Все статусы' },
                    { value: 'success', label: 'Успешно' },
                    { value: 'failed', label: 'Ошибка' },
                    { value: 'denied', label: 'Отклонено' }
                  ]}
                  style={{ 
                    padding: '8px 12px',
                    minWidth: '120px'
                  }}
                />
              </div>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {logs.map((log) => {
                const StatusIcon = getStatusIcon(log.status);
                return (
                  <div key={log.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '12px', 
                    borderRadius: 'var(--mac-radius-md)', 
                    border: '1px solid var(--mac-border)', 
                    backgroundColor: 'var(--mac-bg-secondary)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <StatusIcon style={{ 
                        width: '20px', 
                        height: '20px', 
                        color: getStatusColor(log.status) 
                      }} />
                      <div>
                        <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>{log.action}</p>
                        <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>{log.details}</p>
                        <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                          {log.user} • {log.ip} • {getTimeAgo(log.timestamp)}
                        </p>
                      </div>
                    </div>
                    <MacOSBadge variant={log.status === 'success' ? 'success' : log.status === 'failed' ? 'error' : 'warning'}>
                      {getStatusLabel(log.status)}
                    </MacOSBadge>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Активные сессии */}
      {activeTab === 'sessions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '16px',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Активные сессии
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {sessions.map((session) => {
                const StatusIcon = getStatusIcon(session.status);
                return (
                  <div key={session.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '16px', 
                    borderRadius: 'var(--mac-radius-md)', 
                    border: '1px solid var(--mac-border)', 
                    backgroundColor: 'var(--mac-bg-secondary)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div style={{ 
                        width: '40px', 
                        height: '40px', 
                        borderRadius: '50%', 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        background: 'var(--mac-accent-blue)' 
                      }}>
                        <User style={{ width: '20px', height: '20px', color: 'white' }} />
                      </div>
                      <div>
                        <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>
                          {session.user}
                          {session.isCurrent && (
                            <MacOSBadge variant="success" style={{ marginLeft: '8px' }}>Текущая</MacOSBadge>
                          )}
                        </p>
                        <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>
                          {session.device} • {session.location}
                        </p>
                        <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                          IP: {session.ip} • Последняя активность: {getTimeAgo(session.lastActivity)}
                        </p>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <MacOSBadge variant={session.status === 'active' ? 'success' : session.status === 'idle' ? 'warning' : 'secondary'}>
                        {getStatusLabel(session.status)}
                      </MacOSBadge>
                      {!session.isCurrent && (
                        <MacOSButton variant="outline" size="sm">
                          <XCircle style={{ width: '16px', height: '16px', marginRight: '4px' }} />
                          Завершить
                        </MacOSButton>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Заблокированные IP */}
      {activeTab === 'blocked' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '16px',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Заблокированные IP адреса
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {blockedIPs.map((blocked) => (
                <div key={blocked.id} style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between', 
                  padding: '16px', 
                  borderRadius: 'var(--mac-radius-md)', 
                  border: '1px solid var(--mac-border)', 
                  backgroundColor: 'var(--mac-bg-secondary)' 
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <Globe style={{ width: '24px', height: '24px', color: 'var(--mac-danger)' }} />
                    <div>
                      <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>{blocked.ip}</p>
                      <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>{blocked.reason}</p>
                      <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                        Заблокирован: {formatDateTime(blocked.blockedAt)} • 
                        Попыток: {blocked.attempts} • 
                        Истекает: {formatDateTime(blocked.expiresAt)}
                      </p>
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MacOSBadge variant={blocked.status === 'active' ? 'error' : 'secondary'}>
                      {blocked.status === 'active' ? 'Активен' : 'Истек'}
                    </MacOSBadge>
                    <MacOSButton variant="outline" size="sm">
                      <Eye style={{ width: '16px', height: '16px', marginRight: '4px' }} />
                      Подробнее
                    </MacOSButton>
                  </div>
                </div>
              ))}
            </div>
          </MacOSCard>
        </div>
      )}
    </div>
  );
};

export default SecurityMonitor;

