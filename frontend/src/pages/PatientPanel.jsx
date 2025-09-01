import React, { useEffect, useState } from 'react';
import { User, Calendar, Heart, FileText, Search } from 'lucide-react';
import { Card, Button, Badge, Skeleton } from '../design-system/components';
import { useBreakpoint } from '../design-system/hooks';

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
    <div style={{ padding: 16 }}>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <User className="w-7 h-7 text-blue-600" />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Панель пациента</h1>
            <p className="text-sm text-gray-500">Записи, результаты и рекомендации</p>
          </div>
        </div>

        {/* Search */}
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={query}
                onChange={(e)=>setQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Поиск по врачу, услуге или результату"
              />
            </div>
            <Button>Новая запись</Button>
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
                <div className="space-y-3">
                  {appointments.map(a => (
                    <div key={a.id} className="p-3 border border-gray-200 rounded-lg flex items-center justify-between">
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
                <div className="space-y-3">
                  {results.map(r => (
                    <div key={r.id} className="p-3 border border-gray-200 rounded-lg flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{r.title}</div>
                        <div className="text-sm text-gray-500">{r.date}</div>
                      </div>
                      <Button variant="outline" size="sm"><FileText className="w-4 h-4 mr-2"/>Открыть</Button>
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


