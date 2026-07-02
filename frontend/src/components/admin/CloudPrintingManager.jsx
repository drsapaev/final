import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  SegmentedControl,
  Textarea,
  AppEmpty,
  Modal,
} from '../ui/macos';
import {
  Printer,
  RefreshCw,


  TestTube,
  Eye,
  X } from
'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const PROVIDER_LABELS = {
  mock: 'Mock (Тестовый)',
  microsoft: 'Microsoft Universal Print',
  google: 'Google Cloud Print',
  local: 'Local Print Gateway'
};

const getProviderLabel = (provider) => PROVIDER_LABELS[provider] || provider;

const getStatusText = (status) => {
  switch (status) {
    case 'online': return 'В сети';
    case 'busy': return 'Занят';
    case 'offline': return 'Не в сети';
    case 'error': return 'Ошибка';
    default: return status || 'Статус неизвестен';
  }
};

const getProviderOptions = (providers = []) =>
  providers.map((provider) => ({
    value: provider,
    label: getProviderLabel(provider)
  }));

const getPrinterOptions = (printers = [], providerName = '') =>
  printers
    .filter((printer) => printer.provider === providerName)
    .map((printer) => ({
      value: printer.id,
      label: `${printer.name} (${getStatusText(printer.status)})`
    }));

const normalizeLocalPrinter = (printer) => ({
  id: printer.name || String(printer.id),
  name: printer.display_name || printer.name || 'Локальный принтер',
  description:
    [
      printer.printer_type ? `${printer.printer_type}` : null,
      printer.connection_type ? `подключение: ${printer.connection_type}` : null
    ]
      .filter(Boolean)
      .join(' • ') || 'Локальный системный принтер',
  status: printer.status || null,
  location: printer.device_path || printer.location || 'Локальный компьютер',
  capabilities: {
    printer_type: printer.printer_type || 'unknown',
    device_path: printer.device_path || null,
    paper_width: printer.paper_width || null,
    paper_height: printer.paper_height || null,
    encoding: printer.encoding || 'utf-8'
  },
  provider: 'local',
  printer_type: printer.printer_type || 'unknown',
  connection_type: printer.connection_type || 'local',
  is_default: Boolean(printer.is_default),
  source: 'system'
});

const CloudPrintingManager = () => {
  const [activeTab, setActiveTab] = useState('printers');
  const [printers, setPrinters] = useState([]);
  const [localPrinters, setLocalPrinters] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPrinter, setSelectedPrinter] = useState(null);
  const [statistics, setStatistics] = useState(null);

  // Состояние для печати документа
  const [printForm, setPrintForm] = useState({
    provider_name: '',
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
    provider_name: '',
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

  useEffect(() => {
    if (providers.length === 0) {
      return;
    }

    setPrintForm((prev) => (
      providers.includes(prev.provider_name)
        ? prev
        : { ...prev, provider_name: providers[0] }
    ));

    setMedicalForm((prev) => (
      providers.includes(prev.provider_name)
        ? prev
        : { ...prev, provider_name: providers[0] }
    ));
  }, [providers]);

  const loadPrinters = async () => {
    setLoading(true);
    try {
      const [cloudResponse, localResponse] = await Promise.all([
        api.get('/cloud-printing/printers'),
        api.get('/print/printers')
      ]);
      const printersData = cloudResponse.data?.printers || [];
      const providersData = cloudResponse.data?.providers || [];
      const localPrintersData = (localResponse.data?.printers || []).map(
        normalizeLocalPrinter
      );

      setPrinters(printersData);
      setLocalPrinters(localPrintersData);
      setProviders(
        providersData.length > 0
          ? providersData
          : Array.from(new Set(printersData.map((printer) => printer.provider).filter(Boolean)))
      );
    } catch (error) {
      logger.error('Ошибка загрузки принтеров:', error);
      setPrinters([]);
      setLocalPrinters([]);
      setProviders([]);
      setSelectedPrinter(null);
      toast.error('Не удалось загрузить облачные принтеры');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await api.get('/cloud-printing/statistics');
      setStatistics(response.data?.statistics);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      setStatistics(null);
    }
  };

  const testPrinter = async (providerName, printerId) => {
    try {
      const response = providerName === 'local'
        ? await api.post(`/print/printers/${encodeURIComponent(printerId)}/test`)
        : await api.post(`/cloud-printing/test/${providerName}/${printerId}`);

      if (response.data?.success || response.data?.status === 'printed' || response.data?.message) {
        toast.success('Тестовая печать отправлена');
      } else {
        toast.error(response.data?.message || 'Ошибка тестовой печати');
      }
    } catch (error) {
      logger.error('Ошибка тестовой печати:', error);
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
      logger.error('Ошибка печати:', error);
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
      logger.error('Ошибка печати медицинского документа:', error);
      toast.error('Ошибка печати медицинского документа');
    }
  };

  const getStatusBadgeVariant = (status) => {
    switch (status) {
      case 'online':return 'success';
      case 'busy':return 'warning';
      case 'offline':return 'secondary';
      case 'error':return 'destructive';
      default:return 'secondary';
    }
  };

  const renderPrinterGrid = (list, emptyTitle) =>
    <>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '16px'
      }}>
        {list.map((printer) =>
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
              <Badge variant={getStatusBadgeVariant(printer.status)}>
                {getStatusText(printer.status)}
              </Badge>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: 'var(--mac-font-size-sm)' }}>
              <div><strong>Провайдер:</strong> {printer.provider}</div>
              <div><strong>Местоположение:</strong> {printer.location || 'Не указано'}</div>
              <div><strong>ID:</strong> {printer.id}</div>
              {printer.provider === 'local' &&
              <div><strong>Тип:</strong> {printer.printer_type || 'unknown'}</div>
              }
            </div>

            <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
              <Button
                size="sm"
                onClick={() => testPrinter(printer.provider, printer.id)}
                disabled={printer.status !== 'online'}>

                <TestTube size={16} style={{ marginRight: '4px' }} />
                Тест
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedPrinter(printer)}>

                <Eye size={16} style={{ marginRight: '4px' }} />
                Подробнее
              </Button>
            </div>
          </MacOSCard>
        )}
      </div>

      {list.length === 0 && !loading &&
      <AppEmpty
        icon={Printer}
        title={emptyTitle}
        description="Добавьте принтеры или проверьте подключение к облачным сервисам" />
      }
    </>;

  const renderPrintersTab = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{
        margin: 0,
        color: 'var(--mac-text-primary)',
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-semibold)'
      }}>Принтеры</h3>
        <Button onClick={loadPrinters} disabled={loading}>
          <RefreshCw size={16} style={{ marginRight: '8px' }} />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

        {statistics &&
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
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{
          fontSize: 'var(--mac-font-size-2xl)',
          fontWeight: 'var(--mac-font-weight-bold)',
          color: 'var(--mac-accent)'
        }}>{localPrinters.length}</div>
            <div style={{
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)'
        }}>Локальных ОС-принтеров</div>
          </MacOSCard>
        </div>
    }

      <div style={{ display: 'grid', gap: '24px' }}>
        <div style={{ display: 'grid', gap: '12px' }}>
          <h4 style={{
            margin: 0,
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>Облачные принтеры</h4>
          {renderPrinterGrid(printers, 'Принтеры не найдены')}
        </div>

        <div style={{ display: 'grid', gap: '12px' }}>
          <h4 style={{
            margin: 0,
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-md)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>Локальные ОС-принтеры</h4>
          {renderPrinterGrid(localPrinters, 'Локальные принтеры не найдены')}
        </div>
      </div>
    </div>;


  const renderPrintTab = () =>
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
              <Select
              id="provider"
              value={printForm.provider_name}
              onChange={(value) => setPrintForm({
                ...printForm,
                provider_name: value,
                printer_id: ''
              })}
              options={[
                { value: '', label: 'Выберите провайдера' },
                ...getProviderOptions(providers)
              ]}
              size="large" />
            
            </div>

            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }} htmlFor="printer">Принтер</label>
              <Select
              id="printer"
              value={printForm.printer_id}
              onChange={(value) => setPrintForm({ ...printForm, printer_id: value })}
              options={[
              { value: '', label: 'Выберите принтер' },
              ...getPrinterOptions(printers, printForm.provider_name)]
              }
              size="large" />
            
            </div>

            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }} htmlFor="title">Название документа</label>
              <Input
              id="title"
              value={printForm.title}
              onChange={(e) => setPrintForm({ ...printForm, title: e.target.value })}
              placeholder="Введите название документа" />
            
            </div>

            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }} htmlFor="format">Формат</label>
              <Select
              id="format"
              value={printForm.format}
              onChange={(value) => setPrintForm({ ...printForm, format: value })}
              options={[
              { value: 'html', label: 'HTML' },
              { value: 'text', label: 'Текст' },
              { value: 'pdf', label: 'PDF' }]
              }
              size="large" />
            
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
                <Input
                id="copies"
                type="number"
                min="1"
                max="10"
                value={printForm.copies}
                onChange={(e) => setPrintForm({ ...printForm, copies: parseInt(e.target.value) })} />
              
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                type="checkbox"
                id="color"
                aria-label="Enable color printing"
                checked={printForm.color}
                onChange={(e) => setPrintForm({ ...printForm, color: e.target.checked })}
                style={{ margin: 0 }} />
              
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
                aria-label="Enable duplex printing"
                checked={printForm.duplex}
                onChange={(e) => setPrintForm({ ...printForm, duplex: e.target.checked })}
                style={{ margin: 0 }} />
              
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
          
          <Textarea
          value={printForm.content}
          onChange={(e) => setPrintForm({ ...printForm, content: e.target.value })}
          placeholder="Введите содержимое документа (HTML, текст или base64 для PDF)"
          rows={15}
          style={{ width: '100%' }} />
        
          
          <Button
          onClick={printDocument}
          style={{ width: '100%', marginTop: '16px' }}
          disabled={!printForm.printer_id || !printForm.title || !printForm.content}>
          
            <Printer size={16} style={{ marginRight: '8px' }} />
            Печать
          </Button>
        </MacOSCard>
      </div>
    </div>;


  const renderMedicalTab = () =>
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
              <Select
              id="med-provider"
              value={medicalForm.provider_name}
              onChange={(value) => setMedicalForm({
                ...medicalForm,
                provider_name: value,
                printer_id: ''
              })}
              options={[
                { value: '', label: 'Выберите провайдера' },
                ...getProviderOptions(providers)
              ]}
              size="large" />
            </div>

            <div>
              <label htmlFor="med-printer" style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Принтер</label>
              <Select
              id="med-printer"
              value={medicalForm.printer_id}
              onChange={(value) => setMedicalForm({ ...medicalForm, printer_id: value })}
              options={[
                { value: '', label: 'Выберите принтер' },
                ...getPrinterOptions(printers, medicalForm.provider_name)
              ]}
              size="large" />
            </div>

            <div>
              <label htmlFor="doc-type" style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Тип документа</label>
              <Select
              id="doc-type"
              value={medicalForm.document_type}
              onChange={(value) => setMedicalForm({ ...medicalForm, document_type: value })}
              options={[
                { value: 'prescription', label: 'Рецепт' },
                { value: 'receipt', label: 'Чек' },
                { value: 'ticket', label: 'Талон' },
                { value: 'report', label: 'Отчет' }
              ]}
              size="large" />
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
              <Input
              id="patient-name"
              value={medicalForm.patient_data.patient_name}
              onChange={(e) => setMedicalForm({
                ...medicalForm,
                patient_data: { ...medicalForm.patient_data, patient_name: e.target.value }
              })}
              placeholder="Введите ФИО пациента" />
            
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
                <Input
                id="patient-age"
                value={medicalForm.patient_data.age}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  patient_data: { ...medicalForm.patient_data, age: e.target.value }
                })}
                placeholder="Возраст" />
              
              </div>
              <div>
                <label htmlFor="patient-phone" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Телефон</label>
                <Input
                id="patient-phone"
                value={medicalForm.patient_data.phone}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  patient_data: { ...medicalForm.patient_data, phone: e.target.value }
                })}
                placeholder="+998901234567" />
              
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
            {medicalForm.document_type === 'prescription' &&
          <>
                <div>
                  <label htmlFor="diagnosis" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Диагноз</label>
                  <Input
                id="diagnosis"
                value={medicalForm.template_data.diagnosis}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, diagnosis: e.target.value }
                })}
                placeholder="Введите диагноз" />
              
                </div>
                <div>
                  <label htmlFor="prescription" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Назначение</label>
                  <Textarea
                id="prescription"
                value={medicalForm.template_data.prescription_text}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, prescription_text: e.target.value }
                })}
                placeholder="Введите назначение"
                rows={4} />
              
                </div>
                <div>
                  <label htmlFor="doctor" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Врач</label>
                  <Input
                id="doctor"
                value={medicalForm.template_data.doctor_name}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder="ФИО врача" />
              
                </div>
              </>
          }

            {medicalForm.document_type === 'ticket' &&
          <>
                <div>
                  <label htmlFor="queue-number" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Номер очереди</label>
                  <Input
                id="queue-number"
                value={medicalForm.template_data.queue_number}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, queue_number: e.target.value }
                })}
                placeholder="A001" />
              
                </div>
                <div>
                  <label htmlFor="ticket-doctor" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Врач</label>
                  <Input
                id="ticket-doctor"
                value={medicalForm.template_data.doctor_name}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder="ФИО врача" />
              
                </div>
                <div>
                  <label htmlFor="cabinet" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Кабинет</label>
                  <Input
                id="cabinet"
                value={medicalForm.template_data.cabinet}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, cabinet: e.target.value }
                })}
                placeholder="№ кабинета" />
              
                </div>
              </>
          }

            {medicalForm.document_type === 'report' &&
          <>
                <div>
                  <label htmlFor="examination" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Результаты обследования</label>
                  <Textarea
                id="examination"
                value={medicalForm.template_data.examination_results}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, examination_results: e.target.value }
                })}
                placeholder="Введите результаты обследования"
                rows={3} />
              
                </div>
                <div>
                  <label htmlFor="conclusion" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Заключение</label>
                  <Textarea
                id="conclusion"
                value={medicalForm.template_data.conclusion}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, conclusion: e.target.value }
                })}
                placeholder="Введите заключение"
                rows={3} />
              
                </div>
                <div>
                  <label htmlFor="report-doctor" style={{
                display: 'block',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                marginBottom: '8px'
              }}>Врач</label>
                  <Input
                id="report-doctor"
                value={medicalForm.template_data.doctor_name}
                onChange={(e) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder="ФИО врача" />
              
                </div>
              </>
          }
          </div>

          <Button
          onClick={printMedicalDocument}
          style={{ width: '100%', marginTop: '24px' }}
          disabled={!medicalForm.printer_id || !medicalForm.patient_data.patient_name}>
          
            Печать {medicalForm.document_type === 'prescription' ? 'рецепта' :
          medicalForm.document_type === 'receipt' ? 'чека' :
          medicalForm.document_type === 'ticket' ? 'талона' : 'отчета'}
          </Button>
        </MacOSCard>
      </div>
    </div>;


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
        maxWidth: '100%',
        overflowX: 'auto',
        paddingBottom: '6px',
        marginBottom: '24px',
        scrollbarWidth: 'thin'
      }}>
        <SegmentedControl
          aria-label="Разделы облачной печати"
          value={activeTab}
          onChange={setActiveTab}
          options={[
            {
              value: 'printers',
              label: (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <Printer size={14} aria-hidden="true" />
                  Принтеры
                </span>
              )
            },
            {
              value: 'print',
              label: (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <Printer size={14} aria-hidden="true" />
                  Печать документа
                </span>
              )
            },
            {
              value: 'medical',
              label: (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <TestTube size={14} aria-hidden="true" />
                  Медицинские документы
                </span>
              )
            }
          ]}
          size="large"
          style={{
            minWidth: 'max-content',
            background: 'var(--mac-gradient-sidebar)',
            border: '1px solid var(--mac-main-shell-border)',
            borderRadius: '14px',
            boxShadow: 'var(--mac-main-shell-shadow)'
          }} />
      </div>

      {activeTab === 'printers' && renderPrintersTab()}
      {activeTab === 'print' && renderPrintTab()}
      {activeTab === 'medical' && renderMedicalTab()}

      {/* Модальное окно с подробностями принтера */}
      {selectedPrinter &&
      <Modal
        isOpen={!!selectedPrinter}
        onClose={() => setSelectedPrinter(null)}
        title="Подробности принтера">
        
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div><strong>Название:</strong> {selectedPrinter.name}</div>
            <div><strong>Описание:</strong> {selectedPrinter.description}</div>
            <div><strong>Провайдер:</strong> {selectedPrinter.provider}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <strong>Статус:</strong> 
              <Badge variant={getStatusBadgeVariant(selectedPrinter.status)}>
                {getStatusText(selectedPrinter.status)}
              </Badge>
            </div>
            <div><strong>Местоположение:</strong> {selectedPrinter.location || 'Не указано'}</div>
            <div><strong>ID:</strong> {selectedPrinter.id}</div>
            
            {selectedPrinter.capabilities && Object.keys(selectedPrinter.capabilities).length > 0 &&
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
          }
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '24px' }}>
            <Button
            onClick={() => testPrinter(selectedPrinter.provider, selectedPrinter.id)}
            disabled={selectedPrinter.status !== 'online'}>
            
              <TestTube size={16} style={{ marginRight: '8px' }} />
              Тестовая печать
            </Button>
            <Button
            variant="outline"
            onClick={() => setSelectedPrinter(null)}>
            
              <X size={16} style={{ marginRight: '8px' }} />
              Закрыть
            </Button>
          </div>
        </Modal>
      }
    </div>);

};

export default CloudPrintingManager;
