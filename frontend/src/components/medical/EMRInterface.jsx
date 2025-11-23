import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  Input,
  Alert,
  CircularProgress,
  Badge,
  Select,
  Toast,
  ToastContainer
} from '../ui/macos';
import {
  Plus,
  Edit,
  Trash2,
  Search,
  RefreshCw,
  User,
  Stethoscope,
  FileText,
  History,
  ClipboardList,
  Pill,
  Hospital,
  Brain,
  Eye,
  Download,
  Printer,
  Share,
  ChevronDown,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Activity,
  MessageSquare,
  Heart,
  Delete
} from 'lucide-react';

const EMRInterface = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [patients, setPatients] = useState([]);
  const [medicalRecords, setMedicalRecords] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [toastMessage, setToastMessage] = useState('');
  const [toastType, setToastType] = useState('info');
  const [showToast, setShowToast] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showRecordDialog, setShowRecordDialog] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [recordToDelete, setRecordToDelete] = useState(null);
  const [recordForm, setRecordForm] = useState({
    patient_id: '',
    record_type: 'general',
    chief_complaint: '',
    history_of_present_illness: '',
    physical_examination: '',
    assessment: '',
    plan: '',
    diagnosis: '',
    treatment_notes: '',
    follow_up_instructions: ''
  });

  const recordTypes = [
    { value: 'general', label: 'Общий осмотр', icon: <Stethoscope /> },
    { value: 'consultation', label: 'Консультация', icon: <MessageSquare /> },
    { value: 'follow_up', label: 'Повторный прием', icon: <History /> },
    { value: 'emergency', label: 'Неотложная помощь', icon: <Hospital /> },
    { value: 'psychology', label: 'Психологическая помощь', icon: <Brain /> }
  ];

  useEffect(() => {
    loadEMRData();
  }, []);

  const loadEMRData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      const [patientsRes, recordsRes, templatesRes] = await Promise.all([
        fetch('/api/v1/patients/', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/medical-records/', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/emr/templates', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (patientsRes.ok) {
        const patientsData = await patientsRes.json();
        setPatients(patientsData.patients || patientsData || []);
      } else {
        // Fallback данные для демонстрации
        setPatients([
          { id: 1, full_name: 'Иванов Иван Иванович', phone: '+7 (999) 123-45-67', email: 'ivanov@example.com', date_of_birth: '1985-05-15' },
          { id: 2, full_name: 'Петрова Анна Сергеевна', phone: '+7 (999) 234-56-78', email: 'petrova@example.com', date_of_birth: '1990-08-22' },
          { id: 3, full_name: 'Сидоров Петр Александрович', phone: '+7 (999) 345-67-89', email: 'sidorov@example.com', date_of_birth: '1978-12-03' }
        ]);
      }

      if (recordsRes.ok) {
        const recordsData = await recordsRes.json();
        setMedicalRecords(recordsData.records || recordsData || []);
      } else {
        // Fallback данные для демонстрации
        setMedicalRecords([
          { 
            id: 1, 
            patient_id: 1, 
            patient: { full_name: 'Иванов Иван Иванович' },
            record_type: 'general',
            chief_complaint: 'Головная боль',
            created_at: '2024-01-15T10:30:00Z'
          },
          { 
            id: 2, 
            patient_id: 2, 
            patient: { full_name: 'Петрова Анна Сергеевна' },
            record_type: 'consultation',
            chief_complaint: 'Консультация по результатам анализов',
            created_at: '2024-01-14T14:20:00Z'
          }
        ]);
      }

      if (templatesRes.ok) {
        const templatesData = await templatesRes.json();
        setTemplates(templatesData.templates || templatesData || []);
      } else {
        // Fallback данные для демонстрации
        setTemplates([
          { id: 1, name: 'Общий осмотр', description: 'Шаблон для общего медицинского осмотра', fields: ['chief_complaint', 'physical_examination', 'diagnosis'] },
          { id: 2, name: 'Консультация', description: 'Шаблон для консультации специалиста', fields: ['chief_complaint', 'assessment', 'plan'] },
          { id: 3, name: 'Повторный прием', description: 'Шаблон для повторного приема', fields: ['follow_up', 'treatment_notes'] }
        ]);
      }
    } catch (err) {
      showToastMessage(handleApiError(err), 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRecord = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/medical-records/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(recordForm)
      });

      if (response.ok) {
        showToastMessage('Медицинская запись успешно создана', 'success');
        loadEMRData();
        setShowRecordDialog(false);
        resetRecordForm();
      } else {
        const errorData = await response.json();
        showToastMessage(errorData.detail || 'Ошибка создания записи', 'error');
      }
    } catch (err) {
      showToastMessage(handleApiError(err), 'error');
    }
  };

  const handleUpdateRecord = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/medical-records/${selectedRecord.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(recordForm)
      });

      if (response.ok) {
        showToastMessage('Медицинская запись успешно обновлена', 'success');
        loadEMRData();
        setShowRecordDialog(false);
        resetRecordForm();
      } else {
        const errorData = await response.json();
        showToastMessage(errorData.detail || 'Ошибка обновления записи', 'error');
      }
    } catch (err) {
      showToastMessage(handleApiError(err), 'error');
    }
  };

  const handleDeleteRecord = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/medical-records/${recordToDelete.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        showToastMessage('Медицинская запись успешно удалена', 'success');
        loadEMRData();
        setShowDeleteDialog(false);
        setRecordToDelete(null);
      } else {
        const errorData = await response.json();
        showToastMessage(errorData.detail || 'Ошибка удаления записи', 'error');
      }
    } catch (err) {
      showToastMessage(handleApiError(err), 'error');
    }
  };

  const confirmDeleteRecord = (record) => {
    setRecordToDelete(record);
    setShowDeleteDialog(true);
  };

  const handleEditTemplate = (template) => {
    // TODO: Реализовать редактирование шаблона
    console.log('Edit template:', template);
  };

  const handleDeleteTemplate = async (template) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/emr/templates/${template.id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        showToastMessage('Шаблон успешно удален', 'success');
        loadEMRData();
      } else {
        const errorData = await response.json();
        showToastMessage(errorData.detail || 'Ошибка удаления шаблона', 'error');
      }
    } catch (err) {
      showToastMessage(handleApiError(err), 'error');
    }
  };

  const resetRecordForm = () => {
    setRecordForm({
      patient_id: '',
      record_type: 'general',
      chief_complaint: '',
      history_of_present_illness: '',
      physical_examination: '',
      assessment: '',
      plan: '',
      diagnosis: '',
      treatment_notes: '',
      follow_up_instructions: ''
    });
  };

  const openRecordDialog = (patient = null, record = null) => {
    if (patient) {
      setRecordForm(prev => ({ ...prev, patient_id: patient.id }));
    }
    if (record) {
      setSelectedRecord(record);
      // Явный маппинг полей из записи в форму
      setRecordForm({
        patient_id: record.patient_id || '',
        record_type: record.record_type || 'general',
        chief_complaint: record.chief_complaint || '',
        history_of_present_illness: record.history_of_present_illness || '',
        physical_examination: record.physical_examination || '',
        assessment: record.assessment || '',
        plan: record.plan || '',
        diagnosis: record.diagnosis || '',
        treatment_notes: record.treatment_notes || '',
        follow_up_instructions: record.follow_up_instructions || ''
      });
    } else {
      setSelectedRecord(null);
      resetRecordForm();
    }
    setShowRecordDialog(true);
  };

  const filteredPatients = patients.filter(patient =>
    patient.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    patient.phone?.includes(searchTerm) ||
    patient.email?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getRecordTypeIcon = (type) => {
    const recordType = recordTypes.find(rt => rt.value === type);
    return recordType?.icon || <Stethoscope />;
  };

  const getRecordTypeLabel = (type) => {
    const recordType = recordTypes.find(rt => rt.value === type);
    return recordType?.label || type;
  };

  const getRecordTypeColor = (type) => {
    const colors = {
      general: 'primary',
      consultation: 'info',
      follow_up: 'success',
      emergency: 'error',
      psychology: 'secondary'
    };
    return colors[type] || 'default';
  };

  const tabButtonStyle = (isActive) => ({
    padding: '12px 24px',
    border: 'none',
    background: isActive ? 'var(--mac-accent-blue)' : 'transparent',
    color: isActive ? 'white' : 'var(--mac-text-primary)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    borderRadius: isActive ? '8px 8px 0 0' : '0',
    transition: 'all 0.2s ease',
    fontSize: 14,
    fontWeight: isActive ? 600 : 400
  });

  const handleApiError = (error) => {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return 'Проблема с подключением к серверу';
    }
    
    if (error.status) {
      switch (error.status) {
        case 401:
          return 'Сессия истекла, войдите снова';
        case 404:
          return 'Ресурс не найден';
        case 500:
          return 'Ошибка сервера, попробуйте позже';
        default:
          return error.message || 'Произошла ошибка';
      }
    }
    
    return error.message || 'Произошла неизвестная ошибка';
  };

  const showToastMessage = (message, type = 'info') => {
    setToastMessage(message);
    setToastType(type);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 5000);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Typography variant="h4">
          Электронные медицинские карты
        </Typography>
        <Button
          variant="primary"
          onClick={() => openRecordDialog()}
        >
          <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
          Новая запись
        </Button>
      </div>


      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--mac-border)' }}>
          <button
            style={tabButtonStyle(activeTab === 0)}
            onClick={() => setActiveTab(0)}
          >
            <User style={{ width: 16, height: 16 }} />
            Пациенты
          </button>
          <button
            style={tabButtonStyle(activeTab === 1)}
            onClick={() => setActiveTab(1)}
          >
            <FileText style={{ width: 16, height: 16 }} />
            Медицинские записи
          </button>
          <button
            style={tabButtonStyle(activeTab === 2)}
            onClick={() => setActiveTab(2)}
          >
            <FileText style={{ width: 16, height: 16 }} />
            Шаблоны
          </button>
        </div>
      </Card>

      {/* Контент табов */}
      {activeTab === 0 && (
        <Card>
          <CardContent>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ position: 'relative', width: 300 }}>
                <input
                  type="text"
                  placeholder="Поиск пациентов..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 12px 12px 40px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 8,
                    backgroundColor: 'var(--mac-background)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 14
                  }}
                />
                <Search style={{ 
                  position: 'absolute', 
                  left: 12, 
                  top: '50%', 
                  transform: 'translateY(-50%)', 
                  width: 16, 
                  height: 16, 
                  color: 'var(--mac-text-secondary)' 
                }} />
              </div>
              <Button onClick={loadEMRData}>
                <RefreshCw style={{ width: 16, height: 16, marginRight: 8 }} />
                Обновить
              </Button>
            </div>
            
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--mac-border)' }}>
                    <th style={{ padding: 12, textAlign: 'left' }}>Пациент</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Телефон</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Email</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Дата рождения</th>
                    <th style={{ padding: 12, textAlign: 'left' }}>Записей</th>
                    <th style={{ padding: 12, textAlign: 'right' }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPatients.map((patient) => (
                    <tr key={patient.id} style={{ borderBottom: '1px solid var(--mac-border)' }}>
                      <td style={{ padding: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center' }}>
                          <div style={{ width: 32, height: 32, borderRadius: '50%', backgroundColor: 'var(--mac-accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: 12 }}>
                            <User style={{ width: 16, height: 16, color: 'white' }} />
                          </div>
                          <div>
                            <Typography variant="subtitle2">
                              {patient.full_name || 'Не указано'}
                            </Typography>
                            <Typography variant="body2" color="textSecondary">
                              ID: {patient.id}
                            </Typography>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: 12 }}>{patient.phone || '-'}</td>
                      <td style={{ padding: 12 }}>{patient.email || '-'}</td>
                      <td style={{ padding: 12 }}>
                        {patient.date_of_birth ? new Date(patient.date_of_birth).toLocaleDateString() : '-'}
                      </td>
                      <td style={{ padding: 12 }}>
                        <Badge variant="primary">
                          {medicalRecords.filter(r => r.patient_id === patient.id).length}
                        </Badge>
                      </td>
                      <td style={{ padding: 12, textAlign: 'right' }}>
                        <Button size="small" onClick={() => openRecordDialog(patient)}>
                          <Plus style={{ width: 16, height: 16 }} />
                        </Button>
                        <Button size="small">
                          <Eye style={{ width: 16, height: 16 }} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 1 && (
        <Card>
          <CardContent>
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--mac-background-secondary)' }}>
                    <th style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Пациент</th>
                    <th style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Тип записи</th>
                    <th style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Жалобы</th>
                    <th style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Диагноз</th>
                    <th style={{ padding: 12, textAlign: 'left', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Дата</th>
                    <th style={{ padding: 12, textAlign: 'right', borderBottom: '1px solid var(--mac-border)', fontWeight: 600 }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {medicalRecords.map((record) => {
                    const patient = patients.find(p => p.id === record.patient_id);
                    return (
                      <tr key={record.id} style={{ borderBottom: '1px solid var(--mac-border)' }}>
                        <td style={{ padding: 12 }}>
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <div style={{ width: 40, height: 40, borderRadius: '50%', backgroundColor: 'var(--mac-accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: 16 }}>
                              <User style={{ width: 20, height: 20, color: 'white' }} />
                            </div>
                            <div>
                              <Typography variant="subtitle2">
                                {patient?.full_name || 'Неизвестный пациент'}
                              </Typography>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: 12 }}>
                          <Badge variant="primary">
                            {getRecordTypeLabel(record.record_type)}
                          </Badge>
                        </td>
                        <td style={{ padding: 12 }}>
                          <Typography variant="body2" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {record.chief_complaint || '-'}
                          </Typography>
                        </td>
                        <td style={{ padding: 12 }}>
                          <Typography variant="body2" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {record.diagnosis || '-'}
                          </Typography>
                        </td>
                        <td style={{ padding: 12 }}>
                          {record.created_at ? new Date(record.created_at).toLocaleDateString() : '-'}
                        </td>
                        <td style={{ padding: 12, textAlign: 'right' }}>
                          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }} onClick={() => openRecordDialog(null, record)}>
                            <Edit style={{ width: 16, height: 16 }} />
                          </button>
                          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }}>
                            <Eye style={{ width: 16, height: 16 }} />
                          </button>
                          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }}>
                            <Download style={{ width: 16, height: 16 }} />
                          </button>
                          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }} onClick={() => confirmDeleteRecord(record)}>
                            <Trash2 style={{ width: 16, height: 16, color: 'var(--mac-accent-red)' }} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 2 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Шаблоны медицинских записей
            </Typography>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
              {templates.map((template) => (
                <div key={template.id} style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 16 }}>
                  <div style={{ marginBottom: 16 }}>
                    <Typography variant="h6" gutterBottom>
                      {template.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {template.description}
                    </Typography>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Badge variant="primary">
                      {template.category}
                    </Badge>
                    <div>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8, marginRight: 8 }} onClick={() => handleEditTemplate(template)}>
                        <Edit style={{ width: 16, height: 16 }} />
                      </button>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 8 }} onClick={() => handleDeleteTemplate(template)}>
                        <Delete style={{ width: 16, height: 16, color: 'var(--mac-accent-red)' }} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Диалог создания/редактирования записи */}
      {showRecordDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--mac-background)',
            borderRadius: 12,
            padding: 24,
            width: '90%',
            maxWidth: 600,
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <div style={{ marginBottom: 24 }}>
              <Typography variant="h6">
                {selectedRecord ? 'Редактировать медицинскую запись' : 'Новая медицинская запись'}
              </Typography>
            </div>
            {/* Основная информация */}
            <details open style={{ marginBottom: 16 }}>
              <summary style={{ 
                cursor: 'pointer', 
                padding: '12px 16px', 
                backgroundColor: 'var(--mac-background-secondary)', 
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 16,
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)'
              }}>
                Основная информация
              </summary>
              <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderTop: 'none', borderRadius: '0 0 8px 8px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Пациент</label>
                    <Select
                      options={patients.map((patient) => ({
                        value: patient.id,
                        label: patient.full_name || `ID: ${patient.id}`
                      }))}
                      value={recordForm.patient_id}
                      onChange={(val) => setRecordForm({...recordForm, patient_id: val})}
                      placeholder="Выберите пациента..."
                      style={{ width: '100%' }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Тип записи</label>
                    <Select
                      options={recordTypes.map((type) => ({
                        value: type.value,
                        label: type.label
                      }))}
                      value={recordForm.record_type}
                      onChange={(val) => setRecordForm({...recordForm, record_type: val})}
                      placeholder="Выберите тип записи..."
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              </div>
            </details>
            {/* Жалобы и анамнез */}
            <details open style={{ marginBottom: 16 }}>
              <summary style={{ 
                cursor: 'pointer', 
                padding: '12px 16px', 
                backgroundColor: 'var(--mac-background-secondary)', 
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 16,
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)'
              }}>
                Жалобы и анамнез
              </summary>
              <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderTop: 'none', borderRadius: '0 0 8px 8px' }}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Жалобы пациента</label>
                  <textarea
                    value={recordForm.chief_complaint}
                    onChange={(e) => setRecordForm({...recordForm, chief_complaint: e.target.value})}
                    style={{
                      width: '100%',
                      minHeight: 80,
                      padding: 12,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      backgroundColor: 'var(--mac-background)',
                      color: 'var(--mac-text-primary)',
                      resize: 'vertical'
                    }}
                    placeholder="Опишите жалобы пациента..."
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Анамнез настоящего заболевания</label>
                  <textarea
                    value={recordForm.history_of_present_illness}
                    onChange={(e) => setRecordForm({...recordForm, history_of_present_illness: e.target.value})}
                    style={{
                      width: '100%',
                      minHeight: 80,
                      padding: 12,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      backgroundColor: 'var(--mac-background)',
                      color: 'var(--mac-text-primary)',
                      resize: 'vertical'
                    }}
                    placeholder="Анамнез заболевания..."
                  />
                </div>
              </div>
            </details>
            {/* Осмотр и диагностика */}
            <details open style={{ marginBottom: 16 }}>
              <summary style={{ 
                cursor: 'pointer', 
                padding: '12px 16px', 
                backgroundColor: 'var(--mac-background-secondary)', 
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 16,
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)'
              }}>
                Осмотр и диагностика
              </summary>
              <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderTop: 'none', borderRadius: '0 0 8px 8px' }}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Физикальное обследование</label>
                  <textarea
                    value={recordForm.physical_examination}
                    onChange={(e) => setRecordForm({...recordForm, physical_examination: e.target.value})}
                    style={{
                      width: '100%',
                      minHeight: 80,
                      padding: 12,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      backgroundColor: 'var(--mac-background)',
                      color: 'var(--mac-text-primary)',
                      resize: 'vertical'
                    }}
                    placeholder="Результаты физикального обследования..."
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Диагноз</label>
                    <input
                      type="text"
                      value={recordForm.diagnosis}
                      onChange={(e) => setRecordForm({...recordForm, diagnosis: e.target.value})}
                      style={{
                        width: '100%',
                        padding: 12,
                        border: '1px solid var(--mac-border)',
                        borderRadius: 8,
                        backgroundColor: 'var(--mac-background)',
                        color: 'var(--mac-text-primary)'
                      }}
                      placeholder="Основной диагноз..."
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>План лечения</label>
                    <input
                      type="text"
                      value={recordForm.plan}
                      onChange={(e) => setRecordForm({...recordForm, plan: e.target.value})}
                      style={{
                        width: '100%',
                        padding: 12,
                        border: '1px solid var(--mac-border)',
                        borderRadius: 8,
                        backgroundColor: 'var(--mac-background)',
                        color: 'var(--mac-text-primary)'
                      }}
                      placeholder="План лечения..."
                    />
                  </div>
                </div>
              </div>
            </details>
            {/* План лечения */}
            <details open style={{ marginBottom: 16 }}>
              <summary style={{ 
                cursor: 'pointer', 
                padding: '12px 16px', 
                backgroundColor: 'var(--mac-background-secondary)', 
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 16,
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)'
              }}>
                План лечения
              </summary>
              <div style={{ padding: 16, border: '1px solid var(--mac-border)', borderTop: 'none', borderRadius: '0 0 8px 8px' }}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Лечебные назначения</label>
                  <textarea
                    value={recordForm.treatment_notes}
                    onChange={(e) => setRecordForm({...recordForm, treatment_notes: e.target.value})}
                    style={{
                      width: '100%',
                      minHeight: 80,
                      padding: 12,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      backgroundColor: 'var(--mac-background)',
                      color: 'var(--mac-text-primary)',
                      resize: 'vertical'
                    }}
                    placeholder="Лечебные назначения..."
                  />
                </div>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: 'block', marginBottom: 8, color: 'var(--mac-text-primary)' }}>Рекомендации и дальнейшие действия</label>
                  <textarea
                    value={recordForm.follow_up_instructions}
                    onChange={(e) => setRecordForm({...recordForm, follow_up_instructions: e.target.value})}
                    style={{
                      width: '100%',
                      minHeight: 60,
                      padding: 12,
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      backgroundColor: 'var(--mac-background)',
                      color: 'var(--mac-text-primary)',
                      resize: 'vertical'
                    }}
                    placeholder="Рекомендации и дальнейшие действия..."
                  />
                </div>
              </div>
            </details>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <Button onClick={() => setShowRecordDialog(false)}>Отмена</Button>
              <Button onClick={selectedRecord ? handleUpdateRecord : handleCreateRecord} variant="contained">
                {selectedRecord ? 'Обновить' : 'Создать'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Диалог подтверждения удаления */}
      {showDeleteDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--mac-background)',
            borderRadius: 12,
            padding: 24,
            width: '90%',
            maxWidth: 400,
            textAlign: 'center'
          }}>
            <div style={{ marginBottom: 16 }}>
              <AlertTriangle style={{ width: 48, height: 48, color: 'var(--mac-accent-orange)', margin: '0 auto 16px' }} />
              <Typography variant="h6" gutterBottom>
                Подтверждение удаления
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Вы уверены, что хотите удалить эту медицинскую запись? Это действие нельзя отменить.
              </Typography>
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
              <Button onClick={() => setShowDeleteDialog(false)}>
                Отмена
              </Button>
              <Button onClick={handleDeleteRecord} variant="danger">
                <Trash2 style={{ width: 16, height: 16, marginRight: 8 }} />
                Удалить
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Toast уведомления */}
      {showToast && (
        <ToastContainer>
          <Toast
            type={toastType}
            message={toastMessage}
            duration={5000}
            onClose={() => setShowToast(false)}
          />
        </ToastContainer>
      )}
    </div>
  );
};

export default EMRInterface;

