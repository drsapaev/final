```jsx
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { Calendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { FixedSizeList } from 'react-window';
import InputMask from 'react-input-mask';
import { motion, AnimatePresence } from 'framer-motion';
import jsPDF from 'jspdf';
import { debounce } from 'lodash';
import api from './api';

// Контекст для темы
const ThemeContext = React.createContext('light');

// Хуки для API
const usePatients = (searchQuery) => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchPatients = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/patients/?q=${encodeURIComponent(searchQuery)}&limit=100`);
        setPatients(res.data);
      } catch (error) {
        toast.error('Ошибка загрузки пациентов');
      } finally {
        setLoading(false);
      }
    };
    fetchPatients();
  }, [searchQuery]);

  return { patients, loading };
};

const useVisits = (filters) => {
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchVisits = async () => {
      setLoading(true);
      const params = new URLSearchParams({ limit: '50', skip: '0', ...filters });
      try {
        const res = await api.get(`/visits/?${params.toString()}`);
        setVisits(res.data);
      } catch (error) {
        toast.error('Ошибка загрузки записей');
      } finally {
        setLoading(false);
      }
    };
    fetchVisits();
  }, [filters]);

  return { visits, loading };
};

// Компонент таблицы
const MainTable = ({ visits, onRowClick, showAddress }) => {
  const { t } = useTranslation();
  const columns = useMemo(
    () => [
      { key: 'id', label: t('number'), sticky: true, width: 50 },
      { key: 'full_name', label: t('fio'), width: 200 },
      { key: 'date_of_birth', label: t('birth_year'), width: 100, render: (row) => new Date(row.date_of_birth).getFullYear() },
      { key: 'phone_number', label: t('phone'), width: 150, render: (row) => row.phone_number.replace(/(\d{3})(\d{2})(\d{3})(\d{2})(\d{2})/, '+$1 ($2) $3-$4-$5') },
      { key: 'address', label: t('address'), width: 200, hidden: !showAddress },
      { key: 'doctor_name', label: t('specialist'), width: 150, render: (row) => row.doctor?.full_name || 'N/A' },
      { key: 'service_name', label: t('visit_type'), width: 100, render: (row) => row.service?.name || 'N/A' },
      { key: 'services', label: t('services'), width: 200, render: (row) => <ServiceChecklist services={row.services} /> },
      { key: 'payment_type', label: t('payment_type'), width: 100, render: () => 'N/A' }, // Поле не в модели, заглушка
      { key: 'cost', label: t('cost'), width: 100, render: (row) => row.service?.cost || 0 },
      { key: 'status', label: t('status'), width: 100, render: (row) => <StatusBadge status={row.status} /> },
      { key: 'actions', label: t('actions'), sticky: true, width: 150, render: (row) => <Actions row={row} onClick={() => onRowClick(row)} /> },
    ],
    [t, showAddress]
  );

  const Row = ({ index, style }) => {
    if (index >= visits.length) return <tr style={{ ...style, display: 'flex' }} />;
    const row = visits[index];
    return (
      <motion.tr
        style={{ ...style, display: 'flex', background: index % 2 ? '#f8f9fa' : '#fff' }}
        whileHover={{ backgroundColor: '#e3f2fd' }}
        onClick={() => onRowClick(row)}
        role="row"
        className="border-b"
      >
        {columns.map((col) => (
          !col.hidden && (
            <td
              key={col.key}
              style={{ width: col.width, flexShrink: 0, position: col.sticky ? 'sticky' : 'relative', left: col.sticky && col.key === 'id' ? 0 : undefined, right: col.sticky && col.key === 'actions' ? 0 : undefined, padding: '8px' }}
              role="cell"
              className="text-sm"
            >
              {col.render ? col.render(row) : row[col.key] || 'N/A'}
            </td>
          )
        ))}
      </motion.tr>
    );
  };

  return (
    <div className="overflow-x-auto">
      <FixedSizeList height={400} itemCount={visits.length + 5} itemSize={50} width="100%">
        {Row}
      </FixedSizeList>
    </div>
  );
};

// Компонент чек-листа услуг
const ServiceChecklist = ({ services }) => {
  const [selected, setSelected] = useState(services || []);
  return (
    <select
      multiple
      value={selected}
      onChange={(e) => setSelected(Array.from(e.target.selectedOptions, (option) => option.value))}
      className="w-full p-1 border rounded"
    >
      <optgroup label="Дерматология">
        <option value="derm_consult">Консультация</option>
      </optgroup>
      <optgroup label="Кардиология">
        <option value="cardio_consult">Консультация</option>
        <option value="echokg">ЭхоКГ</option>
      </optgroup>
    </select>
  );
};

// Компонент статуса
const StatusBadge = ({ status }) => {
  const colors = {
    planned: '#B0BEC5',
    queued: '#2196F3',
    in_progress: '#FFA500',
    completed: '#4CAF50',
    canceled: '#F44336',
    no_show: '#F44336',
    paid: '#4CAF50',
  };
  return (
    <span
      style={{ background: colors[status] || '#B0BEC5', color: '#fff', padding: '4px 8px', borderRadius: '12px' }}
      role="status"
      className="text-xs"
    >
      {status}
    </span>
  );
};

// Компонент действий
const Actions = ({ row, onClick }) => (
  <div className="flex gap-2">
    <button onClick={() => onClick(row)} aria-label="Открыть детали" className="text-blue-500 hover:text-blue-700">📋</button>
    <button onClick={() => printTicket(row)} aria-label="Печать талона" className="text-green-500 hover:text-green-700">🖨️</button>
  </div>
);

// Компонент сайдбара визита
const VisitSidebar = ({ visit, onClose, onReschedule, onPay }) => {
  const { t } = useTranslation();
  return (
    <AnimatePresence>
      {visit && (
        <motion.div
          initial={{ x: 300, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 300, opacity: 0 }}
          className="fixed right-0 top-0 w-80 h-full bg-white dark:bg-gray-800 shadow-lg p-4 z-50"
          role="dialog"
          aria-modal="true"
        >
          <h2 className="text-lg font-bold mb-4">{t('visit_details')}</h2>
          <p><strong>{t('fio')}:</strong> {visit.full_name}</p>
          <p><strong>{t('phone')}:</strong> {visit.phone_number}</p>
          <p><strong>{t('status')}:</strong> <StatusBadge status={visit.status} /></p>
          <p><strong>{t('specialist')}:</strong> {visit.doctor?.full_name || 'N/A'}</p>
          <p><strong>{t('visit_type')}:</strong> {visit.service?.name || 'N/A'}</p>
          <div className="flex flex-col gap-2 mt-4">
            <button onClick={onPay} className="bg-blue-500 text-white p-2 rounded hover:bg-blue-600">{t('pay')}</button>
            <button onClick={onReschedule} className="bg-green-500 text-white p-2 rounded hover:bg-green-600">{t('reschedule')}</button>
            <button onClick={onClose} className="bg-red-500 text-white p-2 rounded hover:bg-red-600">{t('close')}</button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// Основной компонент
const RegistrarPanel = () => {
  const { t, i18n } = useTranslation();
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');
  const [activeTab, setActiveTab] = useState('visits');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddress, setShowAddress] = useState(false);
  const [filters, setFilters] = useState({ service_id: '', visit_date: '', status: '' });
  const [selectedVisit, setSelectedVisit] = useState(null);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardPatientQuery, setWizardPatientQuery] = useState('');
  const [wizardPatient, setWizardPatient] = useState(null);
  const searchRef = useRef(null);

  const { patients, loading: patientsLoading } = usePatients(searchQuery);
  const { visits, loading: visitsLoading } = useVisits(filters);

  const debouncedSearch = useCallback(debounce((query) => setSearchQuery(query), 300), []);

  // Горячие клавиши
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === 'Enter' && activeTab === 'queue') {
        e.preventDefault();
        printTicket(selectedVisit);
      }
      if (e.key === 'Escape') {
        setSelectedVisit(null);
        setShowWizard(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeTab, selectedVisit]);

  // Локализация
  useEffect(() => {
    i18n.changeLanguage(localStorage.getItem('lang') || 'ru');
  }, [i18n]);

  // Печать талона
  const printTicket = async (visit) => {
    try {
      const res = await api.post('/print/ticket', { visit_id: visit.id, lang: i18n.language });
      toast.success(t('ticket_printed'));
      logAction('print_ticket', 'visit', visit.id, { lang: i18n.language });
    } catch {
      toast.error(t('print_error'));
    }
  };

  // Генерация PDF-квитанции
  const generateReceipt = async (payment) => {
    const doc = new jsPDF();
    doc.setFont('helvetica');
    doc.text(`${t('receipt')} #${payment.id}`, 10, 10);
    doc.text(`${t('amount')}: ${payment.amount} UZS`, 10, 20);
    doc.save(`receipt_${payment.id}.pdf`);
    logAction('generate_receipt', 'payment', payment.id, {});
  };

  // Логирование действий
  const logAction = async (event, entity, entity_id, payload) => {
    try {
      await api.post('/audit_logs', { event, entity, entity_id, payload });
    } catch {
      console.error('Ошибка логирования действия');
    }
  };

  return (
    <ThemeContext.Provider value={theme}>
      <div className={`min-h-screen grid grid-cols-[250px_1fr] ${theme === 'dark' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-900'} ${theme === 'high-contrast' ? 'bg-black text-yellow-400' : ''}`}>
        <ToastContainer position="top-right" autoClose={3000} theme={theme} />
        {/* Sidebar */}
        <motion.div
          initial={{ width: 250 }}
          animate={{ width: showAddress ? 250 : 60 }}
          className="border-r border-gray-200 p-4"
        >
          <button onClick={() => setShowAddress(!showAddress)} className="mb-4 text-2xl">{showAddress ? '◄' : '►'}</button>
          <h3 className="font-bold mb-2">{t('menu')}</h3>
          <ul className="list-none p-0">
            <li><button onClick={() => setActiveTab('visits')} className={`w-full text-left p-2 rounded ${activeTab === 'visits' ? 'bg-blue-500 text-white' : ''}`}>{t('visits')}</button></li>
            <li><button onClick={() => setActiveTab('calendar')} className={`w-full text-left p-2 rounded ${activeTab === 'calendar' ? 'bg-blue-500 text-white' : ''}`}>{t('calendar')}</button></li>
            <li><button onClick={() => setActiveTab('queue')} className={`w-full text-left p-2 rounded ${activeTab === 'queue' ? 'bg-blue-500 text-white' : ''}`}>{t('queue')}</button></li>
            <li><button onClick={() => setShowWizard(true)} className="w-full text-left p-2 rounded bg-green-500 text-white">{t('new_record')}</button></li>
          </ul>
          <select
            onChange={(e) => { setTheme(e.target.value); localStorage.setItem('theme', e.target.value); }}
            className="mt-4 w-full p-2 border rounded"
          >
            <option value="light">{t('light_theme')}</option>
            <option value="dark">{t('dark_theme')}</option>
            <option value="high-contrast">{t('high_contrast')}</option>
          </select>
        </motion.div>
        {/* Main */}
        <div>
          {/* Header */}
          <div className="flex justify-between p-4 bg-blue-500 text-white">
            <img src="/logo.png" alt="Logo" className="h-8" />
            <div className="flex gap-2">
              <InputMask
                mask="+999 (99) 999-99-99"
                value={searchQuery}
                onChange={(e) => debouncedSearch(e.target.value)}
                placeholder={t('search')}
                inputRef={searchRef}
                className="p-2 rounded border"
              />
              <select
                onChange={(e) => { i18n.changeLanguage(e.target.value); localStorage.setItem('lang', e.target.value); }}
                className="p-2 rounded border"
              >
                <option value="ru">Русский</option>
                <option value="uz">O'zbek</option>
              </select>
            </div>
          </div>
          {/* Tabs */}
          <div className="flex gap-2 p-2 bg-gray-200">
            {['visits', 'cardiologist', 'dermatologist', 'dentist', 'lab'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded ${activeTab === tab ? 'bg-blue-500 text-white' : 'bg-white text-gray-900'}`}
              >
                {t(tab)}
              </button>
            ))}
          </div>
          {/* Content */}
          {activeTab === 'visits' && (
            <MainTable
              visits={visits}
              onRowClick={setSelectedVisit}
              showAddress={showAddress}
            />
          )}
          {activeTab === 'calendar' && (
            <Calendar
              localizer={momentLocalizer(moment)}
              events={visits.map(v => ({ start: new Date(v.visit_date), end: new Date(v.visit_date), title: v.full_name, status: v.status }))}
              views={['month', 'week', 'day']}
              className="h-[500px] m-4"
              eventPropGetter={(event) => ({ style: { backgroundColor: event.status === 'completed' ? '#4CAF50' : '#2196F3' } })}
            />
          )}
          {activeTab === 'queue' && <QueueManager />}
          <VisitSidebar
            visit={selectedVisit}
            onClose={() => setSelectedVisit(null)}
            onReschedule={() => {/* Реализация переноса */}}
            onPay={() => generateReceipt({ id: selectedVisit?.id, amount: selectedVisit?.service?.cost || 0 })}
          />
          {showWizard && (
            <WizardModal
              step={wizardStep}
              setStep={setWizardStep}
              patientQuery={wizardPatientQuery}
              setPatientQuery={setWizardPatientQuery}
              patient={wizardPatient}
              setPatient={setWizardPatient}
              onClose={() => setShowWizard(false)}
            />
          )}
        </div>
      </div>
    </ThemeContext.Provider>
  );
};

// Компонент очереди
const QueueManager = () => {
  const { t } = useTranslation();
  const [queueDate, setQueueDate] = useState(new Date().toISOString().split('T')[0]);
  const [queueService, setQueueService] = useState('');
  const [queueStatus, setQueueStatus] = useState(null);

  useEffect(() => {
    if (queueService && queueDate) {
      api.get(`/visits/?service_id=${queueService}&visit_date=${queueDate}`)
        .then(res => setQueueStatus({ is_open: res.data.length > 0 }))
        .catch(() => toast.error(t('network_error')));
    }
  }, [queueService, queueDate, t]);

  const toggleQueue = async () => {
    try {
      await api.post('/queue/toggle', { service_id: queueService, date: queueDate });
      setQueueStatus({ is_open: !queueStatus.is_open });
      toast.success(t(queueStatus.is_open ? 'queue_closed' : 'queue_opened'));
    } catch {
      toast.error(t('network_error'));
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">{t('queue_management')}</h2>
      <input
        type="date"
        value={queueDate}
        onChange={(e) => setQueueDate(e.target.value)}
        className="p-2 border rounded mr-2"
      />
      <select
        value={queueService}
        onChange={(e) => setQueueService(e.target.value)}
        className="p-2 border rounded"
      >
        <option value="">{t('select_service')}</option>
        <option value="cardio_consult">Кардиология</option>
        <option value="derm_consult">Дерматология</option>
        <option value="dental">Стоматология</option>
      </select>
      {queueStatus && (
        <div className="mt-4">
          <p>{t('status')}: {queueStatus.is_open ? t('open') : t('closed')}</p>
          <button onClick={toggleQueue} className={`p-2 rounded ${queueStatus.is_open ? 'bg-red-500' : 'bg-green-500'} text-white`}>
            {queueStatus.is_open ? t('close_queue') : t('open_queue')}
          </button>
        </div>
      )}
    </div>
  );
};

// Компонент wizard
const WizardModal = ({ step, setStep, patientQuery, setPatientQuery, patient, setPatient, onClose }) => {
  const { t } = useTranslation();
  const { patients, loading } = usePatients(patientQuery);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg w-[400px]">
        <h2 className="text-lg font-bold mb-4">{t('new_record')}</h2>
        {step === 1 && (
          <div>
            <InputMask
              mask="+999 (99) 999-99-99"
              value={patientQuery}
              onChange={(e) => setPatientQuery(e.target.value)}
              placeholder={t('search_patient')}
              className="w-full p-2 border rounded mb-2"
            />
            {loading ? (
              <p>{t('loading')}</p>
            ) : (
              patients.map(p => (
                <div
                  key={p.id}
                  onClick={() => { setPatient(p); setStep(2); }}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
                >
                  {p.full_name}
                </div>
              ))
            )}
          </div>
        )}
        {step === 2 && (
          <div>
            <p><strong>{t('fio')}:</strong> {patient.full_name}</p>
            <button
              onClick={async () => {
                try {
                  await api.post('/visits', { patient_id: patient.id, service_id: 'derm_consult', visit_date: new Date().toISOString(), status: 'planned' });
                  toast.success(t('visit_created'));
                  setShowWizard(false);
                } catch {
                  toast.error(t('network_error'));
                }
              }}
              className="bg-green-500 text-white p-2 rounded mt-4"
            >
              {t('create_visit')}
            </button>
          </div>
        )}
        <button onClick={onClose} className="bg-red-500 text-white p-2 rounded mt-2">{t('close')}</button>
      </div>
    </motion.div>
  );
};

export default RegistrarPanel;
```