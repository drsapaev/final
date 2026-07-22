import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
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
  microsoft: 'Microsoft Universal Print',
  google: 'Google Cloud Print',
  local: 'Local Print Gateway'
};

const getProviderLabel = (provider, t) => {
  if (provider === 'mock') return `Mock (${t('admin2.cp_provider_mock')})`;
  return PROVIDER_LABELS[provider] || provider;
};

const getStatusText = (status, t) => {
  switch (status) {
    case 'online': return t('admin2.cp_status_online');
    case 'busy': return t('admin2.cp_status_busy');
    case 'offline': return t('admin2.cp_status_offline');
    case 'error': return t('admin2.cp_status_error');
    default: return status || t('admin2.cp_status_unknown');
  }
};

const getProviderOptions = (providers = [], t) =>
  providers.map((provider) => ({
    value: provider,
    label: getProviderLabel(provider, t)
  }));

const getPrinterOptions = (printers = [], providerName = '', t) =>
  printers
    .filter((printer) => printer.provider === providerName)
    .map((printer) => ({
      value: printer.id,
      label: `${printer.name} (${getStatusText(printer.status, t)})`
    }));

const normalizeLocalPrinter = (printer, t) => ({
  id: printer.name || String(printer.id),
  name: printer.display_name || printer.name || t('admin2.cp_local_printer'),
  description:
    [
      printer.printer_type ? `${printer.printer_type}` : null,
      printer.connection_type ? `${t('admin2.cp_connection')}: ${printer.connection_type}` : null
    ]
      .filter(Boolean)
      .join(' • ') || t('admin2.cp_local_system_printer'),
  status: printer.status || null,
  location: printer.device_path || printer.location || t('admin2.cp_local_computer'),
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
        (printer) => normalizeLocalPrinter(printer, t)
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
      toast.error(t('admin2.cp_load_printers_failed'));
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = (await api.get('/cloud-printing/statistics')) as import('axios').AxiosResponse<Record<string, unknown>>;
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

      if (response.data?.success || response.data?.status === 'printed' || String(response.data?.message ?? '')) {
        toast.success(t('admin2.cp_test_print_sent'));
      } else {
        toast.error(String(response.data?.message ?? '') || t('admin2.cp_test_print_error'));
      }
    } catch (error) {
      logger.error('Ошибка тестовой печати:', error);
      toast.error(error.response?.data?.detail || t('admin2.cp_test_print_error'));
    }
  };

  const printDocument = async () => {
    if (!printForm.printer_id || !printForm.title || !printForm.content) {
      toast.error(t('admin2.cp_fill_required_fields_all'));
      return;
    }

    try {
      const response = (await api.post('/cloud-printing/print', printForm)) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data?.success) {
        toast.success(t('admin2.cp_document_sent'));
        setPrintForm({
          ...printForm,
          title: '',
          content: ''
        });
      } else {
        toast.error(String(response.data?.message ?? '') || t('admin2.cp_print_error'));
      }
    } catch (error) {
      logger.error('Ошибка печати:', error);
      toast.error(error.response?.data?.detail || t('admin2.cp_medical_print_error'));
    }
  };

  const printMedicalDocument = async () => {
    if (!medicalForm.printer_id || !medicalForm.patient_data.patient_name) {
      toast.error(t('admin2.cp_fill_required_fields'));
      return;
    }

    try {
      const response = (await api.post('/cloud-printing/print/medical', medicalForm)) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data?.success) {
        toast.success(t('admin2.cp_medical_document_sent'));
      } else {
        toast.error(String(response.data?.message ?? '') || t('admin2.cp_print_error'));
      }
    } catch (error) {
      logger.error('Ошибка печати медицинского документа:', error);
      toast.error(t('admin2.cp_medical_print_error'));
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
                {getStatusText(printer.status, t)}
              </Badge>
            </div>

            <div className="admin-data-list-sm">
              <div><strong>{t('admin2.cp_provider')}:</strong> {printer.provider}</div>
              <div><strong>{t('admin2.cp_location')}:</strong> {printer.location || t('admin2.cp_not_specified')}</div>
              <div><strong>{t('admin2.cp_id')}:</strong> {printer.id}</div>
              {printer.provider === 'local' &&
              <div><strong>{t('admin2.cp_type')}:</strong> {printer.printer_type || 'unknown'}</div>
              }
            </div>

            <div className="admin-action-row-mt-16-gap-8">
              <Button
                size="small"
                onClick={() => testPrinter(printer.provider, printer.id)}
                disabled={printer.status !== 'online'}>

                <TestTube size={16} className="mr-1" />
                {t('admin2.cp_test_button')}
              </Button>
              <Button
                size="small"
                variant="outline"
                onClick={() => setSelectedPrinter(printer)}>

                <Eye size={16} className="mr-1" />
                {t('admin2.cp_view_details')}
              </Button>
            </div>
          </MacOSCard>
        )}
      </div>

      {list.length === 0 && !loading &&
      <AppEmpty
        icon={Printer}
        title={emptyTitle}
        description={t('admin2.cp_empty_printers_desc')} />
      }
    </>;

  const renderPrintersTab = () =>
  <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h3 className="admin-section-h3-m0">{t('admin2.cp_printers_title')}</h3>
        <Button onClick={loadPrinters} disabled={loading}>
          <RefreshCw size={16} className="mr-2" />
          {loading ? t('admin2.cp_loading') : t('admin2.cp_refresh')}
        </Button>
      </div>

        {statistics &&
    <div className="admin-grid-auto-200-mb-24-printing">
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-accent">{statistics.total_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">{t('admin2.cp_stat_total_printers')}</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-success">{statistics.online_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">{t('admin2.cp_stat_online')}</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-destructive">{statistics.offline_printers}</div>
            <div className="admin-stat-label-sm-secondary-block">{t('admin2.cp_stat_offline')}</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-warning">{statistics.providers_count}</div>
            <div className="admin-stat-label-sm-secondary-block">{t('admin2.cp_stat_providers')}</div>
          </MacOSCard>
          <MacOSCard className="p-6">
            <div className="admin-stat-num-2xl-bold-dynamic admin-stat-accent">{localPrinters.length}</div>
            <div className="admin-stat-label-sm-secondary-block">{t('admin2.cp_stat_local_printers')}</div>
          </MacOSCard>
        </div>
    }

      <div className="admin-grid-gap-24-only">
        <div className="admin-grid-gap-12-only">
          <h4 className="admin-h4-md-semi-primary-m0">{t('admin2.cp_cloud_printers')}</h4>
          {renderPrinterGrid(printers, t('admin2.cp_cloud_printers_empty'))}
        </div>

        <div className="admin-grid-gap-12-only">
          <h4 className="admin-h4-md-semi-primary-m0">{t('admin2.cp_local_os_printers')}</h4>
          {renderPrinterGrid(localPrinters, t('admin2.cp_local_printers_empty'))}
        </div>
      </div>
    </div>;


  const renderPrintTab = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">{t('admin2.cp_print_document_title')}</h3>
      
      <div className="admin-grid-auto-400-24">
        <MacOSCard className="p-6">
          <h4 className="admin-h4-lg-semi-primary-mb-16">{t('admin2.cp_print_settings')}</h4>
          
          <div className="flex flex-col gap-4">
            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="provider">{t('admin2.cp_provider_label')}</label>
              <Select
              id="provider"
              value={printForm.provider_name}
              onChange={(value) => setPrintForm({
                ...printForm,
                provider_name: String(value),
                printer_id: ''
              })}
              options={[
                { value: '', label: t('admin2.cp_select_provider') },
                ...getProviderOptions(providers, t)
              ]}
              size="large" />
            
            </div>

            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="printer">{t('admin2.cp_printer_label')}</label>
              <Select
              id="printer"
              value={printForm.printer_id}
              onChange={(value: unknown) => setPrintForm({ ...printForm, printer_id: String(value) })}
              options={[
              { value: '', label: t('admin2.cp_select_printer') },
              ...getPrinterOptions(printers, printForm.provider_name, t)]
              }
              size="large" />
            
            </div>

            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="title">{t('admin2.cp_document_title_label')}</label>
              <Input
              id="title"
              value={printForm.title}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPrintForm({ ...printForm, title: e.target.value })}
              placeholder={t('admin2.cp_document_title_placeholder')} />
            
            </div>

            <div>
              <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="format">{t('admin2.cp_format_label')}</label>
              <Select
              id="format"
              value={printForm.format}
              onChange={(value: unknown) => setPrintForm({ ...printForm, format: String(value) })}
              options={[
              { value: 'html', label: 'HTML' },
              { value: 'text', label: t('admin2.cp_format_text') },
              { value: 'pdf', label: 'PDF' }]
              }
              size="large" />
            
            </div>

            <div className="admin-grid-3col-16">
              <div>
                <label className="admin-label-block-sm-med-primary-mb-8" htmlFor="copies">{t('admin2.cp_copies_label')}</label>
                <Input
                id="copies"
                type="number"
                min="1"
                max="10"
                value={printForm.copies}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPrintForm({ ...printForm, copies: parseInt(e.target.value) })} />
              
              </div>
              <div className="flex items-center justify-center gap-2">
                <Checkbox id="color" aria-label="Enable color printing" checked={printForm.color} onChange={(checked: boolean) => setPrintForm({ ...printForm, color: checked })}
                className="admin-checkbox-m0" />
              
                <label className="admin-label-block-sm-primary" htmlFor="color">{t('admin2.cp_color')}</label>
              </div>
              <div className="flex items-center justify-center gap-2">
                <Checkbox id="duplex" aria-label="Enable duplex printing" checked={printForm.duplex} onChange={(checked: boolean) => setPrintForm({ ...printForm, duplex: checked })}
                className="admin-checkbox-m0" />
              
                <label className="admin-label-block-sm-primary" htmlFor="duplex">{t('admin2.cp_duplex')}</label>
              </div>
            </div>
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <h4 className="admin-h4-lg-semi-primary-mb-16">{t('admin2.cp_document_content')}</h4>
          
          <Textarea
          value={printForm.content}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setPrintForm({ ...printForm, content: e.target.value })}
          placeholder={t('admin2.cp_content_placeholder')}
          rows={15}
          className="w-full" />
        
          
          <Button
          onClick={printDocument}
          className="admin-btn-w-full-mt-16"
          disabled={!printForm.printer_id || !printForm.title || !printForm.content}>
          
            <Printer size={16} className="mr-2" />
            {t('admin2.cp_print_button')}
          </Button>
        </MacOSCard>
      </div>
    </div>;


  const renderMedicalTab = () =>
  <div className="flex flex-col gap-6">
      <h3 className="admin-section-h3-m0">{t('admin2.cp_medical_documents_title')}</h3>
      
      <div className="admin-grid-auto-400-24">
        <MacOSCard className="p-6">
          <h4 className="admin-h4-md-semi-primary-mb-16">{t('admin2.cp_main_settings')}</h4>
          
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="med-provider" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_provider_label')}</label>
              <Select
              id="med-provider"
              value={medicalForm.provider_name}
              onChange={(value) => setMedicalForm({
                ...medicalForm,
                provider_name: String(value),
                printer_id: ''
              })}
              options={[
                { value: '', label: t('admin2.cp_select_provider') },
                ...getProviderOptions(providers, t)
              ]}
              size="large" />
            </div>

            <div>
              <label htmlFor="med-printer" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_printer_label')}</label>
              <Select
              id="med-printer"
              value={medicalForm.printer_id}
              onChange={(value: unknown) => setMedicalForm({ ...medicalForm, printer_id: String(value) })}
              options={[
                { value: '', label: t('admin2.cp_select_printer') },
                ...getPrinterOptions(printers, medicalForm.provider_name, t)
              ]}
              size="large" />
            </div>

            <div>
              <label htmlFor="doc-type" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_doc_type_label')}</label>
              <Select
              id="doc-type"
              value={medicalForm.document_type}
              onChange={(value: unknown) => setMedicalForm({ ...medicalForm, document_type: String(value) })}
              options={[
                { value: 'prescription', label: t('admin2.cp_doc_type_prescription') },
                { value: 'receipt', label: t('admin2.cp_doc_type_receipt') },
                { value: 'ticket', label: t('admin2.cp_doc_type_ticket') },
                { value: 'report', label: t('admin2.cp_doc_type_report') }
              ]}
              size="large" />
            </div>

            <h5 className="admin-h5-md-med-primary-mt-24-mb-16">{t('admin2.cp_patient_data_title')}</h5>
            <div>
              <label htmlFor="patient-name" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_patient_name_label')}</label>
              <Input
              id="patient-name"
              value={medicalForm.patient_data.patient_name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                ...medicalForm,
                patient_data: { ...medicalForm.patient_data, patient_name: e.target.value }
              })}
              placeholder={t('admin2.cp_patient_name_placeholder')} />
            </div>

            <div className="admin-grid-2col-16">
              <div>
                <label htmlFor="patient-age" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_patient_age_label')}</label>
                <Input
                id="patient-age"
                value={medicalForm.patient_data.age}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  patient_data: { ...medicalForm.patient_data, age: e.target.value }
                })}
                placeholder={t('admin2.cp_patient_age_placeholder')} />
              </div>
              <div>
                <label htmlFor="patient-phone" className="admin-label-block-sm-med-primary-mb-8">{t('common.phone')}</label>
                <Input
                id="patient-phone"
                value={medicalForm.patient_data.phone}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  patient_data: { ...medicalForm.patient_data, phone: e.target.value }
                })}
                placeholder="+998901234567" />
              </div>
            </div>
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <h4 className="admin-h4-md-semi-primary-mb-16">{t('admin2.cp_template_data_title')}</h4>
          
          <div className="flex flex-col gap-4">
            {medicalForm.document_type === 'prescription' &&
          <>
                <div>
                  <label htmlFor="diagnosis" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_diagnosis_label')}</label>
                  <Input
                id="diagnosis"
                value={medicalForm.template_data.diagnosis}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, diagnosis: e.target.value }
                })}
                placeholder={t('admin2.cp_diagnosis_placeholder')} />
                </div>
                <div>
                  <label htmlFor="prescription" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_prescription_label')}</label>
                  <Textarea
                id="prescription"
                value={medicalForm.template_data.prescription_text}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, prescription_text: e.target.value }
                })}
                placeholder={t('admin2.cp_prescription_placeholder')}
                rows={4} />
                </div>
                <div>
                  <label htmlFor="doctor" className="admin-label-block-sm-med-primary-mb-8">{t('common.doctor')}</label>
                  <Input
                id="doctor"
                value={medicalForm.template_data.doctor_name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder={t('admin2.cp_doctor_name_placeholder')} />
                </div>
              </>
          }

            {medicalForm.document_type === 'ticket' &&
          <>
                <div>
                  <label htmlFor="queue-number" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_queue_number_label')}</label>
                  <Input
                id="queue-number"
                value={medicalForm.template_data.queue_number}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
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
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder={t('admin2.cp_doctor_name_placeholder')} />
                </div>
                <div>
                  <label htmlFor="cabinet" className="admin-label-block-sm-med-primary-mb-8">{t('common.cabinet')}</label>
                  <Input
                id="cabinet"
                value={medicalForm.template_data.cabinet}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, cabinet: e.target.value }
                })}
                placeholder={t('admin2.cp_cabinet_placeholder')} />
                </div>
              </>
          }

            {medicalForm.document_type === 'report' &&
          <>
                <div>
                  <label htmlFor="examination" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_exam_results_label')}</label>
                  <Textarea
                id="examination"
                value={medicalForm.template_data.examination_results}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, examination_results: e.target.value }
                })}
                placeholder={t('admin2.cp_exam_results_placeholder')}
                rows={3} />
                </div>
                <div>
                  <label htmlFor="conclusion" className="admin-label-block-sm-med-primary-mb-8">{t('admin2.cp_conclusion_label')}</label>
                  <Textarea
                id="conclusion"
                value={medicalForm.template_data.conclusion}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, conclusion: e.target.value }
                })}
                placeholder={t('admin2.cp_conclusion_placeholder')}
                rows={3} />
                </div>
                <div>
                  <label htmlFor="report-doctor" className="admin-label-block-sm-med-primary-mb-8">{t('common.doctor')}</label>
                  <Input
                id="report-doctor"
                value={medicalForm.template_data.doctor_name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMedicalForm({
                  ...medicalForm,
                  template_data: { ...medicalForm.template_data, doctor_name: e.target.value }
                })}
                placeholder={t('admin2.cp_doctor_name_placeholder')} />
                </div>
              </>
          }
          </div>

          <Button
          onClick={printMedicalDocument}
          className="admin-btn-w-full-mt-24"
          disabled={!medicalForm.printer_id || !medicalForm.patient_data.patient_name}>
          
            {medicalForm.document_type === 'prescription' ? t('admin2.cp_print_prescription') :
          medicalForm.document_type === 'receipt' ? t('admin2.cp_print_receipt') :
          medicalForm.document_type === 'ticket' ? t('admin2.cp_print_ticket') : t('admin2.cp_print_report')}
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
            {t('admin2.cp_page_title')}
          </h2>
          <p className="admin-header-p-mt-4-sm-secondary">
            {t('admin2.cp_page_subtitle')}
          </p>
        </div>
      </div>

      {/* Табы */}
      <div className="admin-tabs-scroller">
        <SegmentedControl
          aria-label={t('admin2.cp_tabs_aria')}
          value={activeTab}
          onChange={(v: unknown) => setActiveTab(String(v))}
          options={[
            {
              value: 'printers',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <Printer size={14} aria-hidden="true" />
                  {t('admin2.cp_tab_printers')}
                </span>
              )
            },
            {
              value: 'print',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <Printer size={14} aria-hidden="true" />
                  {t('admin2.cp_print_document_title')}
                </span>
              )
            },
            {
              value: 'medical',
              label: (
                <span className="admin-span-inline-flex-center-8">
                  <TestTube size={14} aria-hidden="true" />
                  {t('admin2.cp_tab_medical')}
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
        title={t('admin2.cp_printer_details_title')}>
        
          <div className="flex flex-col gap-3">
            <div><strong>{t('admin2.cp_name_label')}:</strong> {selectedPrinter.name}</div>
            <div><strong>{t('admin2.cp_description_label')}:</strong> {selectedPrinter.description}</div>
            <div><strong>{t('admin2.cp_provider')}:</strong> {selectedPrinter.provider}</div>
            <div className="flex items-center justify-center gap-2">
              <strong>{t('admin2.cp_status_label')}:</strong> 
              <Badge variant={getStatusBadgeVariant(selectedPrinter.status)}>
                {getStatusText(selectedPrinter.status, t)}
              </Badge>
            </div>
            <div><strong>{t('admin2.cp_location')}:</strong> {selectedPrinter.location || t('admin2.cp_not_specified')}</div>
            <div><strong>{t('admin2.cp_id')}:</strong> {selectedPrinter.id}</div>
            
            {selectedPrinter.capabilities && Object.keys(selectedPrinter.capabilities).length > 0 &&
          <div>
                <strong>{t('admin2.cp_capabilities_label')}:</strong>
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
              {t('admin2.cp_test_print_button')}
            </Button>
            <Button
            variant="outline"
            onClick={() => setSelectedPrinter(null)}>
            
              <X size={16} className="mr-2" />
              {t('admin2.cp_close_button')}
            </Button>
          </div>
        </Modal>
      }
    </div>);

};

export default CloudPrintingManager;
