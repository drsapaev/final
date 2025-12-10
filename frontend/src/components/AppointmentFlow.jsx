import React, { useState } from 'react';
import { CreditCard, User, FileText, Pill, CheckCircle, AlertCircle } from 'lucide-react';
import { Card, Button, Badge } from './ui/native';
import logger from '../utils/logger';
import { 
  APPOINTMENT_STATUS, 
  STATUS_LABELS, 
  STATUS_COLORS,
  canStartVisit,
  canCreatePrescription 
} from '../constants/appointmentStatus';

const AppointmentFlow = ({ appointment, onStartVisit, onPayment }) => {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleStartVisit = async () => {
    if (!canStartVisit(appointment?.status)) return;
    
    setIsProcessing(true);
    try {
      await onStartVisit(appointment);
    } catch (error) {
      logger.error('AppointmentFlow: Start visit error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePayment = async () => {
    setIsProcessing(true);
    try {
      await onPayment(appointment);
    } catch (error) {
      logger.error('AppointmentFlow: Payment error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const getStepIcon = (step, status) => {
    switch (step) {
      case 'payment':
        return <CreditCard className="w-5 h-5" />;
      case 'visit':
        return <User className="w-5 h-5" />;
      case 'emr':
        return <FileText className="w-5 h-5" />;
      case 'prescription':
        return <Pill className="w-5 h-5" />;
      default:
        return <CheckCircle className="w-5 h-5" />;
    }
  };

  const getStepStatus = (step) => {
    switch (step) {
      case 'payment':
        return appointment?.status === APPOINTMENT_STATUS.PENDING ? 'current' :
               appointment?.status === APPOINTMENT_STATUS.PAID || 
               appointment?.status === APPOINTMENT_STATUS.IN_VISIT || 
               appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending';
      case 'visit':
        return appointment?.status === APPOINTMENT_STATUS.IN_VISIT ? 'current' :
               appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending';
      case 'emr':
        return appointment?.emr && !appointment.emr.isDraft ? 'completed' :
               appointment?.emr && appointment.emr.isDraft ? 'current' : 'pending';
      case 'prescription':
        return appointment?.prescription && !appointment.prescription.isDraft ? 'completed' :
               appointment?.prescription && appointment.prescription.isDraft ? 'current' : 'pending';
      default:
        return 'pending';
    }
  };

  const getStepColor = (status) => {
    switch (status) {
      case 'completed':
        return 'border-green-500 bg-green-50 text-green-700';
      case 'current':
        return 'border-blue-500 bg-blue-50 text-blue-700';
      case 'pending':
        return 'border-gray-300 bg-gray-50 text-gray-500';
      default:
        return 'border-gray-300 bg-gray-50 text-gray-500';
    }
  };

  const steps = [
    {
      id: 'payment',
      title: 'Оплата',
      description: 'Ожидание оплаты записи',
      action: appointment?.status === APPOINTMENT_STATUS.PENDING ? 'Оплатить' : null
    },
    {
      id: 'visit',
      title: 'Начать прием',
      description: 'Отправить пациента к врачу',
      action: canStartVisit(appointment?.status) ? 'Начать прием' : null
    },
    {
      id: 'emr',
      title: 'ЭМК',
      description: 'Электронная медицинская карта',
      action: null
    },
    {
      id: 'prescription',
      title: 'Рецепт',
      description: 'Назначение препаратов',
      action: null
    }
  ];

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-6">
        <CheckCircle className="w-6 h-6 text-blue-600" />
        <div>
          <h3 className="text-lg font-semibold">Поток записи</h3>
          <p className="text-sm text-gray-600">
            {appointment?.patient_name} • {appointment?.specialist}
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {steps.map((step, index) => {
          const status = getStepStatus(step.id);
          const colorClass = getStepColor(status);
          
          return (
            <div key={step.id} className="relative">
              {/* Соединительная линия */}
              {index < steps.length - 1 && (
                <div className={`absolute left-6 top-10 w-0.5 h-8 ${
                  status === 'completed' ? 'bg-green-500' : 'bg-gray-300'
                }`} />
              )}
              
              <div className={`flex items-center gap-4 p-4 rounded-lg border-2 ${colorClass}`}>
                <div className="flex-shrink-0">
                  {getStepIcon(step.id, status)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium">{step.title}</h4>
                    <Badge 
                      variant={
                        status === 'completed' ? 'success' :
                        status === 'current' ? 'info' : 'secondary'
                      }
                      size="sm"
                    >
                      {status === 'completed' ? 'Готово' :
                       status === 'current' ? 'В процессе' : 'Ожидание'}
                    </Badge>
                  </div>
                  
                  <p className="text-sm opacity-75">{step.description}</p>
                </div>
                
                {step.action && (
                  <div className="flex-shrink-0">
                    <Button
                      size="sm"
                      onClick={step.id === 'payment' ? handlePayment : handleStartVisit}
                      disabled={isProcessing}
                    >
                      {isProcessing ? 'Обработка...' : step.action}
                    </Button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Текущий статус */}
      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Статус записи</div>
            <div className="text-sm text-gray-600">
              {STATUS_LABELS[appointment?.status] || 'Неизвестно'}
            </div>
          </div>
          <Badge variant={STATUS_COLORS[appointment?.status]}>
            {STATUS_LABELS[appointment?.status]}
          </Badge>
        </div>
      </div>

      {/* Предупреждения */}
      {appointment?.status === APPOINTMENT_STATUS.PENDING && (
        <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-yellow-600" />
            <div className="font-medium text-yellow-900">Требуется оплата</div>
          </div>
          <div className="text-sm text-yellow-700">
            Запись не может быть передана врачу без предварительной оплаты
          </div>
        </div>
      )}

      {appointment?.status === APPOINTMENT_STATUS.PAID && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <div className="font-medium text-green-900">Готово к приему</div>
          </div>
          <div className="text-sm text-green-700">
            Запись оплачена, можно отправлять пациента к врачу
          </div>
        </div>
      )}
    </Card>
  );
};

export default AppointmentFlow;

