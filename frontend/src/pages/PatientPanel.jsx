import { useState } from 'react';
import { Card, Button, Badge, Icon } from '../components/ui/macos';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Calendar, Heart, FileText } from 'lucide-react';
import PropTypes from 'prop-types';

const PanelEmptyState = ({ icon: EmptyIcon, title, description }) =>
  <div className="p-6 border border-dashed border-gray-300 rounded-lg text-center bg-white/60">
    <EmptyIcon className="w-8 h-8 mx-auto mb-3 text-gray-400" aria-hidden="true" />
    <div className="font-medium text-gray-900">{title}</div>
    <p className="mt-1 text-sm text-gray-500">{description}</p>
  </div>;

PanelEmptyState.propTypes = {
  icon: PropTypes.elementType.isRequired,
  title: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
};


const PatientPanel = () => {
  useBreakpoint();
  const [query, setQuery] = useState('');
  const appointments = [];
  const results = [];
  const hasPatientData = appointments.length > 0 || results.length > 0;

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
                }} />

              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={!hasPatientData}
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
                  transition: 'border-color var(--mac-duration-normal) var(--mac-ease)',
                  opacity: hasPatientData ? 1 : 0.65
                }}
                placeholder={hasPatientData ? 'Поиск по врачу, услуге или результату' : 'Данные пациента пока не подключены'}
                onFocus={(e) => e.target.style.borderColor = 'var(--mac-accent-blue)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--mac-border)'} />

            </div>
            <Button
              variant="secondary"
              disabled
              title="Запись из кабинета пациента будет доступна после подключения реальных данных">
              <Icon name="plus" size="small" />
              Запись через кабинет
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
              {appointments.length > 0 ?
                <div className="space-y-4">
                  {appointments.map((a) =>
                    <div key={a.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{a.doctor}</div>
                        <div className="text-sm text-gray-500">{a.date} • {a.time}</div>
                      </div>
                      <Badge variant={a.status === 'scheduled' ? 'info' : 'success'}>
                        {a.status === 'scheduled' ? 'Запланировано' : 'Завершено'}
                      </Badge>
                    </div>
                  )}
                </div>
                :
                <PanelEmptyState
                  icon={Calendar}
                  title="Записей пока нет"
                  description="Здесь появятся только подтвержденные записи пациента после подключения личного кабинета к данным клиники." />
              }
            </div>
          </Card>

          <Card className="p-0 overflow-hidden">
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
              <Heart className="w-4 h-4" />
              <h3 className="font-medium text-gray-900">Результаты</h3>
            </div>
            <div className="p-4">
              {results.length > 0 ?
                <div className="space-y-4">
                  {results.map((r) =>
                    <div key={r.id} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{r.title}</div>
                        <div className="text-sm text-gray-500">{r.date}</div>
                      </div>
                      <Button variant="outline" size="sm">
                        <FileText className="w-4 h-4 mr-2" />
                        Открыть
                      </Button>
                    </div>
                  )}
                </div>
                :
                <PanelEmptyState
                  icon={FileText}
                  title="Результаты пока не загружены"
                  description="Система не показывает демонстрационные анализы. Реальные результаты появятся после интеграции с данными пациента." />
              }
            </div>
          </Card>
        </div>
      </div>
    </div>);

};

export default PatientPanel;
