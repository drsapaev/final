import { useState } from 'react';
import { Printer, Settings, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { Card, Button, Badge } from './ui/native';
import { tokenManager } from '../utils/tokenManager';
import logger from '../utils/logger';

const PrintSystem = () => {
  const [printerStatus, setPrinterStatus] = useState('disconnected');
  const [printQueue, setPrintQueue] = useState([]);
  const [printerSettings, setPrinterSettings] = useState({
    type: 'network', // network, usb, none
    networkHost: '192.168.1.100',
    networkPort: '9100',
    usbVendorId: '0x04b8',
    usbProductId: '0x0202',
    paperWidth: 80, // мм
    encoding: 'cp866'
  });

  const testPrint = async () => {
    try {
      const response = await fetch('/api/v1/print/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(printerSettings)
      });

      if (response.ok) {
        setPrinterStatus('connected');
        addToPrintQueue('test', 'Тестовая печать', 'Проверка подключения принтера');
      } else {
        setPrinterStatus('error');
      }
    } catch (error) {
      logger.error('PrintSystem: Test print error:', error);
      setPrinterStatus('error');
    }
  };

  const printTicket = async (ticketData) => {
    try {
      const response = await fetch('/api/v1/print/ticket', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          ...ticketData,
          printer_settings: printerSettings
        })
      });

      if (response.ok) {
        addToPrintQueue('ticket', `Талон №${ticketData.number}`, ticketData.patient_name);
      } else {
        logger.error('PrintSystem: Print ticket error');
      }
    } catch (error) {
      logger.error('PrintSystem: Print ticket error:', error);
    }
  };

  const printReceipt = async (receiptData) => {
    try {
      const response = await fetch('/api/v1/print/receipt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          ...receiptData,
          printer_settings: printerSettings
        })
      });

      if (response.ok) {
        addToPrintQueue('receipt', `Чек №${receiptData.number}`, receiptData.patient_name);
      }
    } catch (error) {
      logger.error('PrintSystem: Print receipt error:', error);
    }
  };

  const addToPrintQueue = (type, title, description) => {
    const newItem = {
      id: Date.now(),
      type,
      title,
      description,
      timestamp: new Date(),
      status: 'printing'
    };

    setPrintQueue((prev) => [newItem, ...prev.slice(0, 9)]);

    // Имитация завершения печати через 2 секунды
    setTimeout(() => {
      setPrintQueue((prev) => prev.map((item) =>
      item.id === newItem.id ? { ...item, status: 'completed' } : item
      ));
    }, 2000);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'disconnected':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      default:
        return <AlertTriangle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'connected':
        return 'Подключен';
      case 'error':
        return 'Ошибка';
      case 'disconnected':
        return 'Отключен';
      default:
        return 'Неизвестно';
    }
  };

  const getQueueItemIcon = (type) => {
    switch (type) {
      case 'ticket':
        return '🎫';
      case 'receipt':
        return '🧾';
      case 'test':
        return '🔧';
      default:
        return '📄';
    }
  };

  return (
    <div className="space-y-6">
      {/* Статус принтера */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Printer className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-xl font-semibold">Система печати</h2>
              <p className="text-gray-500">ESC/POS принтер</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {getStatusIcon(printerStatus)}
            <span className="font-medium">{getStatusText(printerStatus)}</span>
          </div>
        </div>

        {/* Настройки принтера */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-1">Тип подключения</label>
            <select
              value={printerSettings.type}
              onChange={(e) => setPrinterSettings({ ...printerSettings, type: e.target.value })}
              className="w-full p-2 border border-gray-300 rounded-lg">
              
              <option value="network">Сетевой</option>
              <option value="usb">USB</option>
              <option value="none">Отключен</option>
            </select>
          </div>

          {printerSettings.type === 'network' &&
          <>
              <div>
                <label className="block text-sm font-medium mb-1">IP адрес</label>
                <input
                type="text"
                value={printerSettings.networkHost}
                onChange={(e) => setPrinterSettings({ ...printerSettings, networkHost: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
                placeholder="192.168.1.100" />
              
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Порт</label>
                <input
                type="text"
                value={printerSettings.networkPort}
                onChange={(e) => setPrinterSettings({ ...printerSettings, networkPort: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
                placeholder="9100" />
              
              </div>
            </>
          }

          <div>
            <label className="block text-sm font-medium mb-1">Ширина бумаги</label>
            <select
              value={printerSettings.paperWidth}
              onChange={(e) => setPrinterSettings({ ...printerSettings, paperWidth: parseInt(e.target.value) })}
              className="w-full p-2 border border-gray-300 rounded-lg">
              
              <option value={58}>58 мм</option>
              <option value={80}>80 мм</option>
            </select>
          </div>
        </div>

        {/* Кнопки управления */}
        <div className="flex gap-3">
          <Button onClick={testPrint}>
            <Settings className="w-4 h-4 mr-2" />
            Тест печати
          </Button>

          <Button
            variant="outline"
            onClick={() => printTicket({
              number: Math.floor(Math.random() * 100) + 1,
              patient_name: 'Тестовый пациент',
              specialist: 'Терапевт',
              room: '101',
              date: new Date().toLocaleDateString('ru-RU'),
              time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
            })}>
            
            Тестовый талон
          </Button>

          <Button
            variant="outline"
            onClick={() => printReceipt({
              number: 'R' + Math.floor(Math.random() * 1000),
              patient_name: 'Тестовый пациент',
              services: ['Консультация терапевта'],
              total: 50000,
              date: new Date().toLocaleDateString('ru-RU'),
              time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
            })}>
            
            Тестовый чек
          </Button>
        </div>
      </Card>

      {/* Очередь печати */}
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-lg">📋</span>
            <h3 className="text-lg font-semibold">Очередь печати</h3>
          </div>
          <Badge variant="info">{printQueue.length}</Badge>
        </div>

        {printQueue.length === 0 ?
        <div className="text-center py-8 text-gray-500">
            Очередь печати пуста
          </div> :

        <div className="space-y-3">
            {printQueue.map((item) =>
          <div
            key={item.id}
            className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
            
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{getQueueItemIcon(item.type)}</span>
                  <div>
                    <div className="font-medium">{item.title}</div>
                    <div className="text-sm text-gray-500">{item.description}</div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-sm text-gray-500">
                    {item.timestamp.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <Badge variant={item.status === 'completed' ? 'success' : 'warning'}>
                    {item.status === 'completed' ? 'Готово' : 'Печать...'}
                  </Badge>
                </div>
              </div>
          )}
          </div>
        }
      </Card>

      {/* Шаблон талона */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Предпросмотр талона</h3>

        <div className="bg-white border-2 border-dashed border-gray-300 p-4 rounded-lg max-w-sm mx-auto">
          <div className="text-center space-y-2 font-mono text-sm">
            <div className="font-bold">КЛИНИКА</div>
            <div className="text-xs">Электронная очередь</div>
            <div className="border-t border-b border-gray-300 py-2 my-2">
              <div className="text-2xl font-bold">№ 15</div>
            </div>
            <div>Терапевт</div>
            <div>Кабинет: 101</div>
            <div className="text-xs text-gray-600">
              {new Date().toLocaleDateString('ru-RU')}
            </div>
            <div className="text-xs text-gray-600">
              {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="text-xs border-t pt-2">
              Ожидайте вызова на табло
            </div>
          </div>
        </div>
      </Card>
    </div>);

};

export default PrintSystem;