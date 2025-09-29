import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Avatar,
  Tabs,
  Tab,
  Grid,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stepper,
  Step,
  StepLabel,
  StepContent
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Search,
  Refresh,
  Person,
  MedicalServices,
  Description,
  History,
  Assessment,
  Medication,
  LocalHospital,
  Psychology,
  Visibility,
  Download,
  Print,
  Share,
  ExpandMore,
  CheckCircle,
  Warning,
  Error
} from '@mui/icons-material';

const EMRInterface = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [patients, setPatients] = useState([]);
  const [medicalRecords, setMedicalRecords] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showRecordDialog, setShowRecordDialog] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
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
    { value: 'general', label: 'Общий осмотр', icon: <MedicalServices /> },
    { value: 'consultation', label: 'Консультация', icon: <Description /> },
    { value: 'follow_up', label: 'Повторный прием', icon: <History /> },
    { value: 'emergency', label: 'Неотложная помощь', icon: <LocalHospital /> },
    { value: 'psychology', label: 'Психологическая помощь', icon: <Psychology /> }
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
      }

      if (recordsRes.ok) {
        const recordsData = await recordsRes.json();
        setMedicalRecords(recordsData.records || recordsData || []);
      }

      if (templatesRes.ok) {
        const templatesData = await templatesRes.json();
        setTemplates(templatesData.templates || templatesData || []);
      }
    } catch (err) {
      setError('Ошибка загрузки данных EMR');
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
        setSuccess('Медицинская запись успешно создана');
        loadEMRData();
        setShowRecordDialog(false);
        resetRecordForm();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка создания записи');
      }
    } catch (err) {
      setError('Ошибка создания медицинской записи');
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
      setRecordForm(record);
    } else {
      setSelectedRecord(null);
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
    return recordType?.icon || <MedicalServices />;
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

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Заголовок */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Электронные медицинские карты
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => openRecordDialog()}
        >
          Новая запись
        </Button>
      </Box>

      {/* Алерты */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      {/* Табы */}
      <Card sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label="Пациенты" icon={<Person />} />
          <Tab label="Медицинские записи" icon={<Description />} />
          <Tab label="Шаблоны" icon={<Assessment />} />
        </Tabs>
      </Card>

      {/* Контент табов */}
      {activeTab === 0 && (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <TextField
                placeholder="Поиск пациентов..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: <Search />
                }}
                sx={{ width: 300 }}
              />
              <Button startIcon={<Refresh />} onClick={loadEMRData}>
                Обновить
              </Button>
            </Box>
            
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Пациент</TableCell>
                    <TableCell>Телефон</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell>Дата рождения</TableCell>
                    <TableCell>Записей</TableCell>
                    <TableCell align="right">Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredPatients.map((patient) => (
                    <TableRow key={patient.id} hover>
                      <TableCell>
                        <Box display="flex" alignItems="center">
                          <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                            <Person />
                          </Avatar>
                          <Box>
                            <Typography variant="subtitle2">
                              {patient.full_name || 'Не указано'}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              ID: {patient.id}
                            </Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell>{patient.phone || '-'}</TableCell>
                      <TableCell>{patient.email || '-'}</TableCell>
                      <TableCell>
                        {patient.date_of_birth ? new Date(patient.date_of_birth).toLocaleDateString() : '-'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={medicalRecords.filter(r => r.patient_id === patient.id).length}
                          color="primary"
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <IconButton onClick={() => openRecordDialog(patient)}>
                          <Add />
                        </IconButton>
                        <IconButton>
                          <Visibility />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {activeTab === 1 && (
        <Card>
          <CardContent>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Пациент</TableCell>
                    <TableCell>Тип записи</TableCell>
                    <TableCell>Жалобы</TableCell>
                    <TableCell>Диагноз</TableCell>
                    <TableCell>Дата</TableCell>
                    <TableCell align="right">Действия</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {medicalRecords.map((record) => {
                    const patient = patients.find(p => p.id === record.patient_id);
                    return (
                      <TableRow key={record.id} hover>
                        <TableCell>
                          <Box display="flex" alignItems="center">
                            <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                              <Person />
                            </Avatar>
                            <Box>
                              <Typography variant="subtitle2">
                                {patient?.full_name || 'Неизвестный пациент'}
                              </Typography>
                              <Typography variant="body2" color="text.secondary">
                                ID: {record.patient_id}
                              </Typography>
                            </Box>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={getRecordTypeIcon(record.record_type)}
                            label={getRecordTypeLabel(record.record_type)}
                            color={getRecordTypeColor(record.record_type)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                            {record.chief_complaint || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                            {record.diagnosis || '-'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          {record.created_at ? new Date(record.created_at).toLocaleDateString() : '-'}
                        </TableCell>
                        <TableCell align="right">
                          <IconButton onClick={() => openRecordDialog(null, record)}>
                            <Edit />
                          </IconButton>
                          <IconButton>
                            <Visibility />
                          </IconButton>
                          <IconButton>
                            <Download />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {activeTab === 2 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Шаблоны медицинских записей
            </Typography>
            <Grid container spacing={2}>
              {templates.map((template) => (
                <Grid item xs={12} md={6} key={template.id}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        {template.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" paragraph>
                        {template.description}
                      </Typography>
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Chip
                          label={template.category}
                          color="primary"
                          size="small"
                        />
                        <Box>
                          <IconButton size="small">
                            <Edit />
                          </IconButton>
                          <IconButton size="small">
                            <Delete />
                          </IconButton>
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Диалог создания/редактирования записи */}
      <Dialog open={showRecordDialog} onClose={() => setShowRecordDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {selectedRecord ? 'Редактировать медицинскую запись' : 'Новая медицинская запись'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Пациент</InputLabel>
                <Select
                  value={recordForm.patient_id}
                  onChange={(e) => setRecordForm({...recordForm, patient_id: e.target.value})}
                  label="Пациент"
                >
                  {patients.map((patient) => (
                    <MenuItem key={patient.id} value={patient.id}>
                      {patient.full_name || `ID: ${patient.id}`}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Тип записи</InputLabel>
                <Select
                  value={recordForm.record_type}
                  onChange={(e) => setRecordForm({...recordForm, record_type: e.target.value})}
                  label="Тип записи"
                >
                  {recordTypes.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      <Box display="flex" alignItems="center">
                        {type.icon}
                        <Typography sx={{ ml: 1 }}>{type.label}</Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Жалобы пациента"
                multiline
                rows={3}
                value={recordForm.chief_complaint}
                onChange={(e) => setRecordForm({...recordForm, chief_complaint: e.target.value})}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Анамнез настоящего заболевания"
                multiline
                rows={3}
                value={recordForm.history_of_present_illness}
                onChange={(e) => setRecordForm({...recordForm, history_of_present_illness: e.target.value})}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Физикальное обследование"
                multiline
                rows={3}
                value={recordForm.physical_examination}
                onChange={(e) => setRecordForm({...recordForm, physical_examination: e.target.value})}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Диагноз"
                value={recordForm.diagnosis}
                onChange={(e) => setRecordForm({...recordForm, diagnosis: e.target.value})}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="План лечения"
                value={recordForm.plan}
                onChange={(e) => setRecordForm({...recordForm, plan: e.target.value})}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Лечебные назначения"
                multiline
                rows={3}
                value={recordForm.treatment_notes}
                onChange={(e) => setRecordForm({...recordForm, treatment_notes: e.target.value})}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Рекомендации и дальнейшие действия"
                multiline
                rows={2}
                value={recordForm.follow_up_instructions}
                onChange={(e) => setRecordForm({...recordForm, follow_up_instructions: e.target.value})}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowRecordDialog(false)}>Отмена</Button>
          <Button onClick={handleCreateRecord} variant="contained">
            {selectedRecord ? 'Обновить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EMRInterface;

