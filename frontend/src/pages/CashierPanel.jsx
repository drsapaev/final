import React, { useEffect, useState } from 'react';
import { CreditCard, Calendar, Download, Search, Filter, CheckCircle, XCircle } from 'lucide-react';
import { Card, Badge, Button, Skeleton } from '../design-system/components';
import { useBreakpoint } from '../design-system/hooks';

const CashierPanel = () => {
  const { isMobile } = useBreakpoint();
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [payments, setPayments] = useState([]);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      await new Promise(r => setTimeout(r, 800));
      setPayments([
        { id: 1, time: '09:10', patient: 'Ахмедов Алишер', service: 'Консультация', amount: 120000, method: 'Карта', status: 'paid' },
        { id: 2, time: '09:30', patient: 'Каримова Зухра',  service: 'Анализы',     amount: 85000,  method: 'Наличные', status: 'paid' },
        { id: 3, time: '10:05', patient: 'Тошматов Бахтиёр', service: 'ЭхоКГ',       amount: 220000, method: 'Карта', status: 'pending' },
      ]);
      setIsLoading(false);
    };
    load();
  }, []);

  const format = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' сум';

  const filtered = payments.filter(p => {
    const matchesText = [p.patient, p.service, p.method].join(' ').toLowerCase().includes(query.toLowerCase());
    const matchesStatus = status === 'all' || p.status === status;
    return matchesText && matchesStatus;
  });

  return (
    <div style={{ padding: 16 }}>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CreditCard className="w-7 h-7 text-blue-600" />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Панель кассира</h1>
              <p className="text-sm text-gray-500">Приём оплат и выдача чеков</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm"><Calendar className="w-4 h-4 mr-2"/>Сегодня</Button>
            <Button variant="outline" size="sm"><Download className="w-4 h-4 mr-2"/>Экспорт</Button>
          </div>
        </div>

        {/* Filters */}
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={query}
                onChange={(e)=>setQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Поиск по пациенту, услуге, способу оплаты"
              />
            </div>
            <select
              value={status}
              onChange={(e)=>setStatus(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="all">Все статусы</option>
              <option value="paid">Оплачено</option>
              <option value="pending">Ожидает</option>
            </select>
            <Button variant="outline"><Filter className="w-4 h-4 mr-2"/>Фильтры</Button>
          </div>
        </Card>

        {/* Table */}
        <Card className="p-0 overflow-hidden">
          {isLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Время</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Пациент</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Услуга</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Способ</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Сумма</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Статус</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3">{row.time}</td>
                      <td className="px-4 py-3">{row.patient}</td>
                      <td className="px-4 py-3">{row.service}</td>
                      <td className="px-4 py-3">{row.method}</td>
                      <td className="px-4 py-3 font-medium">{format(row.amount)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={row.status === 'paid' ? 'success' : 'warning'}>
                          {row.status === 'paid' ? 'Оплачено' : 'Ожидает'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 flex gap-2">
                        <Button size="sm" variant="success"><CheckCircle className="w-4 h-4 mr-1"/>Принять</Button>
                        <Button size="sm" variant="danger"><XCircle className="w-4 h-4 mr-1"/>Отмена</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default CashierPanel;



