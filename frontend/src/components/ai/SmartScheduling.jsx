import React, { useState, useEffect } from 'react';
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
  Activity
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

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
      console.error('AI analysis error:', err);
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
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-3 flex items-center">
          <UserCheck className="w-4 h-4 mr-2" />
          Информация о враче
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Имя врача</label>
            <input
              type="text"
              value={scheduleData.doctor.name}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, name: e.target.value }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Доктор Иванов"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Специальность</label>
            <input
              type="text"
              value={scheduleData.doctor.specialty}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, specialty: e.target.value }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Кардиолог"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Опыт работы (лет)</label>
            <input
              type="number"
              value={scheduleData.doctor.experience_years}
              onChange={(e) => setScheduleData(prev => ({
                ...prev,
                doctor: { ...prev.doctor, experience_years: parseInt(e.target.value) || 0 }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="10"
            />
          </div>
        </div>
      </div>

      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="font-medium text-green-900 mb-3 flex items-center">
          <Settings className="w-4 h-4 mr-2" />
          Ограничения и требования
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Начало рабочего дня</label>
            <input
              type="time"
              value={constraints.working_hours.start}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                working_hours: { ...prev.working_hours, start: e.target.value }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Конец рабочего дня</label>
            <input
              type="time"
              value={constraints.working_hours.end}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                working_hours: { ...prev.working_hours, end: e.target.value }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Максимум пациентов в день</label>
            <input
              type="number"
              value={constraints.max_patients_per_day}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                max_patients_per_day: parseInt(e.target.value) || 15
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Обеденный перерыв (мин)</label>
            <input
              type="number"
              value={constraints.break_requirements.lunch_break}
              onChange={(e) => setConstraints(prev => ({
                ...prev,
                break_requirements: { ...prev.break_requirements, lunch_break: parseInt(e.target.value) || 60 }
              }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-yellow-900 flex items-center">
            <ClipboardList className="w-4 h-4 mr-2" />
            Текущее расписание
          </h4>
          <button
            onClick={addScheduleSlot}
            className="px-3 py-1 bg-yellow-600 text-white rounded-md text-sm hover:bg-yellow-700"
          >
            Добавить слот
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {scheduleData.current_schedule.map((slot, index) => (
            <div key={index} className="flex space-x-2">
              <input
                type="time"
                value={slot.time}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].time = e.target.value;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <select
                value={slot.type}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].type = e.target.value;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="free">Свободно</option>
                <option value="appointment">Прием</option>
                <option value="break">Перерыв</option>
                <option value="admin">Админ. работа</option>
              </select>
              <input
                type="number"
                value={slot.duration}
                onChange={(e) => {
                  const newSchedule = [...scheduleData.current_schedule];
                  newSchedule[index].duration = parseInt(e.target.value) || 30;
                  setScheduleData(prev => ({ ...prev, current_schedule: newSchedule }));
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="мин"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderDurationPrediction = () => (
    <div className="space-y-6">
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="font-medium text-purple-900 mb-3 flex items-center">
          <Activity className="w-4 h-4 mr-2" />
          Данные о приеме
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Тип приема</label>
            <select
              value={appointmentData.type}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, type: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="consultation">Консультация</option>
              <option value="follow-up">Повторный прием</option>
              <option value="procedure">Процедура</option>
              <option value="emergency">Экстренный</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Специальность врача</label>
            <input
              type="text"
              value={appointmentData.doctor_specialty}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, doctor_specialty: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Кардиолог"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Жалоба пациента</label>
            <input
              type="text"
              value={appointmentData.complaint}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, complaint: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Боли в груди"
            />
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="first_visit"
              checked={appointmentData.is_first_visit}
              onChange={(e) => setAppointmentData(prev => ({ ...prev, is_first_visit: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="first_visit" className="ml-2 text-sm text-gray-700">
              Первичный визит
            </label>
          </div>
        </div>
      </div>

      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-indigo-900 flex items-center">
            <BarChart3 className="w-4 h-4 mr-2" />
            Исторические данные
          </h4>
          <button
            onClick={addHistoricalRecord}
            className="px-3 py-1 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
          >
            Добавить запись
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {historicalData.map((record, index) => (
            <div key={index} className="flex space-x-2">
              <select
                value={record.type}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].type = e.target.value;
                  setHistoricalData(newData);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="consultation">Консультация</option>
                <option value="follow-up">Повторный</option>
                <option value="procedure">Процедура</option>
              </select>
              <input
                type="number"
                value={record.actual_duration}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].actual_duration = parseInt(e.target.value) || 30;
                  setHistoricalData(newData);
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="мин"
              />
              <input
                type="text"
                value={record.complaint}
                onChange={(e) => {
                  const newData = [...historicalData];
                  newData[index].complaint = e.target.value;
                  setHistoricalData(newData);
                }}
                className="flex-2 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Жалоба"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderOptimalSlots = () => (
    <div className="space-y-6">
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="font-medium text-green-900 mb-3 flex items-center">
          <UserCheck className="w-4 h-4 mr-2" />
          Профиль врача
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Имя врача</label>
            <input
              type="text"
              value={doctorProfile.name}
              onChange={(e) => setDoctorProfile(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Доктор Петров"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Специальность</label>
            <input
              type="text"
              value={doctorProfile.specialty}
              onChange={(e) => setDoctorProfile(prev => ({ ...prev, specialty: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Терапевт"
            />
          </div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-3 flex items-center">
          <Target className="w-4 h-4 mr-2" />
          Требования пациента
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Срочность</label>
            <select
              value={patientRequirements.urgency}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, urgency: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="normal">Обычная</option>
              <option value="urgent">Срочная</option>
              <option value="emergency">Экстренная</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Тип приема</label>
            <select
              value={patientRequirements.type}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, type: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="consultation">Консультация</option>
              <option value="follow-up">Повторный прием</option>
              <option value="procedure">Процедура</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ожидаемая длительность (мин)</label>
            <input
              type="number"
              value={patientRequirements.estimated_duration}
              onChange={(e) => setPatientRequirements(prev => ({ ...prev, estimated_duration: parseInt(e.target.value) || 30 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-yellow-900 flex items-center">
            <Clock className="w-4 h-4 mr-2" />
            Доступные слоты
          </h4>
          <button
            onClick={addAvailableSlot}
            className="px-3 py-1 bg-yellow-600 text-white rounded-md text-sm hover:bg-yellow-700"
          >
            Добавить слот
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {availableSlots.map((slot, index) => (
            <div key={index} className="flex space-x-2">
              <input
                type="date"
                value={slot.date}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].date = e.target.value;
                  setAvailableSlots(newSlots);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <input
                type="time"
                value={slot.time}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].time = e.target.value;
                  setAvailableSlots(newSlots);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <input
                type="number"
                value={slot.duration}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].duration = parseInt(e.target.value) || 30;
                  setAvailableSlots(newSlots);
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="мин"
              />
              <input
                type="number"
                value={slot.current_load}
                onChange={(e) => {
                  const newSlots = [...availableSlots];
                  newSlots[index].current_load = parseInt(e.target.value) || 0;
                  setAvailableSlots(newSlots);
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="%"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderWorkloadAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="font-medium text-red-900 mb-3 flex items-center">
          <BarChart3 className="w-4 h-4 mr-2" />
          Период анализа
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Временной период</label>
            <select
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="day">День</option>
              <option value="week">Неделя</option>
              <option value="month">Месяц</option>
              <option value="quarter">Квартал</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-orange-900 flex items-center">
            <Users className="w-4 h-4 mr-2" />
            Данные врачей
          </h4>
          <button
            onClick={addDoctor}
            className="px-3 py-1 bg-orange-600 text-white rounded-md text-sm hover:bg-orange-700"
          >
            Добавить врача
          </button>
        </div>
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {doctorsData.map((doctor, index) => (
            <div key={index} className="flex space-x-2">
              <input
                type="text"
                value={doctor.name}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].name = e.target.value;
                  setDoctorsData(newDoctors);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Имя врача"
              />
              <input
                type="text"
                value={doctor.specialty}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].specialty = e.target.value;
                  setDoctorsData(newDoctors);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Специальность"
              />
              <input
                type="number"
                value={doctor.total_working_hours}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].total_working_hours = parseInt(e.target.value) || 8;
                  setDoctorsData(newDoctors);
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Часы"
              />
              <input
                type="number"
                value={doctor.patient_load}
                onChange={(e) => {
                  const newDoctors = [...doctorsData];
                  newDoctors[index].patient_load = parseInt(e.target.value) || 0;
                  setDoctorsData(newDoctors);
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="%"
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderShiftRecommendations = () => (
    <div className="space-y-6">
      <div className="bg-teal-50 border border-teal-200 rounded-lg p-4">
        <h4 className="font-medium text-teal-900 mb-3 flex items-center">
          <Users className="w-4 h-4 mr-2" />
          Информация об отделении
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название отделения</label>
            <input
              type="text"
              value={departmentData.name}
              onChange={(e) => setDepartmentData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Терапевтическое отделение"
            />
          </div>
        </div>
      </div>

      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-cyan-900 flex items-center">
            <UserCheck className="w-4 h-4 mr-2" />
            Персонал отделения
          </h4>
          <button
            onClick={addStaffMember}
            className="px-3 py-1 bg-cyan-600 text-white rounded-md text-sm hover:bg-cyan-700"
          >
            Добавить сотрудника
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {departmentData.staff.map((staff, index) => (
            <div key={index} className="flex space-x-2">
              <input
                type="text"
                value={staff.name}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].name = e.target.value;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Имя сотрудника"
              />
              <input
                type="text"
                value={staff.role}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].role = e.target.value;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Должность"
              />
              <input
                type="number"
                value={staff.experience}
                onChange={(e) => {
                  const newStaff = [...departmentData.staff];
                  newStaff[index].experience = parseInt(e.target.value) || 0;
                  setDepartmentData(prev => ({ ...prev, staff: newStaff }));
                }}
                className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Опыт"
              />
            </div>
          ))}
        </div>
      </div>

      <div className="bg-pink-50 border border-pink-200 rounded-lg p-4">
        <h4 className="font-medium text-pink-900 mb-3 flex items-center">
          <Settings className="w-4 h-4 mr-2" />
          Требования к персоналу
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Минимум сотрудников на смену</label>
            <input
              type="number"
              value={staffingRequirements.min_staff_per_shift}
              onChange={(e) => setStaffingRequirements(prev => ({ ...prev, min_staff_per_shift: parseInt(e.target.value) || 1 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Часы покрытия</label>
            <select
              value={staffingRequirements.coverage_hours}
              onChange={(e) => setStaffingRequirements(prev => ({ ...prev, coverage_hours: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="24/7">24/7</option>
              <option value="8-20">8:00-20:00</option>
              <option value="9-18">9:00-18:00</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
            <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
          </div>
          <p className="mt-2 text-sm text-red-700">{result.error}</p>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
            Результат AI анализа
          </h3>
          <div className="flex space-x-2">
            <button
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Copy className="h-4 w-4 mr-1" />
              Копировать
            </button>
            <button
              onClick={exportResult}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              Экспорт
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {Object.entries(result).map(([key, value]) => (
            <div key={key} className="border-l-4 border-blue-400 pl-4">
              <h4 className="font-medium text-gray-900 capitalize mb-2">
                {key.replace(/_/g, ' ')}
              </h4>
              <div className="text-sm text-gray-600">
                {typeof value === 'object' && value !== null ? (
                  <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-xs overflow-x-auto max-h-64">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <p>{String(value)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <Brain className="h-6 w-6 text-blue-600 mr-2" />
            AI Умное Планирование Расписания Врачей
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Оптимизация расписаний, прогнозирование длительности приемов и анализ рабочей нагрузки
          </p>
        </div>

        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Настройки и данные
              </h3>
              
              {activeTab === 'schedule-optimization' && renderScheduleOptimization()}
              {activeTab === 'duration-prediction' && renderDurationPrediction()}
              {activeTab === 'optimal-slots' && renderOptimalSlots()}
              {activeTab === 'workload-analysis' && renderWorkloadAnalysis()}
              {activeTab === 'shift-recommendations' && renderShiftRecommendations()}
              
              <div className="mt-6 flex justify-center">
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                      Анализируем...
                    </>
                  ) : (
                    <>
                      <Zap className="h-5 w-5 mr-2" />
                      Запустить AI анализ
                    </>
                  )}
                </button>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Результат</h3>
              {renderResult()}
              
              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center">
                    <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
                    <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
                  </div>
                  <p className="mt-2 text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SmartScheduling;



