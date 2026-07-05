import { useState } from 'react';
import {
  MacOSCard,
  Button,
  Input,
  Select,
  Checkbox,
} from '../ui/macos';
import {
  Calendar,
  Clock,
  Users,

  BarChart3,
  Settings,
  CheckCircle,
  AlertCircle,

  Loader,
  Download,
  Copy,

  Zap,
  Target,
  Brain,
  UserCheck,
  ClipboardList,
  Activity,
  Plus } from

'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const parseOptionalInteger = (value) => {
  if (value === '') return '';
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? '' : parsed;
};

const SmartScheduling = () => {
  const [activeTab, setActiveTab] = useState('schedule-optimization');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Состояния для разных типов запросов
  const [scheduleData, setScheduleData] = useState({
    doctor: {
      name: '',
      specialty: '',
      experience_years: '',
      preferences: {}
    },
    current_schedule: [],
    appointments: []
  });

  const [constraints, setConstraints] = useState({
    working_hours: { start: '', end: '' },
    break_requirements: { lunch_break: '', short_breaks: '' },
    max_patients_per_day: '',
    appointment_types: []
  });

  const [appointmentData, setAppointmentData] = useState({
    patient: {},
    type: '',
    complaint: '',
    doctor_specialty: '',
    is_first_visit: false
  });

  const [historicalData, setHistoricalData] = useState([]);

  const [doctorProfile, setDoctorProfile] = useState({
    name: '',
    specialty: '',
    working_patterns: {},
    performance_metrics: {}
  });

  const [patientRequirements, setPatientRequirements] = useState({
    preferences: {},
    urgency: '',
    type: '',
    estimated_duration: ''
  });

  const [availableSlots, setAvailableSlots] = useState([]);

  const [doctorsData, setDoctorsData] = useState([]);
  const [timePeriod, setTimePeriod] = useState('week');

  const [departmentData, setDepartmentData] = useState({
    name: '',
    staff: [],
    current_shifts: [],
    patient_flow_patterns: {}
  });

  const [staffingRequirements, setStaffingRequirements] = useState({
    min_staff_per_shift: '',
    coverage_hours: '',
    skill_requirements: [],
    compliance_rules: {}
  });

  const tabs = [
  { id: 'schedule-optimization', label: 'Оптимизация расписания', icon: <Calendar className="w-4 h-4" /> },
  { id: 'duration-prediction', label: 'Прогноз длительности', icon: <Clock className="w-4 h-4" /> },
  { id: 'optimal-slots', label: 'Оптимальные слоты', icon: <Target className="w-4 h-4" /> },
  { id: 'workload-analysis', label: 'Анализ нагрузки', icon: <BarChart3 className="w-4 h-4" /> },
  { id: 'shift-recommendations', label: 'Рекомендации смен', icon: <Users className="w-4 h-4" /> }];


  const handleSubmit = async () => {
    setLoading(true);
    setResult(null);
    setError(null);

    let endpoint = '';
    let data = {};

    try {
      switch (activeTab) {
        case 'schedule-optimization':
          endpoint = '/ai/optimize-doctor-schedule';
          data = {
            schedule_data: scheduleData,
            constraints: constraints
          };
          break;
        case 'duration-prediction':
          endpoint = '/ai/predict-appointment-duration';
          data = {
            appointment_data: appointmentData,
            historical_data: historicalData
          };
          break;
        case 'optimal-slots':
          endpoint = '/ai/suggest-optimal-slots';
          data = {
            doctor_profile: doctorProfile,
            patient_requirements: patientRequirements,
            available_slots: availableSlots
          };
          break;
        case 'workload-analysis':
          endpoint = '/ai/analyze-workload-distribution';
          data = {
            doctors_data: doctorsData,
            time_period: timePeriod
          };
          break;
        case 'shift-recommendations':
          endpoint = '/ai/generate-shift-recommendations';
          data = {
            department_data: departmentData,
            staffing_requirements: staffingRequirements
          };
          break;
        default:
          throw new Error('Неизвестный тип запроса');
      }

      const response = await api.post(endpoint, data);
      setResult(response.data);
      toast.success('AI анализ успешно выполнен!');
    } catch (err) {
      toast.error('Ошибка при выполнении AI анализа.');
      logger.error('AI analysis error:', err);
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success('Скопировано в буфер обмена');
    });
  };

  const exportResult = () => {
    if (!result) return;

    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);

    const exportFileDefaultName = `smart_scheduling_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addScheduleSlot = () => {
    setScheduleData((prev) => ({
      ...prev,
      current_schedule: [
      ...prev.current_schedule,
      { time: '', type: '', duration: '' }]

    }));
  };











  const addHistoricalRecord = () => {
    setHistoricalData((prev) => [
    ...prev,
    { type: '', actual_duration: '', complaint: '', date: '' }]
    );
  };

  const addAvailableSlot = () => {
    setAvailableSlots((prev) => [
    ...prev,
    { date: '', time: '', duration: '', current_load: '' }]
    );
  };

  const addDoctor = () => {
    setDoctorsData((prev) => [
    ...prev,
    {
      name: '',
      specialty: '',
      appointments: [],
      total_working_hours: '',
      patient_load: ''
    }]
    );
  };

  const addStaffMember = () => {
    setDepartmentData((prev) => ({
      ...prev,
      staff: [
      ...prev.staff,
      { name: '', role: '', experience: '', preferences: {} }]

    }));
  };

  const renderScheduleOptimization = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-info-bg)',
      border: '1px solid var(--mac-info-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-info)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <UserCheck style={{ width: '16px', height: '16px' }} />
          Информация о враче
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Имя врача
            </label>
            <Input
            type="text"
            value={scheduleData.doctor.name}
            onChange={(e) => setScheduleData((prev) => ({
              ...prev,
              doctor: { ...prev.doctor, name: e.target.value }
            }))}
            placeholder="Доктор Иванов"
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Специальность
            </label>
            <Input
            type="text"
            value={scheduleData.doctor.specialty}
            onChange={(e) => setScheduleData((prev) => ({
              ...prev,
              doctor: { ...prev.doctor, specialty: e.target.value }
            }))}
            placeholder="Кардиолог"
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Опыт работы (лет)
            </label>
            <Input
            type="number"
            value={scheduleData.doctor.experience_years}
            onChange={(e) => setScheduleData((prev) => ({
              ...prev,
              doctor: { ...prev.doctor, experience_years: parseOptionalInteger(e.target.value) }
            }))}
            placeholder="10"
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-success-bg)',
      border: '1px solid var(--mac-success-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-success)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <Settings style={{ width: '16px', height: '16px' }} />
          Ограничения и требования
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Начало рабочего дня
            </label>
            <Input
            type="time"
            value={constraints.working_hours.start}
            onChange={(e) => setConstraints((prev) => ({
              ...prev,
              working_hours: { ...prev.working_hours, start: e.target.value }
            }))}
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Конец рабочего дня
            </label>
            <Input
            type="time"
            value={constraints.working_hours.end}
            onChange={(e) => setConstraints((prev) => ({
              ...prev,
              working_hours: { ...prev.working_hours, end: e.target.value }
            }))}
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Максимум пациентов в день
            </label>
            <Input
            type="number"
            value={constraints.max_patients_per_day}
            onChange={(e) => setConstraints((prev) => ({
              ...prev,
              max_patients_per_day: parseOptionalInteger(e.target.value)
            }))}
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Обеденный перерыв (мин)
            </label>
            <Input
            type="number"
            value={constraints.break_requirements.lunch_break}
            onChange={(e) => setConstraints((prev) => ({
              ...prev,
              break_requirements: { ...prev.break_requirements, lunch_break: parseOptionalInteger(e.target.value) }
            }))}
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-warning-bg)',
      border: '1px solid var(--mac-warning-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-3)' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-warning)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <ClipboardList style={{ width: '16px', height: '16px' }} />
            Текущее расписание
          </h4>
          <Button
          onClick={addScheduleSlot}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить слот
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)', maxHeight: '128px', overflowY: 'auto' }}>
          {scheduleData.current_schedule.map((slot, index) =>
        <div key={index} style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
              <Input
            type="time"
            value={slot.time}
            onChange={(e) => {
              const newSchedule = [...scheduleData.current_schedule];
              newSchedule[index].time = e.target.value;
              setScheduleData((prev) => ({ ...prev, current_schedule: newSchedule }));
            }}
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={slot.type}
            onChange={(e) => {
              const newSchedule = [...scheduleData.current_schedule];
              newSchedule[index].type = e.target.value;
              setScheduleData((prev) => ({ ...prev, current_schedule: newSchedule }));
            }}
            placeholder="Выберите тип"
            options={[
            { value: 'free', label: 'Свободно' },
            { value: 'appointment', label: 'Прием' },
            { value: 'break', label: 'Перерыв' },
            { value: 'admin', label: 'Админ. работа' }]
            }
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={slot.duration}
            onChange={(e) => {
              const newSchedule = [...scheduleData.current_schedule];
              newSchedule[index].duration = parseOptionalInteger(e.target.value);
              setScheduleData((prev) => ({ ...prev, current_schedule: newSchedule }));
            }}
            placeholder="мин"
            style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }} />
          
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderDurationPrediction = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-accent-bg)',
      border: '1px solid var(--mac-accent-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-accent)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <Activity style={{ width: '16px', height: '16px' }} />
          Данные о приеме
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Тип приема
            </label>
            <Select
            value={appointmentData.type}
            onChange={(e) => setAppointmentData((prev) => ({ ...prev, type: e.target.value }))}
            placeholder="Выберите тип"
            options={[
            { value: 'consultation', label: 'Консультация' },
            { value: 'follow-up', label: 'Повторный прием' },
            { value: 'procedure', label: 'Процедура' },
            { value: 'emergency', label: 'Экстренный' }]
            }
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Специальность врача
            </label>
            <Input
            type="text"
            value={appointmentData.doctor_specialty}
            onChange={(e) => setAppointmentData((prev) => ({ ...prev, doctor_specialty: e.target.value }))}
            placeholder="Кардиолог"
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Жалоба пациента
            </label>
            <Input
            type="text"
            value={appointmentData.complaint}
            onChange={(e) => setAppointmentData((prev) => ({ ...prev, complaint: e.target.value }))}
            placeholder="Боли в груди"
            style={{ width: '100%' }} />
          
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <Checkbox
            id="first_visit"
            checked={appointmentData.is_first_visit}
            onChange={(e) => setAppointmentData((prev) => ({ ...prev, is_first_visit: e.target.checked }))} />
          
            <label htmlFor="first_visit" style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Первичный визит
            </label>
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-info-bg)',
      border: '1px solid var(--mac-info-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-3)' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-info)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <BarChart3 style={{ width: '16px', height: '16px' }} />
            Исторические данные
          </h4>
          <Button
          onClick={addHistoricalRecord}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)', maxHeight: '128px', overflowY: 'auto' }}>
          {historicalData.map((record, index) =>
        <div key={index} style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
            <Select
            value={record.type}
            onChange={(e) => {
              const newData = [...historicalData];
              newData[index].type = e.target.value;
              setHistoricalData(newData);
            }}
            placeholder="Выберите тип"
            options={[
            { value: 'consultation', label: 'Консультация' },
            { value: 'follow-up', label: 'Повторный' },
            { value: 'procedure', label: 'Процедура' }]
            }
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={record.actual_duration}
            onChange={(e) => {
              const newData = [...historicalData];
              newData[index].actual_duration = parseOptionalInteger(e.target.value);
              setHistoricalData(newData);
            }}
            placeholder="мин"
            style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={record.complaint}
            onChange={(e) => {
              const newData = [...historicalData];
              newData[index].complaint = e.target.value;
              setHistoricalData(newData);
            }}
            placeholder="Жалоба"
            style={{ flex: 2, fontSize: 'var(--mac-font-size-xs)' }} />
          
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderOptimalSlots = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-success-bg)',
      border: '1px solid var(--mac-success-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-success)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <UserCheck style={{ width: '16px', height: '16px' }} />
          Профиль врача
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Имя врача
            </label>
            <Input
            type="text"
            value={doctorProfile.name}
            onChange={(e) => setDoctorProfile((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Доктор Петров"
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Специальность
            </label>
            <Input
            type="text"
            value={doctorProfile.specialty}
            onChange={(e) => setDoctorProfile((prev) => ({ ...prev, specialty: e.target.value }))}
            placeholder="Терапевт"
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-info-bg)',
      border: '1px solid var(--mac-info-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-info)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <Target style={{ width: '16px', height: '16px' }} />
          Требования пациента
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Срочность
            </label>
            <Select
            value={patientRequirements.urgency}
            onChange={(e) => setPatientRequirements((prev) => ({ ...prev, urgency: e.target.value }))}
            placeholder="Выберите срочность"
            options={[
            { value: 'normal', label: 'Обычная' },
            { value: 'urgent', label: 'Срочная' },
            { value: 'emergency', label: 'Экстренная' }]
            }
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Тип приема
            </label>
            <Select
            value={patientRequirements.type}
            onChange={(e) => setPatientRequirements((prev) => ({ ...prev, type: e.target.value }))}
            placeholder="Выберите тип"
            options={[
            { value: 'consultation', label: 'Консультация' },
            { value: 'follow-up', label: 'Повторный прием' },
            { value: 'procedure', label: 'Процедура' }]
            }
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Ожидаемая длительность (мин)
            </label>
            <Input
            type="number"
            value={patientRequirements.estimated_duration}
            onChange={(e) => setPatientRequirements((prev) => ({ ...prev, estimated_duration: parseOptionalInteger(e.target.value) }))}
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-warning-bg)',
      border: '1px solid var(--mac-warning-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-3)' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-warning)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <Clock style={{ width: '16px', height: '16px' }} />
            Доступные слоты
          </h4>
          <Button
          onClick={addAvailableSlot}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить слот
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)', maxHeight: '128px', overflowY: 'auto' }}>
          {availableSlots.map((slot, index) =>
        <div key={index} style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
              <Input
            type="date"
            value={slot.date}
            onChange={(e) => {
              const newSlots = [...availableSlots];
              newSlots[index].date = e.target.value;
              setAvailableSlots(newSlots);
            }}
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="time"
            value={slot.time}
            onChange={(e) => {
              const newSlots = [...availableSlots];
              newSlots[index].time = e.target.value;
              setAvailableSlots(newSlots);
            }}
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={slot.duration}
            onChange={(e) => {
              const newSlots = [...availableSlots];
              newSlots[index].duration = parseOptionalInteger(e.target.value);
              setAvailableSlots(newSlots);
            }}
            placeholder="мин"
            style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={slot.current_load}
            onChange={(e) => {
              const newSlots = [...availableSlots];
              newSlots[index].current_load = parseOptionalInteger(e.target.value);
              setAvailableSlots(newSlots);
            }}
            placeholder="%"
            style={{ width: '60px', fontSize: 'var(--mac-font-size-xs)' }} />
          
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderWorkloadAnalysis = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-danger)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <BarChart3 style={{ width: '16px', height: '16px' }} />
          Период анализа
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Временной период
            </label>
            <Select
            value={timePeriod}
            onChange={(e) => setTimePeriod(e.target.value)}
            options={[
            { value: 'day', label: 'День' },
            { value: 'week', label: 'Неделя' },
            { value: 'month', label: 'Месяц' },
            { value: 'quarter', label: 'Квартал' }]
            }
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-warning-bg)',
      border: '1px solid var(--mac-warning-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-3)' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-warning)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <Users style={{ width: '16px', height: '16px' }} />
            Данные врачей
          </h4>
          <Button
          onClick={addDoctor}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить врача
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)', maxHeight: '160px', overflowY: 'auto' }}>
          {doctorsData.map((doctor, index) =>
        <div key={index} style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
              <Input
            type="text"
            value={doctor.name}
            onChange={(e) => {
              const newDoctors = [...doctorsData];
              newDoctors[index].name = e.target.value;
              setDoctorsData(newDoctors);
            }}
            placeholder="Имя врача"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={doctor.specialty}
            onChange={(e) => {
              const newDoctors = [...doctorsData];
              newDoctors[index].specialty = e.target.value;
              setDoctorsData(newDoctors);
            }}
            placeholder="Специальность"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={doctor.total_working_hours}
            onChange={(e) => {
              const newDoctors = [...doctorsData];
              newDoctors[index].total_working_hours = parseOptionalInteger(e.target.value);
              setDoctorsData(newDoctors);
            }}
            placeholder="Часы"
            style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={doctor.patient_load}
            onChange={(e) => {
              const newDoctors = [...doctorsData];
              newDoctors[index].patient_load = parseOptionalInteger(e.target.value);
              setDoctorsData(newDoctors);
            }}
            placeholder="%"
            style={{ width: '60px', fontSize: 'var(--mac-font-size-xs)' }} />
          
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderShiftRecommendations = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-success-bg)',
      border: '1px solid var(--mac-success-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-success)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <Users style={{ width: '16px', height: '16px' }} />
          Информация об отделении
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Название отделения
            </label>
            <Input
            type="text"
            value={departmentData.name}
            onChange={(e) => setDepartmentData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Терапевтическое отделение"
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-info-bg)',
      border: '1px solid var(--mac-info-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-3)' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-info)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <UserCheck style={{ width: '16px', height: '16px' }} />
            Персонал отделения
          </h4>
          <Button
          onClick={addStaffMember}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить сотрудника
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)', maxHeight: '128px', overflowY: 'auto' }}>
          {departmentData.staff.map((staff, index) =>
        <div key={index} style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' }}>
              <Input
            type="text"
            value={staff.name}
            onChange={(e) => {
              const newStaff = [...departmentData.staff];
              newStaff[index].name = e.target.value;
              setDepartmentData((prev) => ({ ...prev, staff: newStaff }));
            }}
            placeholder="Имя сотрудника"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={staff.role}
            onChange={(e) => {
              const newStaff = [...departmentData.staff];
              newStaff[index].role = e.target.value;
              setDepartmentData((prev) => ({ ...prev, staff: newStaff }));
            }}
            placeholder="Должность"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={staff.experience}
            onChange={(e) => {
              const newStaff = [...departmentData.staff];
              newStaff[index].experience = parseOptionalInteger(e.target.value);
              setDepartmentData((prev) => ({ ...prev, staff: newStaff }));
            }}
            placeholder="Опыт"
            style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }} />
          
            </div>
        )}
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: 'var(--mac-spacing-4)',
      backgroundColor: 'var(--mac-accent-bg)',
      border: '1px solid var(--mac-accent-border)'
    }}>
        <h4 style={{
        fontWeight: 'var(--mac-font-weight-medium)',
        color: 'var(--mac-accent)',
        margin: '0 0 12px 0',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)'
      }}>
          <Settings style={{ width: '16px', height: '16px' }} />
          Требования к персоналу
        </h4>
        <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Минимум сотрудников на смену
            </label>
            <Input
            type="number"
            value={staffingRequirements.min_staff_per_shift}
            onChange={(e) => setStaffingRequirements((prev) => ({ ...prev, min_staff_per_shift: parseOptionalInteger(e.target.value) }))}
            style={{ width: '100%' }} />
          
          </div>
          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: 'var(--mac-spacing-1)'
          }}>
              Часы покрытия
            </label>
            <Select
            value={staffingRequirements.coverage_hours}
            onChange={(e) => setStaffingRequirements((prev) => ({ ...prev, coverage_hours: e.target.value }))}
            placeholder="Выберите покрытие"
            options={[
            { value: '24/7', label: '24/7' },
            { value: '8-20', label: '8:00-20:00' },
            { value: '9-18', label: '9:00-18:00' }]
            }
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{
          padding: 'var(--mac-spacing-4)',
          backgroundColor: 'var(--mac-error-bg)',
          border: '1px solid var(--mac-error-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-danger)' }} />
            <h3 style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-danger)',
              margin: 0
            }}>
              Ошибка
            </h3>
          </div>
          <p style={{
            marginTop: 'var(--mac-spacing-2)',
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-danger)',
            margin: '8px 0 0 0'
          }}>
            {result.error}
          </p>
        </MacOSCard>);

    }

    return (
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-4)' }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)'
          }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
            Результат AI анализа
          </h3>
          <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
            <Button
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
              
              <Copy style={{ width: '16px', height: '16px' }} />
              Копировать
            </Button>
            <Button
              onClick={exportResult}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>
              
              <Download style={{ width: '16px', height: '16px' }} />
              Экспорт
            </Button>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
          {Object.entries(result).map(([key, value]) =>
          <div key={key} style={{
            borderLeft: '4px solid var(--mac-accent)',
            paddingLeft: '16px'
          }}>
              <h4 style={{
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 8px 0',
              fontSize: 'var(--mac-font-size-sm)',
              textTransform: 'capitalize'
            }}>
                {key.replace(/_/g, ' ')}
              </h4>
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                {typeof value === 'object' && value !== null ?
              <pre style={{
                whiteSpace: 'pre-wrap',
                backgroundColor: 'var(--mac-bg-secondary)',
                padding: 'var(--mac-spacing-2)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                overflowX: 'auto',
                maxHeight: '256px',
                margin: 0,
                fontFamily: 'var(--mac-font-mono)'
              }}>
                    {JSON.stringify(value, null, 2)}
                  </pre> :

              <p style={{ margin: 0 }}>{String(value)}</p>
              }
              </div>
            </div>
          )}
        </div>
      </MacOSCard>);

  };

  return (
    <div style={{
      padding: 'var(--mac-spacing-6)',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        {/* Заголовок */}
        <div style={{
          paddingBottom: '24px',
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: 'var(--mac-spacing-6)'
        }}>
          <h2 style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-3)'
          }}>
            <Brain style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            AI Умное Планирование Расписания Врачей
          </h2>
          <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Оптимизация расписаний, прогнозирование длительности приемов и анализ рабочей нагрузки
          </p>
        </div>

        {/* Вкладки */}
        <div style={{
          display: 'flex',
          marginBottom: 'var(--mac-spacing-6)'
        }}>
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '12px 20px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--mac-spacing-2)',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                  fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                  fontSize: 'var(--mac-font-size-sm)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                  position: 'relative',
                  marginBottom: '-1px'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-primary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-secondary)';
                  }
                }}>
                
                <div style={{
                  width: '16px',
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
                }}>
                  {tab.icon}
                </div>
                {tab.label}
                {isActive &&
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent)',
                  borderRadius: '2px 2px 0 0'
                }} />
                }
              </button>);

          })}
        </div>
        
        {/* Разделительная линия */}
        <div style={{
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: 'var(--mac-spacing-6)'
        }} />

        {/* Контент */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: 'var(--mac-spacing-6)'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Настройки и данные
            </h3>
            
            {activeTab === 'schedule-optimization' && renderScheduleOptimization()}
            {activeTab === 'duration-prediction' && renderDurationPrediction()}
            {activeTab === 'optimal-slots' && renderOptimalSlots()}
            {activeTab === 'workload-analysis' && renderWorkloadAnalysis()}
            {activeTab === 'shift-recommendations' && renderShiftRecommendations()}
            
            <div style={{ marginTop: 'var(--mac-spacing-6)', display: 'flex', justifyContent: 'center' }}>
              <Button
                onClick={handleSubmit}
                disabled={loading}
                aria-label="Run AI scheduling analysis"
                style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                
                {loading ?
                <>
                    <Loader style={{
                    width: '20px',
                    height: '20px',
                    animation: 'spin 1s linear infinite'
                  }} />
                    Анализируем...
                  </> :

                <>
                    <Zap style={{ width: '20px', height: '20px' }} />
                    Запустить AI анализ
                  </>
                }
              </Button>
            </div>
          </div>

          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Результат
            </h3>
            {renderResult()}
            
            {error &&
            <MacOSCard style={{
              padding: 'var(--mac-spacing-4)',
              backgroundColor: 'var(--mac-error-bg)',
              border: '1px solid var(--mac-error-border)',
              marginTop: 'var(--mac-spacing-4)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                  <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-danger)' }} />
                  <h3 style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-danger)',
                  margin: 0
                }}>
                    Ошибка
                  </h3>
                </div>
                <p style={{
                marginTop: 'var(--mac-spacing-2)',
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-danger)',
                margin: '8px 0 0 0'
              }}>
                  {error}
                </p>
              </MacOSCard>
            }
          </div>
        </div>
      </MacOSCard>
    </div>);

};

export default SmartScheduling;
