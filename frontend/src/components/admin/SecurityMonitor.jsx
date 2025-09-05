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
import { Card, Button, Badge } from '../../design-system/components';

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
      critical: 'var(--danger-color)',
      high: 'var(--warning-color)',
      medium: 'var(--info-color)',
      low: 'var(--success-color)'
    };
    return colorMap[severity] || 'var(--text-secondary)';
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
      success: 'var(--success-color)',
      failed: 'var(--danger-color)',
      blocked: 'var(--danger-color)',
      monitoring: 'var(--info-color)',
      investigating: 'var(--warning-color)',
      quarantined: 'var(--warning-color)',
      denied: 'var(--danger-color)',
      active: 'var(--success-color)',
      idle: 'var(--warning-color)',
      expired: 'var(--text-tertiary)'
    };
    return colorMap[status] || 'var(--text-secondary)';
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
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-4">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-gray-200 rounded w-1/2"></div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Вкладки */}
      <div className="border-b" style={{ borderColor: 'var(--border-color)' }}>
        <nav className="flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
                style={{
                  borderBottomColor: activeTab === tab.id ? 'var(--accent-color)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--accent-color)' : 'var(--text-secondary)'
                }}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Обзор безопасности */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Статистика */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Всего угроз</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{currentData.totalThreats}</p>
                </div>
                <AlertTriangle className="w-8 h-8" style={{ color: 'var(--warning-color)' }} />
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Критические</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--danger-color)' }}>{currentData.criticalThreats}</p>
                </div>
                <XCircle className="w-8 h-8" style={{ color: 'var(--danger-color)' }} />
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Заблокированные IP</p>
                  <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{currentData.blockedIPs}</p>
                </div>
                <Globe className="w-8 h-8" style={{ color: 'var(--info-color)' }} />
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Оценка безопасности</p>
                  <p className="text-2xl font-bold" style={{ color: currentData.securityScore >= 80 ? 'var(--success-color)' : 'var(--warning-color)' }}>
                    {currentData.securityScore}%
                  </p>
                </div>
                <Shield className="w-8 h-8" style={{ color: currentData.securityScore >= 80 ? 'var(--success-color)' : 'var(--warning-color)' }} />
              </div>
            </Card>
          </div>

          {/* Последние угрозы */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Последние угрозы
            </h3>
            <div className="space-y-3">
              {threats.slice(0, 5).map((threat) => {
                const SeverityIcon = getSeverityIcon(threat.severity);
                return (
                  <div key={threat.id} className="flex items-center justify-between p-3 rounded-lg border" 
                       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                    <div className="flex items-center space-x-3">
                      <SeverityIcon className="w-5 h-5" style={{ color: getSeverityColor(threat.severity) }} />
                      <div>
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{threat.type}</p>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{threat.description}</p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          {threat.source} • {getTimeAgo(threat.timestamp)}
                        </p>
                      </div>
                    </div>
                    <Badge variant={threat.severity === 'critical' ? 'error' : threat.severity === 'high' ? 'warning' : 'info'}>
                      {getSeverityLabel(threat.severity)}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}

      {/* Угрозы */}
      {activeTab === 'threats' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                Угрозы безопасности
              </h3>
              <Button onClick={onRefresh}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Обновить
              </Button>
            </div>
            
            <div className="space-y-3">
              {threats.map((threat) => {
                const SeverityIcon = getSeverityIcon(threat.severity);
                const StatusIcon = getStatusIcon(threat.status);
                return (
                  <div key={threat.id} className="p-4 rounded-lg border" 
                       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        <SeverityIcon className="w-6 h-6 mt-1" style={{ color: getSeverityColor(threat.severity) }} />
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <h4 className="font-medium" style={{ color: 'var(--text-primary)' }}>{threat.type}</h4>
                            <Badge variant={threat.severity === 'critical' ? 'error' : threat.severity === 'high' ? 'warning' : 'info'}>
                              {getSeverityLabel(threat.severity)}
                            </Badge>
                            <Badge variant={threat.status === 'blocked' ? 'success' : 'warning'}>
                              {getStatusLabel(threat.status)}
                            </Badge>
                          </div>
                          <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>{threat.description}</p>
                          <div className="text-xs space-y-1" style={{ color: 'var(--text-tertiary)' }}>
                            <p>Источник: {threat.source}</p>
                            <p>Цель: {threat.target}</p>
                            <p>Время: {formatDateTime(threat.timestamp)}</p>
                          </div>
                          {threat.actions && threat.actions.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Действия:</p>
                              <div className="flex flex-wrap gap-1">
                                {threat.actions.map((action, index) => (
                                  <Badge key={index} variant="secondary" className="text-xs">
                                    {action}
                                  </Badge>
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
          </Card>
        </div>
      )}

      {/* Логи безопасности */}
      {activeTab === 'logs' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                Логи безопасности
              </h3>
              <div className="flex items-center space-x-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    placeholder="Поиск в логах..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-64 pl-10 pr-3 py-2 rounded-lg border text-sm"
                    style={{ 
                      border: '1px solid var(--border-color)', 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)' 
                    }}
                  />
                </div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-3 py-2 rounded-lg border text-sm"
                  style={{ 
                    border: '1px solid var(--border-color)', 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)' 
                  }}
                >
                  <option value="">Все статусы</option>
                  <option value="success">Успешно</option>
                  <option value="failed">Ошибка</option>
                  <option value="denied">Отклонено</option>
                </select>
              </div>
            </div>
            
            <div className="space-y-2">
              {logs.map((log) => {
                const StatusIcon = getStatusIcon(log.status);
                return (
                  <div key={log.id} className="flex items-center justify-between p-3 rounded-lg border" 
                       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                    <div className="flex items-center space-x-3">
                      <StatusIcon className="w-5 h-5" style={{ color: getStatusColor(log.status) }} />
                      <div>
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{log.action}</p>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{log.details}</p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          {log.user} • {log.ip} • {getTimeAgo(log.timestamp)}
                        </p>
                      </div>
                    </div>
                    <Badge variant={log.status === 'success' ? 'success' : log.status === 'failed' ? 'error' : 'warning'}>
                      {getStatusLabel(log.status)}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}

      {/* Активные сессии */}
      {activeTab === 'sessions' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Активные сессии
            </h3>
            
            <div className="space-y-3">
              {sessions.map((session) => {
                const StatusIcon = getStatusIcon(session.status);
                return (
                  <div key={session.id} className="flex items-center justify-between p-4 rounded-lg border" 
                       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                    <div className="flex items-center space-x-4">
                      <div className="w-10 h-10 rounded-full flex items-center justify-center" 
                           style={{ background: 'var(--accent-color)' }}>
                        <User className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                          {session.user}
                          {session.isCurrent && (
                            <Badge variant="success" className="ml-2">Текущая</Badge>
                          )}
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {session.device} • {session.location}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          IP: {session.ip} • Последняя активность: {getTimeAgo(session.lastActivity)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Badge variant={session.status === 'active' ? 'success' : session.status === 'idle' ? 'warning' : 'secondary'}>
                        {getStatusLabel(session.status)}
                      </Badge>
                      {!session.isCurrent && (
                        <Button variant="outline" size="sm">
                          <XCircle className="w-4 h-4 mr-1" />
                          Завершить
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}

      {/* Заблокированные IP */}
      {activeTab === 'blocked' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Заблокированные IP адреса
            </h3>
            
            <div className="space-y-3">
              {blockedIPs.map((blocked) => (
                <div key={blocked.id} className="flex items-center justify-between p-4 rounded-lg border" 
                     style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                  <div className="flex items-center space-x-4">
                    <Globe className="w-6 h-6" style={{ color: 'var(--danger-color)' }} />
                    <div>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{blocked.ip}</p>
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{blocked.reason}</p>
                      <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                        Заблокирован: {formatDateTime(blocked.blockedAt)} • 
                        Попыток: {blocked.attempts} • 
                        Истекает: {formatDateTime(blocked.expiresAt)}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Badge variant={blocked.status === 'active' ? 'error' : 'secondary'}>
                      {blocked.status === 'active' ? 'Активен' : 'Истек'}
                    </Badge>
                    <Button variant="outline" size="sm">
                      <Eye className="w-4 h-4 mr-1" />
                      Подробнее
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default SecurityMonitor;
