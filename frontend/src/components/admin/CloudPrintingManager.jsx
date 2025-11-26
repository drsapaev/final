import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect, 
  MacOSTextarea,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSModal
} from '../ui/macos';
import { 
  Printer, 
  RefreshCw, 
  Settings, 
  FileText, 
  TestTube,
  Eye,
  X
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

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
      const response = await api.get('/cloud-printing/printers');
      setPrinters(response.data?.printers || []);
    } catch (error) {
      console.error('Ошибка загрузки принтеров:', error);
      // Fallback данные для демонстрации
      setPrinters([
        {
          id: 'mock-printer-1',
          name: 'Тестовый принтер',
          description: 'Mock принтер для тестирования',
          provider: 'mock',
          status: 'online',
          location: 'Кабинет 101'
        },
        {
          id: 'mock-printer-2',
          name: 'Принтер документов',
          description: 'Основной принтер для документов',
          provider: 'mock',
          status: 'busy',
          location: 'Регистратура'
        }
      ]);
      toast.error('Ошибка загрузки принтеров, показаны тестовые данные');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await api.get('/cloud-printing/statistics');
      setStatistics(response.data?.statistics);
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      // Fallback данные для демонстрации
      setStatistics({
        total_printers: 2,
        online_printers: 1,
        offline_printers: 0,
        providers_count: 1
      });
    }
  };

  const testPrinter = async (providerName, printerId) => {
    try {
      const response = await api.post(`/cloud-printing/test/${providerName}/${printerId}`);
      if (response.data?.success) {
        toast.success('Тестовая печать отправлена');
      } else {
        toast.error(response.data?.message || 'Ошибка тестовой печати');
      }
    } catch (error) {
      console.error('Ошибка тестовой печати:', error);
      toast.error(error.response?.data?.detail || 'Ошибка тестовой печати');
    }
  };

  const printDocument = async () => {
    if (!printForm.printer_id || !printForm.title || !printForm.content) {
      toast.error('Заполните все обязательные поля');
      return;
    }

    try {
      const response = await api.post('/cloud-printing/print', printForm);
      if (response.data?.success) {
        toast.success('Документ отправлен на печать');
        setPrintForm({
          ...printForm,
          title: '',
          content: ''
        });
      } else {
        toast.error(response.data?.message || 'Ошибка печати');
      }
    } catch (error) {
      console.error('Ошибка печати:', error);
      toast.error(error.response?.data?.detail || 'Ошибка печати медицинского документа');
    }
  };

  const printMedicalDocument = async () => {
    if (!medicalForm.printer_id || !medicalForm.patient_data.patient_name) {
      toast.error('Заполните обязательные поля');
      return;
    }

    try {
      const response = await api.post('/cloud-printing/print/medical', medicalForm);
      if (response.data?.success) {
        toast.success('Медицинский документ отправлен на печать');
      } else {
        toast.error(response.data?.message || 'Ошибка печати');
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>Принтеры</h3>
        <MacOSButton onClick={loadPrinters} disabled={loading}>
          <RefreshCw size={16} style={{ marginRight: '8px' }} />
          {loading ? 'Загрузка...' : 'Обновить'}
        </MacOSButton>
      </div>

      {statistics && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px',
          marginBottom: '24px'
        }}>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-accent)' 
            }}>{statistics.total_printers}</div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>Всего принтеров</div>
          </MacOSCard>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-success)' 
            }}>{statistics.online_printers}</div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>В сети</div>
          </MacOSCard>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-destructive)' 
            }}>{statistics.offline_printers}</div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>Не в сети</div>
          </MacOSCard>
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-warning)' 
            }}>{statistics.providers_count}</div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>Провайдеров</div>
          </MacOSCard>
        </div>
      )}

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '16px' 
      }}>
        {printers.map((printer) => (
          <MacOSCard key={`${printer.provider}-${printer.id}`} style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <h4 style={{ 
                  margin: '0 0 4px 0',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-primary)'
                }}>{printer.name}</h4>
                <p style={{ 
                  margin: 0,
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>{printer.description}</p>
              </div>
              <MacOSBadge variant={getStatusBadgeVariant(printer.status)}>
                {getStatusText(printer.status)}
              </MacOSBadge>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: 'var(--mac-font-size-sm)' }}>
              <div><strong>Провайдер:</strong> {printer.provider}</div>
              <div><strong>Местоположение:</strong> {printer.location || 'Не указано'}</div>
              <div><strong>ID:</strong> {printer.id}</div>
            </div>

            <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
              <MacOSButton
                size="sm"
                onClick={() => testPrinter(printer.provider, printer.id)}
                disabled={printer.status !== 'online'}
              >
                <TestTube size={16} style={{ marginRight: '4px' }} />
                Тест
              </MacOSButton>
              <MacOSButton
                size="sm"
                variant="outline"
                onClick={() => setSelectedPrinter(printer)}
              >
                <Eye size={16} style={{ marginRight: '4px' }} />
                Подробнее
              </MacOSButton>
            </div>
          </MacOSCard>
        ))}
      </div>

      {printers.length === 0 && !loading && (
        <MacOSEmptyState
          icon={Printer}
          title="Принтеры не найдены"
          description="Добавьте принтеры или проверьте подключение к облачным сервисам"
        />
      )}
    </div>
  );

  const renderPrintTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h3 style={{ 
        margin: 0,
        color: 'var(--mac-text-primary)',
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)'
      }}>Печать документа</h3>
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
        gap: '24px' 
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)'
          }}>Настройки печати</h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }} htmlFor="provider">Провайдер</label>
              <MacOSSelect
                id="provider"
                value={printForm.provider_name}
                onChange={(e) => setPrintForm({ ...printForm, provider_name: e.target.value })}
                options={[
                  { value: 'mock', label: 'Mock (Тестовый)' },
                  { value: 'microsoft', label: 'Microsoft Universal Print' }
                ]}
              />
            </div>

            <div>
              <label style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }} htmlFor="printer">Принтер</label>
              <MacOSSelect
                id="printer"
                value={printForm.printer_id}
                onChange={(e) => setPrintForm({ ...printForm, printer_id: e.target.value })}
                options={[
                  { value: '', label: 'Выберите принтер' },
                  ...printers
                    .filter(p => p.provider === printForm.provider_name)
                    .map(printer => ({
                      value: printer.id,
                      label: `${printer.name} (${getStatusText(printer.status)})`
                    }))
                ]}
              />
            </div>

            <div>
              <label style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }} htmlFor="title">Название документа</label>
              <MacOSInput
                id="title"
                value={printForm.title}
                onChange={(e) => setPrintForm({ ...printForm, title: e.target.value })}
                placeholder="Введите название документа"
              />
            </div>

            <div>
              <label style={{ 
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }} htmlFor="format">Формат</label>
              <MacOSSelect
                id="format"
                value={printForm.format}
                onChange={(e) => setPrintForm({ ...printForm, format: e.target.value })}
                options={[
                  { value: 'html', label: 'HTML' },
                  { value: 'text', label: 'Текст' },
                  { value: 'pdf', label: 'PDF' }
                ]}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }} htmlFor="copies">Копии</label>
                <MacOSInput
                  id="copies"
                  type="number"
                  min="1"
                  max="10"
                  value={printForm.copies}
                  onChange={(e) => setPrintForm({ ...printForm, copies: parseInt(e.target.value) })}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="color"
                  checked={printForm.color}
                  onChange={(e) => setPrintForm({ ...printForm, color: e.target.checked })}
                  style={{ margin: 0 }}
                />
                <label style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }} htmlFor="color">Цветная</label>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="duplex"
                  checked={printForm.duplex}
                  onChange={(e) => setPrintForm({ ...printForm, duplex: e.target.checked })}
                  style={{ margin: 0 }}
                />
                <label style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }} htmlFor="duplex">Двусторонняя</label>
              </div>
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)'
          }}>Содержимое документа</h4>
          
          <MacOSTextarea
            value={printForm.content}
            onChange={(e) => setPrintForm({ ...printForm, content: e.target.value })}
            placeholder="Введите содержимое документа (HTML, текст или base64 для PDF)"
            rows={15}
            style={{ width: '100%' }}
          />
          
          <MacOSButton 
            onClick={printDocument}
            style={{ width: '100%', marginTop: '16px' }}
            disabled={!printForm.printer_id || !printForm.title || !printForm.content}
          >
            <Printer size={16} style={{ marginRight: '8px' }} />
            Печать
          </MacOSButton>
        </MacOSCard>
      </div>
    </div>
  );

  const renderMedicalTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h3 style={{ 
        margin: 0,
        color: 'var(--mac-text-primary)',
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)'
      }}>Печать медицинских документов</h3>
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
        gap: '24px' 
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            fontSize: 'var(--mac-font-size-md)',
            color: 'var(--mac-text-primary)'
          }}>Основные настройки</h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label htmlFor="med-provider" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Провайдер</label>
              <MacOSSelect
                id="med-provider"
                value={medicalForm.provider_name}
                onChange={(e) => setMedicalForm({ ...medicalForm, provider_name: e.target.value })}
              >
                <option value="mock">Mock (Тестовый)</option>
                <option value="microsoft">Microsoft Universal Print</option>
              </MacOSSelect>
            </div>

            <div>
              <label htmlFor="med-printer" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Принтер</label>
              <MacOSSelect
                id="med-printer"
                value={medicalForm.printer_id}
                onChange={(e) => setMedicalForm({ ...medicalForm, printer_id: e.target.value })}
              >
                <option value="">Выберите принтер</option>
                {printers
                  .filter(p => p.provider === medicalForm.provider_name)
                  .map(printer => (
                    <option key={printer.id} value={printer.id}>
                      {printer.name} ({getStatusText(printer.status)})
                    </option>
                  ))}
              </MacOSSelect>
            </div>

            <div>
              <label htmlFor="doc-type" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Тип документа</label>
              <MacOSSelect
                id="doc-type"
                value={medicalForm.document_type}
                onChange={(e) => setMedicalForm({ ...medicalForm, document_type: e.target.value })}
              >
                <option value="prescription">Рецепт</option>
                <option value="receipt">Чек</option>
                <option value="ticket">Талон</option>
                <option value="report">Отчет</option>
              </MacOSSelect>
            </div>

            <h5 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginTop: '24px',
              marginBottom: '16px',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-md)'
            }}>Данные пациента</h5>
            <div>
              <label htmlFor="patient-name" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>ФИО пациента *</label>
              <MacOSInput
                id="patient-name"
                value={medicalForm.patient_data.patient_name}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  patient_data: { ...medicalForm.patient_data, patient_name: e.target.value }
                })}
                placeholder="Введите ФИО пациента"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
              <div>
                <label htmlFor="patient-age" style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>Возраст</label>
                <MacOSInput
                  id="patient-age"
                  value={medicalForm.patient_data.age}
                  onChange={(e) => setMedicalForm({
                    ...medicalForm,
                    patient_data: { ...medicalForm.patient_data, age: e.target.value }
                  })}
                  placeholder="Возраст"
                />
              </div>
              <div>
                <label htmlFor="patient-phone" style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>Телефон</label>
                <MacOSInput
                  id="patient-phone"
                  value={medicalForm.patient_data.phone}
                  onChange={(e) => setMedicalForm({
                    ...medicalForm,
                    patient_data: { ...medicalForm.patient_data, phone: e.target.value }
                  })}
                  placeholder="+998901234567"
                />
              </div>
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            fontSize: 'var(--mac-font-size-md)',
            color: 'var(--mac-text-primary)'
          }}>Данные шаблона</h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {medicalForm.document_type === 'prescription' && (
              <>
                <div>
                  <label htmlFor="diagnosis" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Диагноз</label>
                  <MacOSInput
                    id="diagnosis"
                    value={medicalForm.template_data.diagnosis}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, diagnosis: e.target.value }
                    })}
                    placeholder="Введите диагноз"
                  />
                </div>
                <div>
                  <label htmlFor="prescription" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Назначение</label>
                  <MacOSTextarea
                    id="prescription"
                    value={medicalForm.template_data.prescription_text}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, prescription_text: e.target.value }
                    })}
                    placeholder="Введите назначение"
                    rows={4}
                  />
                </div>
                <div>
                  <label htmlFor="doctor" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Врач</label>
                  <MacOSInput
                    id="doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
              </>
            )}

            {medicalForm.document_type === 'ticket' && (
              <>
                <div>
                  <label htmlFor="queue-number" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Номер очереди</label>
                  <MacOSInput
                    id="queue-number"
                    value={medicalForm.template_data.queue_number}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, queue_number: e.target.value }
                    })}
                    placeholder="A001"
                  />
                </div>
                <div>
                  <label htmlFor="ticket-doctor" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Врач</label>
                  <MacOSInput
                    id="ticket-doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
                <div>
                  <label htmlFor="cabinet" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Кабинет</label>
                  <MacOSInput
                    id="cabinet"
                    value={medicalForm.template_data.cabinet}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, cabinet: e.target.value }
                    })}
                    placeholder="№ кабинета"
                  />
                </div>
              </>
            )}

            {medicalForm.document_type === 'report' && (
              <>
                <div>
                  <label htmlFor="examination" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Результаты обследования</label>
                  <MacOSTextarea
                    id="examination"
                    value={medicalForm.template_data.examination_results}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, examination_results: e.target.value }
                    })}
                    placeholder="Введите результаты обследования"
                    rows={3}
                  />
                </div>
                <div>
                  <label htmlFor="conclusion" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Заключение</label>
                  <MacOSTextarea
                    id="conclusion"
                    value={medicalForm.template_data.conclusion}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, conclusion: e.target.value }
                    })}
                    placeholder="Введите заключение"
                    rows={3}
                  />
                </div>
                <div>
                  <label htmlFor="report-doctor" style={{
                    display: 'block',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px'
                  }}>Врач</label>
                  <MacOSInput
                    id="report-doctor"
                    value={medicalForm.template_data.doctor_name}
                    onChange={(e) => setMedicalForm({
                      ...medicalForm,
                      template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                    })}
                    placeholder="ФИО врача"
                  />
                </div>
              </>
            )}
          </div>

          <MacOSButton 
            onClick={printMedicalDocument}
            style={{ width: '100%', marginTop: '24px' }}
            disabled={!medicalForm.printer_id || !medicalForm.patient_data.patient_name}
          >
            Печать {medicalForm.document_type === 'prescription' ? 'рецепта' : 
                   medicalForm.document_type === 'receipt' ? 'чека' :
                   medicalForm.document_type === 'ticket' ? 'талона' : 'отчета'}
          </MacOSButton>
        </MacOSCard>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Printer size={24} color="var(--mac-accent)" />
        <div>
          <h2 style={{ 
            margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Облачная печать
          </h2>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление принтерами и печать документов через облачные сервисы
          </p>
        </div>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }}>
        <button
          onClick={() => setActiveTab('printers')}
          style={{
            padding: '16px 24px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: activeTab === 'printers' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
            borderBottom: activeTab === 'printers' ? '2px solid var(--mac-accent)' : '2px solid transparent',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
        >
          Принтеры
        </button>
        <button
          onClick={() => setActiveTab('print')}
          style={{
            padding: '16px 24px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: activeTab === 'print' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
            borderBottom: activeTab === 'print' ? '2px solid var(--mac-accent)' : '2px solid transparent',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
        >
          Печать документа
        </button>
        <button
          onClick={() => setActiveTab('medical')}
          style={{
            padding: '16px 24px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: activeTab === 'medical' ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
            borderBottom: activeTab === 'medical' ? '2px solid var(--mac-accent)' : '2px solid transparent',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)'
          }}
        >
          Медицинские документы
        </button>
      </div>

      {activeTab === 'printers' && renderPrintersTab()}
      {activeTab === 'print' && renderPrintTab()}
      {activeTab === 'medical' && renderMedicalTab()}

      {/* Модальное окно с подробностями принтера */}
      {selectedPrinter && (
        <MacOSModal
          isOpen={!!selectedPrinter}
          onClose={() => setSelectedPrinter(null)}
          title="Подробности принтера"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div><strong>Название:</strong> {selectedPrinter.name}</div>
            <div><strong>Описание:</strong> {selectedPrinter.description}</div>
            <div><strong>Провайдер:</strong> {selectedPrinter.provider}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <strong>Статус:</strong> 
              <MacOSBadge variant={getStatusBadgeVariant(selectedPrinter.status)}>
                {getStatusText(selectedPrinter.status)}
              </MacOSBadge>
            </div>
            <div><strong>Местоположение:</strong> {selectedPrinter.location || 'Не указано'}</div>
            <div><strong>ID:</strong> {selectedPrinter.id}</div>
            
            {selectedPrinter.capabilities && Object.keys(selectedPrinter.capabilities).length > 0 && (
              <div>
                <strong>Возможности:</strong>
                <pre style={{ 
                  fontSize: 'var(--mac-font-size-xs)',
                  backgroundColor: 'var(--mac-surface-secondary)',
                  padding: '8px',
                  borderRadius: 'var(--mac-border-radius-md)',
                  marginTop: '4px',
                  overflow: 'auto',
                  color: 'var(--mac-text-primary)'
                }}>
                  {JSON.stringify(selectedPrinter.capabilities, null, 2)}
                </pre>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '24px' }}>
            <MacOSButton
              onClick={() => testPrinter(selectedPrinter.provider, selectedPrinter.id)}
              disabled={selectedPrinter.status !== 'online'}
            >
              <TestTube size={16} style={{ marginRight: '8px' }} />
              Тестовая печать
            </MacOSButton>
            <MacOSButton
              variant="outline"
              onClick={() => setSelectedPrinter(null)}
            >
              <X size={16} style={{ marginRight: '8px' }} />
              Закрыть
            </MacOSButton>
          </div>
        </MacOSModal>
      )}
    </div>
  );
};

export default CloudPrintingManager;

