import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Label, Select, Textarea } from '../ui/native';
import { 
  Bell, 
  Users, 
  Send, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Settings,
  BarChart3,
  MessageSquare,
  Phone,
  Mail,
  RefreshCw,
  Filter,
  Calendar,
  Activity
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const RegistrarNotificationManager = () => {
  const { theme, getColor, getSpacing } = useTheme();
  const [activeTab, setActiveTab] = useState('send');
  const [loading, setLoading] = useState(false);
  const [registrars, setRegistrars] = useState([]);
  const [stats, setStats] = useState(null);

  // Состояние для отправки уведомлений
  const [notificationForm, setNotificationForm] = useState({
    type: 'system_alert',
    alert_type: 'system_error',
    message: '',
    priority: 'normal',
    department: ''
  });

  // Состояние для тестирования
  const [testMessage, setTestMessage] = useState('Тестовое уведомление системы');

  useEffect(() => {
    loadRegistrars();
    loadStats();
  }, []);

  const loadRegistrars = async () => {
    try {
      const response = await api.get('/registrar/notifications/registrars');
      setRegistrars(response.data.registrars || []);
    } catch (error) {
      console.error('Ошибка загрузки регистраторов:', error);
      toast.error('Ошибка загрузки списка регистраторов');
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/registrar/notifications/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      toast.error('Ошибка загрузки статистики');
    }
  };

  const handleSendNotification = async () => {
    if (!notificationForm.message.trim()) {
      toast.error('Введите текст уведомления');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/system-alert', {
        alert_type: notificationForm.alert_type,
        message: notificationForm.message,
        priority: notificationForm.priority,
        department: notificationForm.department || null
      });

      if (response.data.success) {
        toast.success(`Уведомление отправлено ${response.data.sent_count} регистраторам`);
        setNotificationForm({
          ...notificationForm,
          message: ''
        });
        loadStats(); // Обновляем статистику
      } else {
        toast.error('Ошибка отправки уведомления');
      }
    } catch (error) {
      console.error('Ошибка отправки уведомления:', error);
      toast.error('Ошибка отправки уведомления');
    } finally {
      setLoading(false);
    }
  };

  const handleSendDailySummary = async () => {
    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/daily-summary');
      
      if (response.data.success) {
        toast.success(`Ежедневная сводка отправлена ${response.data.sent_count} регистраторам`);
        loadStats();
      } else {
        toast.error('Ошибка отправки сводки');
      }
    } catch (error) {
      console.error('Ошибка отправки сводки:', error);
      toast.error('Ошибка отправки ежедневной сводки');
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async () => {
    if (!testMessage.trim()) {
      toast.error('Введите текст тестового уведомления');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/registrar/notifications/test?message=${encodeURIComponent(testMessage)}`);
      
      if (response.data.success) {
        toast.success(`Тестовое уведомление отправлено ${response.data.sent_count} регистраторам`);
        loadStats();
      } else {
        toast.error('Ошибка отправки тестового уведомления');
      }
    } catch (error) {
      console.error('Ошибка отправки тестового уведомления:', error);
      toast.error('Ошибка отправки тестового уведомления');
    } finally {
      setLoading(false);
    }
  };

  const renderSendTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {/* Форма отправки уведомления */}
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ 
          margin: `0 0 ${getSpacing('md')} 0`,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Send size={20} />
          Отправить уведомление
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: getSpacing('md'), marginBottom: getSpacing('md') }}>
          <div>
            <Label>Тип уведомления</Label>
            <Select
              value={notificationForm.alert_type}
              onChange={(e) => setNotificationForm({...notificationForm, alert_type: e.target.value})}
            >
              <option value="system_error">Системная ошибка</option>
              <option value="payment_issue">Проблема с оплатой</option>
              <option value="queue_overflow">Переполнение очереди</option>
              <option value="equipment_failure">Неисправность оборудования</option>
              <option value="security_alert">Безопасность</option>
              <option value="maintenance">Техническое обслуживание</option>
            </Select>
          </div>

          <div>
            <Label>Приоритет</Label>
            <Select
              value={notificationForm.priority}
              onChange={(e) => setNotificationForm({...notificationForm, priority: e.target.value})}
            >
              <option value="normal">Обычный</option>
              <option value="warning">Предупреждение</option>
              <option value="critical">Критический</option>
            </Select>
          </div>
        </div>

        <div style={{ marginBottom: getSpacing('md') }}>
          <Label>Отделение (опционально)</Label>
          <Input
            placeholder="Например: Кардиология, Стоматология"
            value={notificationForm.department}
            onChange={(e) => setNotificationForm({...notificationForm, department: e.target.value})}
          />
        </div>

        <div style={{ marginBottom: getSpacing('md') }}>
          <Label>Текст уведомления</Label>
          <Textarea
            placeholder="Введите текст уведомления для регистраторов..."
            value={notificationForm.message}
            onChange={(e) => setNotificationForm({...notificationForm, message: e.target.value})}
            rows={4}
          />
        </div>

        <Button 
          onClick={handleSendNotification}
          disabled={loading || !notificationForm.message.trim()}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm'),
            backgroundColor: getColor('primary', 600),
            color: 'white'
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Send size={16} />}
          Отправить уведомление
        </Button>
      </Card>

      {/* Быстрые действия */}
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ 
          margin: `0 0 ${getSpacing('md')} 0`,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Activity size={20} />
          Быстрые действия
        </h3>

        <div style={{ display: 'flex', gap: getSpacing('md'), flexWrap: 'wrap' }}>
          <Button 
            onClick={handleSendDailySummary}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: getSpacing('sm'),
              backgroundColor: getColor('blue', 600),
              color: 'white'
            }}
          >
            <Calendar size={16} />
            Отправить ежедневную сводку
          </Button>

          <div style={{ display: 'flex', gap: getSpacing('sm'), alignItems: 'center' }}>
            <Input
              placeholder="Текст тестового уведомления"
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              style={{ minWidth: '200px' }}
            />
            <Button 
              onClick={handleTestNotification}
              disabled={loading || !testMessage.trim()}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: getSpacing('sm'),
                backgroundColor: getColor('green', 600),
                color: 'white'
              }}
            >
              <MessageSquare size={16} />
              Тест
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );

  const renderRegistrarsTab = () => (
    <Card style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: getSpacing('lg')
      }}>
        <h3 style={{ 
          margin: 0,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Users size={20} />
          Активные регистраторы ({registrars.length})
        </h3>
        <Button 
          onClick={loadRegistrars}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>

      <div style={{ display: 'grid', gap: getSpacing('md') }}>
        {registrars.map((registrar) => (
          <div
            key={registrar.id}
            style={{
              padding: getSpacing('md'),
              border: `1px solid ${getColor('gray', 200)}`,
              borderRadius: '8px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <div style={{ 
                fontWeight: 'bold',
                color: getColor('text', 900),
                marginBottom: getSpacing('xs')
              }}>
                {registrar.full_name || registrar.username}
              </div>
              <div style={{ 
                fontSize: '14px',
                color: getColor('text', 600),
                display: 'flex',
                alignItems: 'center',
                gap: getSpacing('md')
              }}>
                {registrar.email && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                    <Mail size={14} />
                    {registrar.email}
                  </span>
                )}
                {registrar.phone && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                    <Phone size={14} />
                    {registrar.phone}
                  </span>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
              {registrar.telegram_id && (
                <Badge style={{ backgroundColor: getColor('blue', 100), color: getColor('blue', 800) }}>
                  Telegram
                </Badge>
              )}
              <Badge 
                style={{ 
                  backgroundColor: registrar.is_active ? getColor('green', 100) : getColor('red', 100),
                  color: registrar.is_active ? getColor('green', 800) : getColor('red', 800)
                }}
              >
                {registrar.is_active ? 'Активен' : 'Неактивен'}
              </Badge>
            </div>
          </div>
        ))}
      </div>

      {registrars.length === 0 && (
        <div style={{ 
          textAlign: 'center', 
          padding: getSpacing('xl'),
          color: getColor('text', 500)
        }}>
          Нет активных регистраторов
        </div>
      )}
    </Card>
  );

  const renderStatsTab = () => (
    <Card style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: getSpacing('lg')
      }}>
        <h3 style={{ 
          margin: 0,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <BarChart3 size={20} />
          Статистика уведомлений
        </h3>
        <Button 
          onClick={loadStats}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>

      {stats ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md') }}>
          <div style={{ 
            padding: getSpacing('md'),
            backgroundColor: getColor('blue', 50),
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('blue', 600) }}>
              {stats.total_sent}
            </div>
            <div style={{ color: getColor('text', 600) }}>Всего отправлено</div>
          </div>

          <div style={{ 
            padding: getSpacing('md'),
            backgroundColor: getColor('green', 50),
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('green', 600) }}>
              {stats.successful_deliveries}
            </div>
            <div style={{ color: getColor('text', 600) }}>Успешно доставлено</div>
          </div>

          <div style={{ 
            padding: getSpacing('md'),
            backgroundColor: getColor('red', 50),
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('red', 600) }}>
              {stats.failed_deliveries}
            </div>
            <div style={{ color: getColor('text', 600) }}>Ошибки доставки</div>
          </div>
        </div>
      ) : (
        <div style={{ 
          textAlign: 'center', 
          padding: getSpacing('xl'),
          color: getColor('text', 500)
        }}>
          Загрузка статистики...
        </div>
      )}

      {stats && stats.channels_stats && (
        <div style={{ marginTop: getSpacing('lg') }}>
          <h4 style={{ 
            margin: `0 0 ${getSpacing('md')} 0`,
            color: getColor('text', 900)
          }}>
            Статистика по каналам
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: getSpacing('md') }}>
            <div style={{ 
              padding: getSpacing('sm'),
              border: `1px solid ${getColor('gray', 200)}`,
              borderRadius: '6px',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'bold', color: getColor('blue', 600) }}>
                {stats.channels_stats.telegram}
              </div>
              <div style={{ fontSize: '14px', color: getColor('text', 600) }}>Telegram</div>
            </div>

            <div style={{ 
              padding: getSpacing('sm'),
              border: `1px solid ${getColor('gray', 200)}`,
              borderRadius: '6px',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'bold', color: getColor('green', 600) }}>
                {stats.channels_stats.email}
              </div>
              <div style={{ fontSize: '14px', color: getColor('text', 600) }}>Email</div>
            </div>

            <div style={{ 
              padding: getSpacing('sm'),
              border: `1px solid ${getColor('gray', 200)}`,
              borderRadius: '6px',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'bold', color: getColor('orange', 600) }}>
                {stats.channels_stats.sms}
              </div>
              <div style={{ fontSize: '14px', color: getColor('text', 600) }}>SMS</div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );

  const tabs = [
    { id: 'send', label: 'Отправка', icon: Send },
    { id: 'registrars', label: 'Регистраторы', icon: Users },
    { id: 'stats', label: 'Статистика', icon: BarChart3 }
  ];

  return (
    <div style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: getSpacing('md'),
        marginBottom: getSpacing('lg')
      }}>
        <Bell size={24} color={getColor('primary', 600)} />
        <h2 style={{ 
          margin: 0, 
          color: getColor('text', 900),
          fontSize: '24px',
          fontWeight: 'bold'
        }}>
          Уведомления регистратуры
        </h2>
      </div>

      {/* Вкладки */}
      <div style={{ 
        display: 'flex', 
        borderBottom: `1px solid ${getColor('gray', 200)}`,
        marginBottom: getSpacing('lg')
      }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: `${getSpacing('md')} ${getSpacing('lg')}`,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: getSpacing('sm'),
                borderBottom: activeTab === tab.id ? `2px solid ${getColor('primary', 600)}` : '2px solid transparent',
                color: activeTab === tab.id ? getColor('primary', 600) : getColor('text', 600),
                fontWeight: activeTab === tab.id ? 'bold' : 'normal'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Содержимое вкладок */}
      {activeTab === 'send' && renderSendTab()}
      {activeTab === 'registrars' && renderRegistrarsTab()}
      {activeTab === 'stats' && renderStatsTab()}
    </div>
  );
};

export default RegistrarNotificationManager;

