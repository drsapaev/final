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
  Checkbox } from '../ui/macos';
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
import { useTranslation } from '../../i18n/useTranslation';

const PROVIDER_LABELS = {
  mock: 'Mock (Тестовый)',
  microsoft: 'Microsoft Universal Print',
  google: 'Google Cloud Print',
  local: 'Local Print Gateway'
};

const getProviderLabel = (provider) => PROVIDER_LABELS[provider] || provider;

const getStatusText = (status) => {
  const { t } = useTranslation();
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
      <div className="admin-grid-auto-300">
        {list.map((printer) =>
          <MacOSCard key={`${printer.provider}-${printer.id}`} className="p-4">
            <div className="admin-flex-between-flex-start-mb-12">
              <div>
                <h4 className="admin-h4-semi-mb-4-primary">{printer.name}</h4>
                <p className="admin-p-m0-sm-secondary">{printer.description}</p>
              </div>
              <Badge variant={getStatusBadgeVariant(printer.status)}>
                {getStatusText(printer.status)}
              </Badge>
            </div>

            <div className="admin-data-list-sm">
              <div><strong>Провайдер:</strong> {printer.provider}</div>
              <div><strong>Местоположение:</strong> {printer.location || 'Не указано'}</div>
              <div><strong>ID:</strong> {printer.id}</div>
              {printer.provider === 'local' &&
              <div><strong>Тип:</strong> {printer.printer_type || 'unknown'}</div>
              }
            </div>

            <div className="admin-action-row-mt-16-gap-8">
              <Button
                size="sm"
                onClick={() => testPrinter(printer.provider, printer.id)}
                disabled={printer.status !== 'online'}>

                <TestTube size={16} className="mr-1" />
                Тест
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectedPrinter(printer)}>

                <Eye size={16} className="mr-1" />
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
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">Принтеры</h3>
        <Button onClick={loadPrinters} disabled={loading}>
          <RefreshCw size={16} className="mr-2" />
          {loading ? 'Загрузка...' : 'Обновить'}
        </Button>
      </div>

        {statistics &&
    <div className="admin-grid-auto-200-mb-24-printing">
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-accent">{statistics.total_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">Всего принтеров</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-success">{statistics.online_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">В сети</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-destructive">{statistics.offline_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">Не в сети</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-warning">{statistics.providers_count}</div>
            <div className="admin-stat-label-sm-secondary-block">Провайдеров</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-accent">{localPrinters.length}</div>
            <div className="admin-stat-label-sm-secondary-block">Локальных ОС-принтеров</div>
          </MacOSCard>
        </div>
    }

      <div className="admin-grid-gap-24-only">
        <div className="admin-grid-gap-12-only">
          <h4 className="admin-h4-md-semi-primary-m0">Облачные принтеры</h4>
          {renderPrinterGrid(printers, 'Принтеры не найдены')}
        </div>

        <div className="admin-grid-gap-12-only">
          <h4 className="admin-h4-md-semi-primary-m0">Локальные ОС-принтеры</h4>
          {renderPrinterGrid(localPrinters, 'Локальные принтеры не найдены')}
        </div>
      </div>
    </div>;


  const renderPrintTab = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">Печать документа</h3>
      
      <div className="admin-grid-auto-400-24">
        <MacOSCard className="p-6">
          <h4 className="admin-h4-lg-semi-primary-mb-16">Настройки печати</h4>
          
          <div className="flex flex-col gap-4">
            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="provider">Провайдер</label>
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
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="printer">Принтер</label>
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
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="title">Название документа</label>
              <Input
              id="title"
              value={printForm.title}
              onChange={(e) => setPrintForm({ ...printForm, title: e.target.value })}
              placeholder="Введите название документа" />
            
            </div>

            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="format">Формат</label>
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

            <div className="admin-grid-3col-16">
              <div>
                <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="copies">Копии</label>
                <Input
                id="copies"
                type="number"
                min="1"
                max="10"
                value={printForm.copies}
                onChange={(e) => setPrintForm({ ...printForm, copies: parseInt(e.target.value) })} />
              
              </div>
              <div className="flex items-center justify-center gap-2">
                <Checkbox id="color" aria-label="Enable color printing" checked={printForm.color} onChange={(e) => setPrintForm({ ...printForm, color: e.target.checked })}
                className="admin-checkbox-m0" />
              
                <label className="admin-label-block-sm-primary" htmlFor="color">Цветная</label>
              </div>
              <div className="flex items-center justify-center gap-2">
                <Checkbox id="duplex" aria-label="Enable duplex printing" checked={printForm.duplex} onChange={(e) => setPrintForm({ ...printForm, duplex: e.target.checked })}
                className="admin-checkbox-m0" />
              
                <label className="admin-label-block-sm-primary" htmlFor="duplex">Двусторонняя</label>
              </div>
            </div>
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <h4 className="admin-h4-lg-semi-primary-mb-16">Содержимое документа</h4>
          
          <Textarea
          value={printForm.content}
          onChange={(e) => setPrintForm({ ...printForm, content: e.target.value })}
          placeholder="Введите содержимое документа (HTML, текст или base64 для PDF)"
          rows={15}
          className="w-full" />
        
          
          <Button
          onClick={printDocument}
          className="admin-btn-w-full-mt-16"
          disabled={!printForm.printer_id || !printForm.title || !printForm.content}>
          
            <Printer size={16} className="mr-2" />
            Печать
          </Button>
        </MacOSCard>
      </div>
    </div>;


  const renderMedicalTab = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">Печать медицинских документов</h3>
      
      <div className="admin-grid-auto-400-24">
        <MacOSCard className="p-6">
          <h4 className="admin-h4-md-semi-primary-mb-16">Основные настройки</h4>
          
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="med-provider" className="admin-label-block-sm-med-primary-mb-8">Провайдер</label>
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
              <label htmlFor="med-printer" className="admin-label-block-sm-med-primary-mb-8">Принтер</label>
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
              <label htmlFor="doc-type" className="admin-label-block-sm-med-primary-mb-8">Тип документа</label>
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

            <h5 className="admin-h5-md-med-primary-mt-24-mb-16">Данные пациента</h5>
            <div>
              <label htmlFor="patient-name" className="admin-label-block-sm-med-primary-mb-8">ФИО пациента *</label>
              <Input
              id="patient-name"
              value={medicalForm.patient_data.patient_name}
              onChange={(e) => setMedicalForm({
                ...medicalForm,
                patient_data: { ...medicalForm.patient_data, patient_name: e.target.value }
              })}
              placeholder="Введите ФИО пациента" />
            </div>

            <div className="admin-grid-2col-16">
              <div>
                <label htmlFor="patient-age" className="admin-label-block-sm-med-primary-mb-8">Возраст</label>
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
                <label htmlFor="patient-phone" className="admin-label-block-sm-med-primary-mb-8">{t('common.phone')}</label>
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

        <MacOSCard className="p-6">
          <h4 className="admin-h4-md-semi-primary-mb-16">Данные шаблона</h4>
          
          <div className="flex flex-col gap-4">
            {medicalForm.document_type === 'prescription' &&
          <>
                <div>
                  <label htmlFor="diagnosis" className="admin-label-block-sm-med-primary-mb-8">Диагноз</label>
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
                  <label htmlFor="prescription" className="admin-label-block-sm-med-primary-mb-8">Назначение</label>
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
                  <label htmlFor="doctor" className="admin-label-block-sm-med-primary-mb-8">{t('common.doctor')}</label>
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
                  <label htmlFor="queue-number" className="admin-label-block-sm-med-primary-mb-8">Номер очереди</label>
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
                  <label htmlFor="ticket-doctor" className="admin-label-block-sm-med-primary-mb-8">{t('common.doctor')}</label>
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
                  <label htmlFor="cabinet" className="admin-label-block-sm-med-primary-mb-8">{t('common.cabinet')}</label>
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
                  <label htmlFor="examination" className="admin-label-block-sm-med-primary-mb-8">Результаты обследования</label>
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
                  <label htmlFor="conclusion" className="admin-label-block-sm-med-primary-mb-8">Заключение</label>
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
                  <label htmlFor="report-doctor" className="admin-label-block-sm-med-primary-mb-8">{t('common.doctor')}</label>
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
          className="admin-btn-w-full-mt-24"
          disabled={!medicalForm.printer_id || !medicalForm.patient_data.patient_name}>
          
            Печать {medicalForm.document_type === 'prescription' ? 'рецепта' :
          medicalForm.document_type === 'receipt' ? 'чека' :
          medicalForm.document_type === 'ticket' ? 'талона' : 'отчета'}
          </Button>
        </MacOSCard>
      </div>
    </div>;


  return (
    <div className="admin-page-container">
      <div className="admin-header-flex-16-mb-24-printing">
        <Printer size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-h2-xl-bold-primary-m0">
            Облачная печать
          </h2>
          <p className="admin-header-p-mt-4-sm-secondary">
            Управление принтерами и печать документов через облачные сервисы
          </p>
        </div>
      </div>

      {/* Табы */}
      <div className="admin-tabs-scroller">
        <SegmentedControl
          aria-label="Разделы облачной печати"
          value={activeTab}
          onChange={setActiveTab}
          options={[
            {
              value: 'printers',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <Printer size={14} aria-hidden="true" />
                  Принтеры
                </span>
              )
            },
            {
              value: 'print',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <Printer size={14} aria-hidden="true" />
                  Печать документа
                </span>
              )
            },
            {
              value: 'medical',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <TestTube size={14} aria-hidden="true" />
                  Медицинские документы
                </span>
              )
            }
          ]}
          size="large"
          className="admin-segmented-sidebar" />
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
        
          <div className="flex flex-col gap-3">
            <div><strong>Название:</strong> {selectedPrinter.name}</div>
            <div><strong>Описание:</strong> {selectedPrinter.description}</div>
            <div><strong>Провайдер:</strong> {selectedPrinter.provider}</div>
            <div className="flex items-center justify-center gap-2">
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
                <pre className="admin-pre-block-mt-4">
                  {JSON.stringify(selectedPrinter.capabilities, null, 2)}
                </pre>
              </div>
          }
          </div>

          <div className="admin-modal-footer-flex-8-mt-24">
            <Button
            onClick={() => testPrinter(selectedPrinter.provider, selectedPrinter.id)}
            disabled={selectedPrinter.status !== 'online'}>
            
              <TestTube size={16} className="mr-2" />
              Тестовая печать
            </Button>
            <Button
            variant="outline"
            onClick={() => setSelectedPrinter(null)}>
            
              <X size={16} className="mr-2" />
              Закрыть
            </Button>
          </div>
        </Modal>
      }
    </div>);

};

export default CloudPrintingManager;
