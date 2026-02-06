import React, { useEffect, useState } from 'react';
import { Card, Button, Badge, Progress, Icon } from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Heart, FileText } from 'lucide-react';

// Simple Skeleton component
const Skeleton = ({ className = '' }) => (
  <div
    className={className}
    style={{
      background: 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s infinite',
      borderRadius: '8px',
      minHeight: '96px'
    }}
  />
);
const PatientPanel = () => {
  const { isMobile } = useBreakpoint();
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [appointments, setAppointments] = useState([]);
  const [results, setResults] = useState([]);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      await new Promise(r => setTimeout(r, 700));
      setAppointments([
        { id: 1, date: '2025-09-02', time: '09:30', doctor: 'Кардиолог', status: 'scheduled' },
        { id: 2, date: '2025-09-10', time: '10:00', doctor: 'Дерматолог', status: 'completed' }
      ]);
      setResults([
        { id: 1, title: 'Анализ крови', date: '2025-08-15' },
        { id: 2, title: 'ЭКГ', date: '2025-08-20' }
      ]);
      setIsLoading(false);
    };
    load();
  }, []);

  return (
    <div style={{
      padding: '0px', // Убираем padding, так как он уже есть в main контейнере
      background: 'var(--mac-gradient-window)',
      minHeight: '100vh',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)'
    }}>

      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Search */}
        <Card style={{
          backgroundColor: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-lg)',
          padding: '16px',
          boxShadow: 'var(--mac-shadow-sm)',
          backdropFilter: 'var(--mac-blur-light)',
          WebkitBackdropFilter: 'var(--mac-blur-light)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Icon
                name="magnifyingglass"
                size="small"
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mac-text-tertiary)'
                }}
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px 12px 12px 40px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  fontFamily: 'inherit',
                  outline: 'none',
                  transition: 'border-color var(--mac-duration-normal) var(--mac-ease)'
                }}
                placeholder="Search by doctor, service or result"
                onFocus={(e) => e.target.style.borderColor = 'var(--mac-accent-blue)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--mac-border)'}
              />
            </div>
            <Button variant="primary">
              <Icon name="plus" size="small" />
              New Appointment
            </Button>
          </div>
        </Card>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-0 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">Мои записи</h3>
            </div>
            <div className="p-4">
              {isLoading ? (
                <Skeleton className="h-24" />
              ) : (
                <div className="space-y-4">
                  {appointments.map(a => (
                    <div key={a.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{a.doctor}</div>
                        <div className="text-sm text-gray-500">{a.date} • {a.time}</div>
                      </div>
                      <Badge variant={a.status === 'scheduled' ? 'info' : 'success'}>
                        {a.status === 'scheduled' ? 'Запланировано' : 'Завершено'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card className="p-0 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <Heart className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">Результаты</h3>
            </div>
            <div className="p-4">
              {isLoading ? (
                <Skeleton className="h-24" />
              ) : (
                <div className="space-y-4">
                  {results.map(r => (
                    <div key={r.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{r.title}</div>
                        <div className="text-sm text-gray-500">{r.date}</div>
                      </div>
                      <Button variant="outline" size="sm"><FileText className="w-4 h-4 mr-2" />Открыть</Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PatientPanel;



