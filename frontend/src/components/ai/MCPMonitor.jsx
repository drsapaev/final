import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Progress,
  Badge,
  Alert,
  Button,
  CircularProgress,
} from '../ui/macos';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Zap,
  HardDrive,
  Brain,
  Clock,
  Settings,
} from 'lucide-react';
import { mcpAPI } from '../../api/mcpClient';
import { useSnackbar } from 'notistack';

import logger from '../../utils/logger';
const MCPMonitor = () => {
  const [loading, setLoading] = useState(true);
  const [mcpStatus, setMcpStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [capabilities, setCapabilities] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const { enqueueSnackbar } = useSnackbar();

  const fetchMCPStatus = async () => {
    try {
      setLoading(true);
      
      // Параллельно загружаем все данные
      const [statusData, metricsData, capabilitiesData] = await Promise.all([
        mcpAPI.getStatus(),
        mcpAPI.getMetrics(),
        mcpAPI.getCapabilities()
      ]);
      
      setMcpStatus(statusData);
      setMetrics(metricsData);
      setCapabilities(capabilitiesData);
      
    } catch (error) {
      enqueueSnackbar('Ошибка загрузки статуса MCP', { variant: 'error' });
      logger.error('MCP status error:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMCPStatus();
    
    // Авто-обновление каждые 30 секунд если включено
    if (autoRefresh) {
      const interval = setInterval(fetchMCPStatus, 30000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getHealthColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'unhealthy': return 'error';
      default: return 'default';
    }
  };

  const getHealthIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle color="success" />;
      case 'degraded': return <Warning color="warning" />;
      case 'unhealthy': return <Error color="error" />;
      default: return null;
    }
  };

  const formatUptime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const diff = Date.now() - new Date(timestamp).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}ч ${minutes}м`;
  };

  const calculateSuccessRate = () => {
    if (!metrics) return 0;
    const total = metrics.requests_total || 0;
    const success = metrics.requests_success || 0;
    return total > 0 ? ((success / total) * 100).toFixed(1) : 0;
  };

  if (loading && !mcpStatus) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Заголовок */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Psychology color="primary" sx={{ fontSize: 32 }} />
            <Typography variant="h5" fontWeight="bold">
              MCP Мониторинг
            </Typography>
            {mcpStatus && (
              <Chip
                label={mcpStatus.healthy ? 'Активен' : 'Неактивен'}
                color={mcpStatus.healthy ? 'success' : 'error'}
                size="small"
              />
            )}
          </Box>
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Авто-обновление">
              <IconButton 
                onClick={() => setAutoRefresh(!autoRefresh)}
                color={autoRefresh ? 'primary' : 'default'}
              >
                <Timeline />
              </IconButton>
            </Tooltip>
            <Tooltip title="Обновить">
              <IconButton onClick={fetchMCPStatus} disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Paper>

      {/* Общие метрики */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Speed color="primary" />
                <Typography variant="subtitle2" color="text.secondary">
                  Всего запросов
                </Typography>
              </Box>
              <Typography variant="h4">
                {metrics?.requests_total || 0}
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={100} 
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <CheckCircle color="success" />
                <Typography variant="subtitle2" color="text.secondary">
                  Успешность
                </Typography>
              </Box>
              <Typography variant="h4">
                {calculateSuccessRate()}%
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={calculateSuccessRate()} 
                color="success"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Error color="error" />
                <Typography variant="subtitle2" color="text.secondary">
                  Ошибки
                </Typography>
              </Box>
              <Typography variant="h4">
                {metrics?.requests_failed || 0}
              </Typography>
              <LinearProgress 
                variant="determinate" 
                value={metrics?.requests_failed ? (metrics.requests_failed / (metrics.requests_total || 1)) * 100 : 0} 
                color="error"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Storage color="info" />
                <Typography variant="subtitle2" color="text.secondary">
                  Серверы
                </Typography>
              </Box>
              <Typography variant="h4">
                {Object.keys(metrics?.server_stats || {}).length}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Активных MCP серверов
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Статус серверов */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Статус серверов
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <List>
              {metrics?.server_stats && Object.entries(metrics.server_stats).map(([serverName, stats]) => (
                <ListItem key={serverName}>
                  <ListItemIcon>
                    {getHealthIcon(stats.healthy ? 'healthy' : 'unhealthy')}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle1">
                          {serverName.toUpperCase()}
                        </Typography>
                        <Chip 
                          label={stats.healthy ? 'Активен' : 'Неактивен'}
                          size="small"
                          color={stats.healthy ? 'success' : 'error'}
                        />
                      </Box>
                    }
                    secondary={
                      <Box sx={{ mt: 1 }}>
                        <Typography variant="caption" display="block">
                          Запросов: {stats.requests || 0} | 
                          Ошибок: {stats.errors || 0} | 
                          Ср. время: {(stats.avg_response_time || 0).toFixed(2)}с
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
              ))}
              
              {(!metrics?.server_stats || Object.keys(metrics.server_stats).length === 0) && (
                <ListItem>
                  <ListItemText 
                    primary="Нет данных о серверах"
                    secondary="Серверы еще не инициализированы или нет активности"
                  />
                </ListItem>
              )}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Возможности системы
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            {capabilities?.servers && Object.entries(capabilities.servers).map(([serverName, serverCaps]) => (
              <Box key={serverName} sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="primary" gutterBottom>
                  {serverName.toUpperCase()} сервер
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                  <Chip 
                    label={`Инструментов: ${serverCaps.tools?.length || 0}`} 
                    size="small" 
                    variant="outlined"
                  />
                  <Chip 
                    label={`Ресурсов: ${serverCaps.resources?.length || 0}`} 
                    size="small" 
                    variant="outlined"
                  />
                </Box>
                
                {serverCaps.tools && serverCaps.tools.length > 0 && (
                  <Box sx={{ ml: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Доступные функции:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                      {serverCaps.tools.slice(0, 3).map((tool) => (
                        <Chip 
                          key={tool.name}
                          label={tool.name} 
                          size="small" 
                          sx={{ fontSize: '0.7rem' }}
                        />
                      ))}
                      {serverCaps.tools.length > 3 && (
                        <Chip 
                          label={`+${serverCaps.tools.length - 3}`} 
                          size="small" 
                          sx={{ fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  </Box>
                )}
              </Box>
            ))}
            
            {(!capabilities?.servers || Object.keys(capabilities.servers).length === 0) && (
              <Alert severity="info">
                Информация о возможностях недоступна
              </Alert>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Конфигурация */}
      <Paper sx={{ p: 2, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          Конфигурация MCP
        </Typography>
        <Divider sx={{ mb: 2 }} />
        
        <Grid container spacing={2}>
          {metrics?.config && Object.entries(metrics.config).map(([key, value]) => (
            <Grid item xs={12} sm={6} md={4} key={key}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {key.replace(/_/g, ' ').toLowerCase()}
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {typeof value === 'boolean' ? (
                    <Chip 
                      label={value ? 'Да' : 'Нет'} 
                      size="small" 
                      color={value ? 'success' : 'default'}
                    />
                  ) : (
                    value?.toString() || 'N/A'
                  )}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Paper>

      {/* Последняя проверка здоровья */}
      {metrics?.last_health_check && (
        <Alert 
          severity={metrics.last_health_check.overall === 'healthy' ? 'success' : 'warning'}
          sx={{ mt: 2 }}
        >
          Последняя проверка: {new Date(metrics.last_health_check.timestamp).toLocaleString('ru-RU')}
        </Alert>
      )}
    </Box>
  );
};

export default MCPMonitor;
