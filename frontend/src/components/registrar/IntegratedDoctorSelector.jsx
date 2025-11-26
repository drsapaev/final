import React, { useState, useEffect } from 'react';
import { 
  Heart, 
  Stethoscope, 
  Scissors, 
  User,
  Calendar,
  Clock,
  MapPin,
  RefreshCw,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { Card, Badge } from '../ui/native';

/**
 * Интегрированный селектор врачей для регистратуры
 * Использует данные врачей и расписаний из админ панели
 */
const IntegratedDoctorSelector = ({ 
  selectedDoctorId = null, 
  onDoctorChange,
  specialty = null,
  showSchedule = true,
  className = ''
}) => {
  const [loading, setLoading] = useState(true);
  const [doctors, setDoctors] = useState([]);
  const [queueSettings, setQueueSettings] = useState({});
  const [error, setError] = useState('');

  // Иконки специальностей
  const specialtyIcons = {
    cardiology: Heart,
    dermatology: Stethoscope,
    stomatology: Scissors
  };

  const specialtyColors = {
    cardiology: 'text-red-600',
    dermatology: 'text-orange-600',
    stomatology: 'text-blue-600'
  };

  const specialtyNames = {
    cardiology: 'Кардиология',
    dermatology: 'Дерматология',
    stomatology: 'Стоматология'
  };

  const weekdayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // Загружаем врачей и настройки очередей
      const token = localStorage.getItem('auth_token');
      const [doctorsRes, queueRes] = await Promise.all([
        fetch('/api/v1/registrar/doctors', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/registrar/queue-settings', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (doctorsRes.ok) {
        const doctorsData = await doctorsRes.json();
        setDoctors(doctorsData.doctors);
      }

      if (queueRes.ok) {
        const queueData = await queueRes.json();
        setQueueSettings(queueData);
      }

    } catch (err) {
      console.error('Ошибка загрузки данных врачей:', err);
      setError('Ошибка загрузки данных врачей');
    } finally {
      setLoading(false);
    }
  };

  const handleDoctorSelect = (doctor) => {
    onDoctorChange(doctor);
  };

  const getWorkingDays = (schedules) => {
    return schedules
      .filter(s => s.active && s.start_time && s.end_time)
      .map(s => ({
        weekday: s.weekday,
        time: `${s.start_time}-${s.end_time}`,
        breaks: s.breaks
      }));
  };

  const getQueueInfo = (doctor) => {
    const specialty = doctor.specialty;
    const specialtySettings = queueSettings.specialties?.[specialty];
    
    if (!specialtySettings) return null;

    return {
      startNumber: specialtySettings.start_number,
      maxPerDay: specialtySettings.max_per_day,
      queueRange: `${specialtySettings.start_number}-${specialtySettings.start_number + specialtySettings.max_per_day - 1}`
    };
  };

  if (loading) {
    return (
      <Card className={`p-4 ${className}`}>
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка врачей...</span>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={`p-4 ${className}`}>
        <div className="flex items-center text-red-600">
          <AlertCircle size={20} className="mr-2" />
          <span>{error}</span>
        </div>
      </Card>
    );
  }

  if (doctors.length === 0) {
    return (
      <Card className={`p-8 text-center ${className}`}>
        <User size={48} className="mx-auto text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
          Врачи не найдены
        </h3>
        <p className="text-gray-500">
          {specialty ? `Нет врачей специальности "${specialty}"` : 'Добавьте врачей в админ панели'}
        </p>
      </Card>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {doctors.map(doctor => {
        const isSelected = selectedDoctorId === doctor.id;
        const SpecialtyIcon = specialtyIcons[doctor.specialty] || User;
        const iconColor = specialtyColors[doctor.specialty] || 'text-gray-600';
        const queueInfo = getQueueInfo(doctor);
        const workingDays = getWorkingDays(doctor.schedules || []);

        return (
          <Card
            key={doctor.id}
            className={`p-4 cursor-pointer transition-all ${
              isSelected
                ? 'ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-900/20'
                : 'hover:shadow-md hover:bg-gray-50 dark:hover:bg-gray-800'
            }`}
            onClick={() => handleDoctorSelect(doctor)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <SpecialtyIcon size={24} className={iconColor} />
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-1">
                    <h4 className="text-lg font-medium text-gray-900 dark:text-white">
                      {doctor.user?.full_name || `Врач #${doctor.id}`}
                    </h4>
                    {isSelected && (
                      <CheckCircle size={20} className="text-blue-600" />
                    )}
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
                      <Badge variant="outline" className="mr-2">
                        {specialtyNames[doctor.specialty] || doctor.specialty}
                      </Badge>
                      {doctor.cabinet && (
                        <>
                          <MapPin size={14} className="mr-1" />
                          Каб. {doctor.cabinet}
                        </>
                      )}
                    </div>
                    
                    {doctor.price_default > 0 && (
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        Базовая цена: {doctor.price_default.toLocaleString()} UZS
                      </div>
                    )}
                    
                    {/* Информация об очереди */}
                    {queueInfo && (
                      <div className="text-sm text-blue-600 dark:text-blue-400">
                        Онлайн-очередь: №{queueInfo.queueRange} (макс. {queueInfo.maxPerDay}/день)
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Расписание врача */}
            {showSchedule && workingDays.length > 0 && (
              <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
                <div className="flex items-center mb-2">
                  <Calendar size={16} className="mr-2 text-gray-500" />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Расписание:
                  </span>
                </div>
                <div className="grid grid-cols-7 gap-1">
                  {weekdayNames.map((dayName, dayIndex) => {
                    const daySchedule = workingDays.find(s => s.weekday === dayIndex);
                    
                    return (
                      <div
                        key={dayIndex}
                        className={`text-center p-1 rounded text-xs ${
                          daySchedule
                            ? 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
                            : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500'
                        }`}
                      >
                        <div className="font-medium">{dayName}</div>
                        {daySchedule && (
                          <div className="mt-1">
                            <Clock size={10} className="inline mr-1" />
                            {daySchedule.time}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};

export default IntegratedDoctorSelector;

