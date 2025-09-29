import React from 'react';
import { CheckCircle, Clock, AlertCircle, CreditCard, User, FileText, Pill } from 'lucide-react';
import { Card, Badge } from './ui/native';
import { 
  APPOINTMENT_STATUS, 
  STATUS_LABELS, 
  STATUS_COLORS,
  getProgress 
} from '../constants/appointmentStatus';

const VisitTimeline = ({ appointment, emr, prescription }) => {
  const timelineSteps = [
    {
      id: 'appointment',
      title: 'Запись создана',
      description: 'Пациент записан на прием',
      icon: Clock,
      status: 'completed',
      completedAt: appointment?.created_at
    },
    {
      id: 'payment',
      title: 'Оплата',
      description: 'Ожидание оплаты записи',
      icon: CreditCard,
      status: appointment?.status === APPOINTMENT_STATUS.PENDING ? 'current' : 
              appointment?.status === APPOINTMENT_STATUS.PAID || 
              appointment?.status === APPOINTMENT_STATUS.IN_VISIT || 
              appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.paid_at
    },
    {
      id: 'visit',
      title: 'Прием у врача',
      description: 'Начало приема',
      icon: User,
      status: appointment?.status === APPOINTMENT_STATUS.IN_VISIT ? 'current' :
              appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.visit_started_at
    },
    {
      id: 'emr',
      title: 'ЭМК',
      description: 'Электронная медицинская карта',
      icon: FileText,
      status: emr && !emr.isDraft ? 'completed' :
              emr && emr.isDraft ? 'current' : 'pending',
      completedAt: emr?.savedAt
    },
    {
      id: 'prescription',
      title: 'Рецепт',
      description: 'Назначение препаратов',
      icon: Pill,
      status: prescription && !prescription.isDraft ? 'completed' :
              prescription && prescription.isDraft ? 'current' : 'pending',
      completedAt: prescription?.savedAt
    }
  ];

  const getStepIcon = (step) => {
    const IconComponent = step.icon;
    
    switch (step.status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'current':
        return <IconComponent className="w-5 h-5 text-blue-500" />;
      case 'pending':
        return <IconComponent className="w-5 h-5 text-gray-400" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStepColor = (step) => {
    switch (step.status) {
      case 'completed':
        return 'border-green-500 bg-green-50';
      case 'current':
        return 'border-blue-500 bg-blue-50';
      case 'pending':
        return 'border-gray-300 bg-gray-50';
      default:
        return 'border-gray-300 bg-gray-50';
    }
  };

  const progress = getProgress(appointment?.status);

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">Прогресс визита</h3>
        <div className="flex items-center gap-2">
          <div className="text-sm text-gray-600">{Math.round(progress)}%</div>
          <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {timelineSteps.map((step, index) => (
          <div key={step.id} className="relative">
            {/* Соединительная линия */}
            {index < timelineSteps.length - 1 && (
              <div className={`absolute left-6 top-10 w-0.5 h-8 ${
                step.status === 'completed' ? 'bg-green-500' : 'bg-gray-300'
              }`} />
            )}
            
            <div className={`flex items-start gap-4 p-4 rounded-lg border-2 ${getStepColor(step)}`}>
              <div className="flex-shrink-0">
                {getStepIcon(step)}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="font-medium text-gray-900">{step.title}</h4>
                  <Badge 
                    variant={
                      step.status === 'completed' ? 'success' :
                      step.status === 'current' ? 'info' : 'secondary'
                    }
                    size="sm"
                  >
                    {step.status === 'completed' ? 'Готово' :
                     step.status === 'current' ? 'В процессе' : 'Ожидание'}
                  </Badge>
                </div>
                
                <p className="text-sm text-gray-600 mb-2">{step.description}</p>
                
                {step.completedAt && (
                  <div className="text-xs text-gray-500">
                    Завершено: {new Date(step.completedAt).toLocaleString('ru-RU')}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Текущий статус */}
      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Текущий статус</div>
            <div className="text-sm text-gray-600">
              {STATUS_LABELS[appointment?.status] || 'Неизвестно'}
            </div>
          </div>
          <Badge variant={STATUS_COLORS[appointment?.status]}>
            {STATUS_LABELS[appointment?.status]}
          </Badge>
        </div>
      </div>

      {/* Следующий шаг */}
      {appointment?.status !== APPOINTMENT_STATUS.COMPLETED && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-blue-600" />
            <div className="font-medium text-blue-900">Следующий шаг</div>
          </div>
          <div className="text-sm text-blue-700">
            {appointment?.status === APPOINTMENT_STATUS.PENDING && 
              'Ожидается оплата записи для начала приема'}
            {appointment?.status === APPOINTMENT_STATUS.PAID && 
              'Можно начать прием у врача'}
            {appointment?.status === APPOINTMENT_STATUS.IN_VISIT && 
              (!emr ? 'Создайте ЭМК для записи приема' :
               emr.isDraft ? 'Сохраните ЭМК для завершения приема' :
               !prescription ? 'Оформите рецепт (опционально)' :
               'Прием готов к завершению')}
          </div>
        </div>
      )}
    </Card>
  );
};

export default VisitTimeline;

