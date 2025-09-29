import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Select, Label, Textarea } from '../ui/native';
import { toast } from 'react-toastify';

const CloudPrintingManager = () => {
  const [activeTab, setActiveTab] = useState('printers');
  const [printers, setPrinters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPrinter, setSelectedPrinter] = useState(null);
  const [printJobs, setPrintJobs] = useState([]);
  const [statistics, setStatistics] = useState(null);

  // Состояние для печати документа
  const [printForm, setPrintForm] = useState({
    provider_name: 'mock',
    printer_id: '',
    title: '',
    content: '',
    format: 'html',
    copies: 1,
    color: false,
    duplex: false
  });

  // Состояние для медицинского документа
  const [medicalForm, setMedicalForm] = useState({
    provider_name: 'mock',
    printer_id: '',
    document_type: 'prescription',
    patient_data: {
      patient_name: '',
      age: '',
      phone: ''
    },
    template_data: {
      diagnosis: '',
      prescription_text: '',
      doctor_name: '',
      queue_number: '',
      cabinet: '',
      examination_results: '',
      conclusion: ''
    }
  });

  useEffect(() => {
    loadPrinters();
    loadStatistics();
  }, []);

  const loadPrinters = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/cloud-printing/printers`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPrinters(data.printers || []);
      } else {
        toast.error('Ошибка загрузки принтеров');
      }
    } catch (error) {
      console.error('Ошибка загрузки принтеров:', error);
      toast.error('Ошибка загрузки принтеров');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/cloud-printing/statistics`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setStatistics(data.statistics);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  };

  const testPrinter = async (providerName, printerId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/cloud-printing/test/${providerName}/${printerId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Тестовая печать отправлена');
      } else {
        toast.error(data.message || 'Ошибка тестовой печати');
      }
    } catch (error) {
      console.error('Ошибка тестовой печати:', error);
      toast.error('Ошибка тестовой печати');
    }
  };

  const printDocument = async () => {
    if (!printForm.printer_id || !printForm.title || !printForm.content) {
      toast.error('Заполните все обязательные поля');
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/cloud-printing/print`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(printForm)
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Документ отправлен на печать');
        setPrintForm({
          ...printForm,
          title: '',
          content: ''
        });
      } else {
        toast.error(data.message || 'Ошибка печати');
      }
    } catch (error) {
      console.error('Ошибка печати:', error);
      toast.error('Ошибка печати');
    }
  };

  const printMedicalDocument = async () => {
    if (!medicalForm.printer_id || !medicalForm.patient_data.patient_name) {
      toast.error('Заполните обязательные поля');
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/cloud-printing/print/medical`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(medicalForm)
      });

      const data = await response.json();
      if (data.success) {
        toast.success('Медицинский документ отправлен на печать');
      } else {
        toast.error(data.message || 'Ошибка печати');
      }
    } catch (error) {
      console.error('Ошибка печати медицинского документа:', error);
      toast.error('Ошибка печати медицинского документа');
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'online': return 'success';
      case 'busy': return 'warning';
      case 'offline': return 'secondary';
      case 'error': return 'destructive';
      default: return 'secondary';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'online': return 'В сети';
      case 'busy': return 'Занят';
      case 'offline': return 'Не в сети';
      case 'error': return 'Ошибка';
      default: return status;
    }
  };

  const renderPrintersTab = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Принтеры</h3>
        <Button onClick={loadPrinters} disabled={loading}>
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <div className="text-2xl font-bold text-blue-600">{statistics.total_printers}</div>
            <div className="text-sm text-gray-600">Всего принтеров</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-green-600">{statistics.online_printers}</div>
            <div className="text-sm text-gray-600">В сети</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-red-600">{statistics.offline_printers}</div>
            <div className="text-sm text-gray-600">Не в сети</div>
          </Card>
          <Card className="p-4">
            <div className="text-2xl font-bold text-purple-600">{statistics.providers_count}</div>
            <div className="text-sm text-gray-600">Провайдеров</div>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {printers.map((printer) => (
          <Card key={`${printer.provider}-${printer.id}`} className="p-4">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h4 className="font-semibold">{printer.name}</h4>
                <p className="text-sm text-gray-600">{printer.description}</p>
              </div>
              <Badge variant={getStatusBadgeVariant(printer.status)}>
                {getStatusText(printer.status)}
              </Badge>
            </div>
            
            <div className="space-y-2 text-sm">
              <div><strong>Провайдер:</strong> {printer.provider}</div>
              <div><strong>Местоположение:</strong> {printer.location || 'Не указано'}</div>
              <div><strong>ID:</strong> {printer.id}</div>
            </div>

            <div className="mt-4 flex gap-2">
              <Button
                size="sm"
                onClick={() => testPrinter(printer.provider, printer.id)}
                disabled={printer.status !== 'online'}
              >
                Тест
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedPrinter(printer)}
              >
                Подробнее
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {printers.length === 0 && !loading && (
        <div className="text-center py-8 text-gray-500">
          Принтеры не найдены
        </div>
      )}
    </div>
  );

  const renderPrintTab = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Печать документа</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-6">
          <h4 className="font-semibold mb-4">Настройки печати</h4>
          
          <div className="space-y-4">
            <div>
              <Label htmlFor="provider">Провайдер</Label>
              <Select
                id="provider"
                value={printForm.provider_name}
                onChange={(e) => setPrintForm({...printForm, provider_name: e.target.value})}
              >
                <option value="mock">Mock (Тестовый)</option>
                <option value="microsoft">Microsoft Universal Print</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="printer">Принтер</Label>
              <Select
                id="printer"
                value={printForm.printer_id}
                onChange={(e) => setPrintForm({...printForm, printer_id: e.target.value})}
              >
                <option value="">Выберите принтер</option>
                {printers
                  .filter(p => p.provider === printForm.provider_name)
                  .map(printer => (
                    <option key={printer.id} value={printer.id}>
                      {printer.name} ({getStatusText(printer.status)})
                    </option>
                  ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="title">Название документа</Label>
              <Input
                id="title"
                value={printForm.title}
                onChange={(e) => setPrintForm({...printForm, title: e.target.value})}
                placeholder="Введите название документа"
              />
            </div>

            <div>
              <Label htmlFor="format">Формат</Label>
              <Select
                id="format"
                value={printForm.format}
                onChange={(e) => setPrintForm({...printForm, format: e.target.value})}
              >
                <option value="html">HTML</option>
                <option value="text">Текст</option>
                <option value="pdf">PDF</option>
              </Select>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="copies">Копии</Label>
                <Input
                  id="copies"
                  type="number"
                  min="1"
                  max="10"
                  value={printForm.copies}
                  onChange={(e) => setPrintForm({...printForm, copies: parseInt(e.target.value)})}
                />
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="color"
                  checked={printForm.color}
                  onChange={(e) => setPrintForm({...printForm, color: e.target.checked})}
                />
                <Label htmlFor="color">Цветная</Label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="duplex"
                  checked={printForm.duplex}
                  onChange={(e) => setPrintForm({...printForm, duplex: e.target.checked})}
                />
                <Label htmlFor="duplex">Двусторонняя</Label>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h4 className="font-semibold mb-4">Содержимое документа</h4>
          
          <Textarea
            value={printForm.content}
            onChange={(e) => setPrintForm({...printForm, content: e.target.value})}
            placeholder="Введите содержимое документа (HTML, текст или base64 для PDF)"
            rows={15}
            className="w-full"
          />
          
          <Button 
            onClick={printDocument}
            className="w-full mt-4"
            disabled={!printForm.printer_id || !printForm.title || !printForm.content}
          >
            Печать
          </Button>
        </Card>
      </div>
    </div>
  );

  const renderMedicalTab = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Печать медицинских документов</h3>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h4 className="font-semibold mb-4">Основные настройки</h4>
          
          <div className="space-y-4">
            <div>
              <Label htmlFor="med-provider">Провайдер</Label>
              <Select
                id="med-provider"
                value={medicalForm.provider_name}
                onChange={(e) => setMedicalForm({...medicalForm, provider_name: e.target.value})}
              >
                <option value="mock">Mock (Тестовый)</option>
                <option value="microsoft">Microsoft Universal Print</option>
              </Select>
            </div>

            <div>
              <Label htmlFor="med-printer">Принтер</Label>
              <Select
                id="med-printer"
                value={medicalForm.printer_id}
                onChange={(e) => setMedicalForm({...medicalForm, printer_id: e.target.value})}
              >
                <option value="">Выберите принтер</option>
                {printers
                  .filter(p => p.provider === medicalForm.provider_name)
                  .map(printer => (
                    <option key={printer.id} value={printer.id}>
                      {printer.name} ({getStatusText(printer.status)})
                    </option>
                  ))}
              </Select>
            </div>

            <div>
              <Label htmlFor="doc-type">Тип документа</Label>
              <Select
                id="doc-type"
                value={medicalForm.document_type}
                onChange={(e) => setMedicalForm({...medicalForm, document_type: e.target.value})}
              >
                <option value="prescription">Рецепт</option>
                <option value="receipt">Чек</option>
                <option value="ticket">Талон</option>
                <option value="report">Отчет</option>
              </Select>
            </div>

            <h5 className="font-medium mt-6">Данные пациента</h5>
            <div>
              <Label htmlFor="patient-name">ФИО пациента *</Label>
              <Input
                id="patient-name"
                value={medicalForm.patient_data.patient_name}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  patient_data: {...medicalForm.patient_data, patient_name: e.target.value}
                })}
                placeholder="Введите ФИО пациента"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="patient-age">Возраст</Label>
                <Input
                  id="patient-age"
                  value={medicalForm.patient_data.age}
                  onChange={(e) => setMedicalForm({
                    ...medicalForm,
                    patient_data: {...medicalForm.patient_data, age: e.target.value}
                  })}
                  placeholder="Возраст"
                />
              </div>
              <div>
                <Label htmlFor="patient-phone">Телефон</Label>
                <Input
                  id="patient-phone"
                  value={medicalForm.patient_data.phone}
                  onChange={(e) => setMedicalForm({
                    ...medicalForm,
                    patient_data: {...medicalForm.patient_data, phone: e.target.value}
                  })}
                  placeholder="+998901234567"
                />
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h4 className="font-semibold mb-4">Данные шаблона</h4>
          
          <div className="space-y-4">
            {medicalForm.document_type === 'prescription' && (
              <>
                <div>
                  <Label htmlFor="diagnosis">Диагноз</Label>
                  <Input
                    id="diagnosis"
                    value={medicalForm.template_data.diagnosis}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, diagnosis: e.target.value}
                    })}
                    placeholder="Введите диагноз"
                  />
                </div>
                <div>
                  <Label htmlFor="prescription">Назначение</Label>
                  <Textarea
                    id="prescription"
                    value={medicalForm.template_data.prescription_text}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, prescription_text: e.target.value}
                    })}
                    placeholder="Введите назначение"
                    rows={4}
                  />
                </div>
                <div>
                  <Label htmlFor="doctor">Врач</Label>
                  <Input
                    id="doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, doctor_name: e.target.value}
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
              </>
            )}

            {medicalForm.document_type === 'ticket' && (
              <>
                <div>
                  <Label htmlFor="queue-number">Номер очереди</Label>
                  <Input
                    id="queue-number"
                    value={medicalForm.template_data.queue_number}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, queue_number: e.target.value}
                    })}
                    placeholder="A001"
                  />
                </div>
                <div>
                  <Label htmlFor="ticket-doctor">Врач</Label>
                  <Input
                    id="ticket-doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, doctor_name: e.target.value}
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
                <div>
                  <Label htmlFor="cabinet">Кабинет</Label>
                  <Input
                    id="cabinet"
                    value={medicalForm.template_data.cabinet}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, cabinet: e.target.value}
                    })}
                    placeholder="№ кабинета"
                  />
                </div>
              </>
            )}

            {medicalForm.document_type === 'report' && (
              <>
                <div>
                  <Label htmlFor="examination">Результаты обследования</Label>
                  <Textarea
                    id="examination"
                    value={medicalForm.template_data.examination_results}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, examination_results: e.target.value}
                    })}
                    placeholder="Введите результаты обследования"
                    rows={3}
                  />
                </div>
                <div>
                  <Label htmlFor="conclusion">Заключение</Label>
                  <Textarea
                    id="conclusion"
                    value={medicalForm.template_data.conclusion}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, conclusion: e.target.value}
                    })}
                    placeholder="Введите заключение"
                    rows={3}
                  />
                </div>
                <div>
                  <Label htmlFor="report-doctor">Врач</Label>
                  <Input
                    id="report-doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: {...medicalForm.template_data, doctor_name: e.target.value}
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
              </>
            )}
          </div>

          <Button 
            onClick={printMedicalDocument}
            className="w-full mt-6"
            disabled={!medicalForm.printer_id || !medicalForm.patient_data.patient_name}
          >
            Печать {medicalForm.document_type === 'prescription' ? 'рецепта' : 
                   medicalForm.document_type === 'receipt' ? 'чека' :
                   medicalForm.document_type === 'ticket' ? 'талона' : 'отчета'}
          </Button>
        </Card>
      </div>
    </div>
  );

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Облачная печать</h2>
        <p className="text-gray-600">Управление принтерами и печать документов через облачные сервисы</p>
      </div>

      <div className="mb-6">
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('printers')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'printers'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Принтеры
          </button>
          <button
            onClick={() => setActiveTab('print')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'print'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Печать документа
          </button>
          <button
            onClick={() => setActiveTab('medical')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'medical'
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Медицинские документы
          </button>
        </div>
      </div>

      {activeTab === 'printers' && renderPrintersTab()}
      {activeTab === 'print' && renderPrintTab()}
      {activeTab === 'medical' && renderMedicalTab()}

      {/* Модальное окно с подробностями принтера */}
      {selectedPrinter && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Подробности принтера</h3>
            
            <div className="space-y-3">
              <div><strong>Название:</strong> {selectedPrinter.name}</div>
              <div><strong>Описание:</strong> {selectedPrinter.description}</div>
              <div><strong>Провайдер:</strong> {selectedPrinter.provider}</div>
              <div><strong>Статус:</strong> <Badge variant={getStatusBadgeVariant(selectedPrinter.status)}>{getStatusText(selectedPrinter.status)}</Badge></div>
              <div><strong>Местоположение:</strong> {selectedPrinter.location || 'Не указано'}</div>
              <div><strong>ID:</strong> {selectedPrinter.id}</div>
              
              {selectedPrinter.capabilities && Object.keys(selectedPrinter.capabilities).length > 0 && (
                <div>
                  <strong>Возможности:</strong>
                  <pre className="text-xs bg-gray-100 p-2 rounded mt-1 overflow-auto">
                    {JSON.stringify(selectedPrinter.capabilities, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex gap-2 mt-6">
              <Button
                onClick={() => testPrinter(selectedPrinter.provider, selectedPrinter.id)}
                disabled={selectedPrinter.status !== 'online'}
              >
                Тестовая печать
              </Button>
              <Button
                variant="outline"
                onClick={() => setSelectedPrinter(null)}
              >
                Закрыть
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CloudPrintingManager;

