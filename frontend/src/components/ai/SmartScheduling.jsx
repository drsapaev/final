import React, { useState, useEffect } from 'react';
import { 
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSBadge,
  MacOSLoadingSkeleton
} from '../ui/macos';
import { 
  Calendar, 
  Clock, 
  Users, 
  TrendingUp, 
  BarChart3,
  Settings,
  CheckCircle,
  AlertCircle,
  Info,
  Loader,
  Download,
  Copy,
  RefreshCw,
  Zap,
  Target,
  Brain,
  UserCheck,
  ClipboardList,
  Activity,
  Plus,
  Minus
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

import logger from '../../utils/logger';
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
    working_hours: { start: '09:00', end: '18:00' },
    break_requirements: { lunch_break: 60, short_breaks: 15 },
    max_patients_per_day: 15,
    appointment_types: []
  });

  const [appointmentData, setAppointmentData] = useState({
    patient: {},
    type: 'consultation',
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
    urgency: 'normal',
    type: 'consultation',
    estimated_duration: 30
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
    min_staff_per_shift: 1,
    coverage_hours: '24/7',
    skill_requirements: [],
    compliance_rules: {}
  });

  const tabs = [
    { id: 'schedule-optimization', label: 'Оптимизация расписания', icon: <Calendar className="w-4 h-4" /> },
    { id: 'duration-prediction', label: 'Прогноз длительности', icon: <Clock className="w-4 h-4" /> },
    { id: 'optimal-slots', label: 'Оптимальные слоты', icon: <Target className="w-4 h-4" /> },
    { id: 'workload-analysis', label: 'Анализ нагрузки', icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'shift-recommendations', label: 'Рекомендации смен', icon: <Users className="w-4 h-4" /> }
  ];

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
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `smart_scheduling_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addScheduleSlot = () => {
    setScheduleData(prev => ({
      ...prev,
      current_schedule: [
        ...prev.current_schedule,
        { time: '', type: 'free', duration: 30 }
      ]
    }));
  };

  const addAppointment = () => {
    setScheduleData(prev => ({
      ...prev,
      appointments: [
        ...prev.appointments,
        { time: '', patient_type: 'regular', complaint: '', estimated_duration: 30 }
      ]
    }));
  };

  const addHistoricalRecord = () => {
    setHistoricalData(prev => [
      ...prev,
      { type: 'consultation', actual_duration: 30, complaint: '', date: '' }
    ]);
  };

  const addAvailableSlot = () => {
    setAvailableSlots(prev => [
      ...prev,
      { date: '', time: '', duration: 30, current_load: 0 }
    ]);
  };

  const addDoctor = () => {
    setDoctorsData(prev => [
      ...prev,
      { 
        name: '', 
        specialty: '', 
        appointments: [], 
        total_working_hours: 8, 
        patient_load: 0 
      }
    ]);
  };

  const addStaffMember = () => {
    setDepartmentData(prev => ({
      ...prev,
      staff: [
        ...prev.staff,
        { name: '', role: '', experience: 0, preferences: {} }
      ]
    }));
  };

  const renderScheduleOptimization = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-info-bg)', 
        border: '1px solid var(--mac-info-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-info)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <UserCheck style={{ width: '16px', height: '16px' }} />
          Информация о враче
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Имя врача
            </label>
            <MacOSInput
              type="text"
              value={scheduleData.doctor.name}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, name: e.target.value }
              }))}
              placeholder="Доктор Иванов"
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Специальность
            </label>
            <MacOSInput
              type="text"
              value={scheduleData.doctor.specialty}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, specialty: e.target.value }
              }))}
              placeholder="Кардиолог"
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Опыт работы (лет)
            </label>
            <MacOSInput
              type="number"
              value={scheduleData.doctor.experience_years}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, experience_years: parseInt(e.target.value) || 0 }
              }))}
              placeholder="10"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-success-bg)', 
        border: '1px solid var(--mac-success-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-success)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Settings style={{ width: '16px', height: '16px' }} />
          Ограничения и требования
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Начало рабочего дня
            </label>
            <MacOSInput
              type="time"
              value={constraints.working_hours.start}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                working_hours: { ...prev.working_hours, start: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Конец рабочего дня
            </label>
            <MacOSInput
              type="time"
              value={constraints.working_hours.end}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                working_hours: { ...prev.working_hours, end: e.target.value }
              }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Максимум пациентов в день
            </label>
            <MacOSInput
              type="number"
              value={constraints.max_patients_per_day}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                max_patients_per_day: parseInt(e.target.value) || 15
              }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Обеденный перерыв (мин)
            </label>
            <MacOSInput
              type="number"
              value={constraints.break_requirements.lunch_break}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                break_requirements: { ...prev.break_requirements, lunch_break: parseInt(e.target.value) || 60 }
              }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-warning-bg)', 
        border: '1px solid var(--mac-warning-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <ClipboardList style={{ width: '16px', height: '16px' }} />
            Текущее расписание
          </h4>
          <MacOSButton
            onClick={addScheduleSlot}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить слот
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {scheduleData.current_schedule.map((slot, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSInput
                type="time"
                value={slot.time}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].time = e.target.value;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={slot.type}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].type = e.target.value;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                options={[
                  { value: 'free', label: 'Свободно' },
                  { value: 'appointment', label: 'Прием' },
                  { value: 'break', label: 'Перерыв' },
                  { value: 'admin', label: 'Админ. работа' }
                ]}
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={slot.duration}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].duration = parseInt(e.target.value) || 30;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                placeholder="мин"
                style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }}
              />
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderDurationPrediction = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-accent-bg)', 
        border: '1px solid var(--mac-accent-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-accent)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Activity style={{ width: '16px', height: '16px' }} />
          Данные о приеме
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Тип приема
            </label>
            <MacOSSelect
              value={appointmentData.type}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, type: e.target.value }))}
              options={[
                { value: 'consultation', label: 'Консультация' },
                { value: 'follow-up', label: 'Повторный прием' },
                { value: 'procedure', label: 'Процедура' },
                { value: 'emergency', label: 'Экстренный' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Специальность врача
            </label>
            <MacOSInput
              type="text"
              value={appointmentData.doctor_specialty}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, doctor_specialty: e.target.value }))}
              placeholder="Кардиолог"
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Жалоба пациента
            </label>
            <MacOSInput
              type="text"
              value={appointmentData.complaint}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, complaint: e.target.value }))}
              placeholder="Боли в груди"
              style={{ width: '100%' }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MacOSCheckbox
              id="first_visit"
              checked={appointmentData.is_first_visit}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, is_first_visit: e.target.checked }))}
            />
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
        padding: '16px', 
        backgroundColor: 'var(--mac-info-bg)', 
        border: '1px solid var(--mac-info-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <BarChart3 style={{ width: '16px', height: '16px' }} />
            Исторические данные
          </h4>
          <MacOSButton
            onClick={addHistoricalRecord}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {historicalData.map((record, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSSelect
                value={record.type}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].type = e.target.value;
                  setHistoricalData(newData);
                }}
                options={[
                  { value: 'consultation', label: 'Консультация' },
                  { value: 'follow-up', label: 'Повторный' },
                  { value: 'procedure', label: 'Процедура' }
                ]}
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={record.actual_duration}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].actual_duration = parseInt(e.target.value) || 30;
                  setHistoricalData(newData);
                }}
                placeholder="мин"
                style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={record.complaint}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].complaint = e.target.value;
                  setHistoricalData(newData);
                }}
                placeholder="Жалоба"
                style={{ flex: 2, fontSize: 'var(--mac-font-size-xs)' }}
              />
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderOptimalSlots = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-success-bg)', 
        border: '1px solid var(--mac-success-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-success)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <UserCheck style={{ width: '16px', height: '16px' }} />
          Профиль врача
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Имя врача
            </label>
            <MacOSInput
              type="text"
              value={doctorProfile.name}
              onChange={(e) => setDoctorProfile(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Доктор Петров"
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Специальность
            </label>
            <MacOSInput
              type="text"
              value={doctorProfile.specialty}
              onChange={(e) => setDoctorProfile(prev => ({ ...prev, specialty: e.target.value }))}
              placeholder="Терапевт"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-info-bg)', 
        border: '1px solid var(--mac-info-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-info)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Target style={{ width: '16px', height: '16px' }} />
          Требования пациента
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Срочность
            </label>
            <MacOSSelect
              value={patientRequirements.urgency}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, urgency: e.target.value }))}
              options={[
                { value: 'normal', label: 'Обычная' },
                { value: 'urgent', label: 'Срочная' },
                { value: 'emergency', label: 'Экстренная' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Тип приема
            </label>
            <MacOSSelect
              value={patientRequirements.type}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, type: e.target.value }))}
              options={[
                { value: 'consultation', label: 'Консультация' },
                { value: 'follow-up', label: 'Повторный прием' },
                { value: 'procedure', label: 'Процедура' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Ожидаемая длительность (мин)
            </label>
            <MacOSInput
              type="number"
              value={patientRequirements.estimated_duration}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, estimated_duration: parseInt(e.target.value) || 30 }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-warning-bg)', 
        border: '1px solid var(--mac-warning-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Clock style={{ width: '16px', height: '16px' }} />
            Доступные слоты
          </h4>
          <MacOSButton
            onClick={addAvailableSlot}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить слот
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {availableSlots.map((slot, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSInput
                type="date"
                value={slot.date}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].date = e.target.value;
                  setAvailableSlots(newSlots);
                }}
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="time"
                value={slot.time}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].time = e.target.value;
                  setAvailableSlots(newSlots);
                }}
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={slot.duration}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].duration = parseInt(e.target.value) || 30;
                  setAvailableSlots(newSlots);
                }}
                placeholder="мин"
                style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={slot.current_load}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].current_load = parseInt(e.target.value) || 0;
                  setAvailableSlots(newSlots);
                }}
                placeholder="%"
                style={{ width: '60px', fontSize: 'var(--mac-font-size-xs)' }}
              />
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderWorkloadAnalysis = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-danger)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <BarChart3 style={{ width: '16px', height: '16px' }} />
          Период анализа
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Временной период
            </label>
            <MacOSSelect
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value)}
              options={[
                { value: 'day', label: 'День' },
                { value: 'week', label: 'Неделя' },
                { value: 'month', label: 'Месяц' },
                { value: 'quarter', label: 'Квартал' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-warning-bg)', 
        border: '1px solid var(--mac-warning-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Users style={{ width: '16px', height: '16px' }} />
            Данные врачей
          </h4>
          <MacOSButton
            onClick={addDoctor}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить врача
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '160px', overflowY: 'auto' }}>
          {doctorsData.map((doctor, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSInput
                type="text"
                value={doctor.name}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].name = e.target.value;
                  setDoctorsData(newDoctors);
                }}
                placeholder="Имя врача"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={doctor.specialty}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].specialty = e.target.value;
                  setDoctorsData(newDoctors);
                }}
                placeholder="Специальность"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={doctor.total_working_hours}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].total_working_hours = parseInt(e.target.value) || 8;
                  setDoctorsData(newDoctors);
                }}
                placeholder="Часы"
                style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={doctor.patient_load}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].patient_load = parseInt(e.target.value) || 0;
                  setDoctorsData(newDoctors);
                }}
                placeholder="%"
                style={{ width: '60px', fontSize: 'var(--mac-font-size-xs)' }}
              />
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderShiftRecommendations = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-success-bg)', 
        border: '1px solid var(--mac-success-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-success)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Users style={{ width: '16px', height: '16px' }} />
          Информация об отделении
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Название отделения
            </label>
            <MacOSInput
              type="text"
              value={departmentData.name}
              onChange={(e) => setDepartmentData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Терапевтическое отделение"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-info-bg)', 
        border: '1px solid var(--mac-info-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <UserCheck style={{ width: '16px', height: '16px' }} />
            Персонал отделения
          </h4>
          <MacOSButton
            onClick={addStaffMember}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить сотрудника
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {departmentData.staff.map((staff, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSInput
                type="text"
                value={staff.name}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].name = e.target.value;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                placeholder="Имя сотрудника"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={staff.role}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].role = e.target.value;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                placeholder="Должность"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={staff.experience}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].experience = parseInt(e.target.value) || 0;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                placeholder="Опыт"
                style={{ width: '80px', fontSize: 'var(--mac-font-size-xs)' }}
              />
            </div>
          ))}
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-accent-bg)', 
        border: '1px solid var(--mac-accent-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-accent)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Settings style={{ width: '16px', height: '16px' }} />
          Требования к персоналу
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Минимум сотрудников на смену
            </label>
            <MacOSInput
              type="number"
              value={staffingRequirements.min_staff_per_shift}
              onChange={(e) => setStaffingRequirements(prev => ({ ...prev, min_staff_per_shift: parseInt(e.target.value) || 1 }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Часы покрытия
            </label>
            <MacOSSelect
              value={staffingRequirements.coverage_hours}
              onChange={(e) => setStaffingRequirements(prev => ({ ...prev, coverage_hours: e.target.value }))}
              options={[
                { value: '24/7', label: '24/7' },
                { value: '8-20', label: '8:00-20:00' },
                { value: '9-18', label: '9:00-18:00' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>
    </div>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-error-bg)', 
          border: '1px solid var(--mac-error-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
            marginTop: '8px',
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-danger)',
            margin: '8px 0 0 0'
          }}>
            {result.error}
          </p>
        </MacOSCard>
      );
    }

    return (
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
            Результат AI анализа
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            <MacOSButton
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Copy style={{ width: '16px', height: '16px' }} />
              Копировать
            </MacOSButton>
            <MacOSButton
              onClick={exportResult}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Download style={{ width: '16px', height: '16px' }} />
              Экспорт
            </MacOSButton>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {Object.entries(result).map(([key, value]) => (
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
                {typeof value === 'object' && value !== null ? (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    backgroundColor: 'var(--mac-bg-secondary)', 
                    padding: '8px', 
                    borderRadius: 'var(--mac-radius-sm)', 
                    fontSize: 'var(--mac-font-size-xs)', 
                    overflowX: 'auto', 
                    maxHeight: '256px',
                    margin: 0,
                    fontFamily: 'var(--mac-font-mono)'
                  }}>
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <p style={{ margin: 0 }}>{String(value)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </MacOSCard>
    );
  };

  return (
    <div style={{ 
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{ 
          paddingBottom: '24px', 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
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
          marginBottom: '24px'
        }}>
          {tabs.map(tab => {
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
                  gap: '8px',
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
                }}
              >
                <div style={{ 
                  width: '16px', 
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
                }}>
                  {tab.icon}
                </div>
                {tab.label}
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '0',
                    right: '0',
                    height: '3px',
                    backgroundColor: 'var(--mac-accent)',
                    borderRadius: '2px 2px 0 0'
                  }} />
                )}
              </button>
            );
          })}
        </div>
        
        {/* Разделительная линия */}
        <div style={{ 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }} />

        {/* Контент */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
          gap: '24px' 
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
            
            <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
              <MacOSButton
                onClick={handleSubmit}
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {loading ? (
                  <>
                    <Loader style={{ 
                      width: '20px', 
                      height: '20px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Анализируем...
                  </>
                ) : (
                  <>
                    <Zap style={{ width: '20px', height: '20px' }} />
                    Запустить AI анализ
                  </>
                )}
              </MacOSButton>
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
            
            {error && (
              <MacOSCard style={{ 
                padding: '16px', 
                backgroundColor: 'var(--mac-error-bg)', 
                border: '1px solid var(--mac-error-border)',
                marginTop: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
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
                  marginTop: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-danger)',
                  margin: '8px 0 0 0'
                }}>
                  {error}
                </p>
              </MacOSCard>
            )}
          </div>
        </div>
      </MacOSCard>
    </div>
  );
};

export default SmartScheduling;



