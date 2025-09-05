import { useState, useEffect, useCallback } from 'react';

const useSecurity = () => {
  const [securityData, setSecurityData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');

  // Моковые данные для демонстрации
  const mockSecurityData = {
    overview: {
      totalThreats: 23,
      criticalThreats: 3,
      mediumThreats: 8,
      lowThreats: 12,
      blockedIPs: 15,
      activeSessions: 8,
      failedLogins: 45,
      securityScore: 85,
      lastScan: '2024-02-10T15:30:00Z',
      nextScan: '2024-02-10T16:30:00Z'
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
        actions: ['IP заблокирован', 'Уведомление отправлено'],
        riskScore: 95
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
        actions: ['Мониторинг усилен'],
        riskScore: 60
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
        actions: ['IP заблокирован', 'Алерт отправлен', 'Логи сохранены'],
        riskScore: 98
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
        actions: ['Файл изолирован', 'Сканирование запущено'],
        riskScore: 85
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
        actions: ['Доступ ограничен', 'Расследование начато'],
        riskScore: 70
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
        details: 'Успешный вход в систему',
        sessionId: 'sess_123456'
      },
      {
        id: 2,
        action: 'Password Change',
        user: 'doctor@clinic.uz',
        ip: '192.168.1.101',
        timestamp: '2024-02-10T15:25:00Z',
        status: 'success',
        details: 'Пароль успешно изменен',
        sessionId: 'sess_123457'
      },
      {
        id: 3,
        action: 'Failed Login',
        user: 'unknown@example.com',
        ip: '203.0.113.1',
        timestamp: '2024-02-10T15:20:00Z',
        status: 'failed',
        details: 'Неверный пароль - 3 попытки',
        sessionId: null
      },
      {
        id: 4,
        action: 'Data Export',
        user: 'admin@clinic.uz',
        ip: '192.168.1.100',
        timestamp: '2024-02-10T15:15:00Z',
        status: 'success',
        details: 'Экспорт данных пациентов',
        sessionId: 'sess_123456'
      },
      {
        id: 5,
        action: 'Permission Denied',
        user: 'nurse@clinic.uz',
        ip: '192.168.1.102',
        timestamp: '2024-02-10T15:10:00Z',
        status: 'denied',
        details: 'Попытка доступа к административным функциям',
        sessionId: 'sess_123458'
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
        isCurrent: true,
        sessionId: 'sess_123456'
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
        isCurrent: false,
        sessionId: 'sess_123457'
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
        isCurrent: false,
        sessionId: 'sess_123458'
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
        status: 'active',
        country: 'Unknown',
        isp: 'Unknown'
      },
      {
        id: 2,
        ip: '198.51.100.1',
        reason: 'Data Breach Attempt',
        blockedAt: '2024-02-10T13:45:00Z',
        expiresAt: '2024-02-24T13:45:00Z',
        attempts: 3,
        status: 'active',
        country: 'Unknown',
        isp: 'Unknown'
      },
      {
        id: 3,
        ip: '192.0.2.1',
        reason: 'Suspicious Activity',
        blockedAt: '2024-02-09T16:20:00Z',
        expiresAt: '2024-02-16T16:20:00Z',
        attempts: 8,
        status: 'expired',
        country: 'Unknown',
        isp: 'Unknown'
      }
    ]
  };

  // Загрузка данных безопасности
  const loadSecurityData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setSecurityData(mockSecurityData);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Блокировка IP адреса
  const blockIP = useCallback(async (ip, reason, duration = 7) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newBlockedIP = {
        id: Date.now(),
        ip,
        reason,
        blockedAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + duration * 24 * 60 * 60 * 1000).toISOString(),
        attempts: 1,
        status: 'active',
        country: 'Unknown',
        isp: 'Unknown'
      };
      
      setSecurityData(prev => ({
        ...prev,
        blockedIPs: [newBlockedIP, ...prev.blockedIPs],
        overview: {
          ...prev.overview,
          blockedIPs: prev.overview.blockedIPs + 1
        }
      }));
      
      return newBlockedIP;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Разблокировка IP адреса
  const unblockIP = useCallback(async (ipId) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setSecurityData(prev => ({
        ...prev,
        blockedIPs: prev.blockedIPs.filter(ip => ip.id !== ipId),
        overview: {
          ...prev.overview,
          blockedIPs: Math.max(0, prev.overview.blockedIPs - 1)
        }
      }));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Завершение сессии
  const terminateSession = useCallback(async (sessionId) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setSecurityData(prev => ({
        ...prev,
        sessions: prev.sessions.filter(session => session.id !== sessionId),
        overview: {
          ...prev.overview,
          activeSessions: Math.max(0, prev.overview.activeSessions - 1)
        }
      }));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Завершение всех других сессий
  const terminateAllOtherSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setSecurityData(prev => ({
        ...prev,
        sessions: prev.sessions.filter(session => session.isCurrent),
        overview: {
          ...prev.overview,
          activeSessions: 1
        }
      }));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление статуса угрозы
  const updateThreatStatus = useCallback(async (threatId, newStatus) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setSecurityData(prev => ({
        ...prev,
        threats: prev.threats.map(threat => 
          threat.id === threatId 
            ? { ...threat, status: newStatus }
            : threat
        )
      }));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация данных
  const filteredThreats = securityData.threats?.filter(threat => {
    const matchesSearch = !searchTerm || 
      threat.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      threat.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      threat.source.toLowerCase().includes(searchTerm.toLowerCase()) ||
      threat.target.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = !filterStatus || threat.status === filterStatus;
    const matchesSeverity = !filterSeverity || threat.severity === filterSeverity;
    
    const matchesDateRange = !filterDateRange || (() => {
      const threatDate = new Date(threat.timestamp);
      const today = new Date();
      
      switch (filterDateRange) {
        case 'today':
          return threatDate.toDateString() === today.toDateString();
        case 'week':
          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
          return threatDate >= weekAgo;
        case 'month':
          const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
          return threatDate >= monthAgo;
        default:
          return true;
      }
    })();
    
    return matchesSearch && matchesStatus && matchesSeverity && matchesDateRange;
  }) || [];

  const filteredLogs = securityData.logs?.filter(log => {
    const matchesSearch = !searchTerm || 
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.details.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.ip.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = !filterStatus || log.status === filterStatus;
    
    const matchesDateRange = !filterDateRange || (() => {
      const logDate = new Date(log.timestamp);
      const today = new Date();
      
      switch (filterDateRange) {
        case 'today':
          return logDate.toDateString() === today.toDateString();
        case 'week':
          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
          return logDate >= weekAgo;
        case 'month':
          const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
          return logDate >= monthAgo;
        default:
          return true;
      }
    })();
    
    return matchesSearch && matchesStatus && matchesDateRange;
  }) || [];

  // Получение статистики безопасности
  const getSecurityStats = () => {
    const stats = {
      totalThreats: securityData.overview?.totalThreats || 0,
      criticalThreats: securityData.overview?.criticalThreats || 0,
      mediumThreats: securityData.overview?.mediumThreats || 0,
      lowThreats: securityData.overview?.lowThreats || 0,
      blockedIPs: securityData.overview?.blockedIPs || 0,
      activeSessions: securityData.overview?.activeSessions || 0,
      failedLogins: securityData.overview?.failedLogins || 0,
      securityScore: securityData.overview?.securityScore || 0
    };
    
    return stats;
  };

  // Получение трендов безопасности
  const getSecurityTrends = () => {
    const trends = {
      threats: {
        current: securityData.overview?.totalThreats || 0,
        previous: 18,
        change: ((securityData.overview?.totalThreats || 0) - 18) / 18 * 100
      },
      blockedIPs: {
        current: securityData.overview?.blockedIPs || 0,
        previous: 12,
        change: ((securityData.overview?.blockedIPs || 0) - 12) / 12 * 100
      },
      securityScore: {
        current: securityData.overview?.securityScore || 0,
        previous: 82,
        change: ((securityData.overview?.securityScore || 0) - 82) / 82 * 100
      }
    };
    
    return trends;
  };

  // Экспорт логов безопасности
  const exportSecurityLogs = useCallback(async (format = 'json') => {
    try {
      const logsData = filteredLogs;
      let content, mimeType, extension;
      
      if (format === 'json') {
        content = JSON.stringify(logsData, null, 2);
        mimeType = 'application/json';
        extension = 'json';
      } else if (format === 'csv') {
        const headers = ['ID', 'Action', 'User', 'IP', 'Timestamp', 'Status', 'Details'];
        const csvContent = [
          headers.join(','),
          ...logsData.map(log => [
            log.id,
            `"${log.action}"`,
            `"${log.user}"`,
            `"${log.ip}"`,
            `"${log.timestamp}"`,
            `"${log.status}"`,
            `"${log.details}"`
          ].join(','))
        ].join('\n');
        content = csvContent;
        mimeType = 'text/csv';
        extension = 'csv';
      }
      
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `security-logs-${new Date().toISOString().split('T')[0]}.${extension}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [filteredLogs]);

  // Загрузка при монтировании
  useEffect(() => {
    loadSecurityData();
  }, [loadSecurityData]);

  return {
    securityData,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterStatus,
    setFilterStatus,
    filterSeverity,
    setFilterSeverity,
    filterDateRange,
    setFilterDateRange,
    filteredThreats,
    filteredLogs,
    loadSecurityData,
    blockIP,
    unblockIP,
    terminateSession,
    terminateAllOtherSessions,
    updateThreatStatus,
    exportSecurityLogs,
    refresh: loadSecurityData,
    getSecurityStats,
    getSecurityTrends
  };
};

export default useSecurity;
