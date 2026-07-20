
import { useTranslation } from '../i18n/useTranslation';
import { CheckCircle, Clock, AlertCircle, CreditCard, User, FileText, Pill } from 'lucide-react';
import PropTypes from 'prop-types';
import { Card, Badge } from './ui/macos';
import { 
  APPOINTMENT_STATUS, 
  STATUS_LABELS, 
  STATUS_COLORS,
  getProgress 
} from '../constants/appointmentStatus';

const VisitTimeline = ({ appointment, emr, prescription }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const timelineSteps = [
    {
      id: 'appointment',
      title: t('final.timeline_appointment_created'),
      description: t('misc.vt_patsient_zapisan_na_priem'),
      icon: Clock,
      status: 'completed',
      completedAt: appointment?.created_at
    },
    {
      id: 'payment',
      title: t('final.timeline_payment'),
      description: t('misc.vt_ozhidanie_oplaty_zapisi'),
      icon: CreditCard,
      status: appointment?.status === APPOINTMENT_STATUS.PENDING ? 'current' : 
              appointment?.status === APPOINTMENT_STATUS.PAID || 
              appointment?.status === APPOINTMENT_STATUS.IN_VISIT || 
              appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.paid_at
    },
    {
      id: 'visit',
      title: t('final.timeline_doctor_visit'),
      description: t('misc.vt_nachalo_priema'),
      icon: User,
      status: appointment?.status === APPOINTMENT_STATUS.IN_VISIT ? 'current' :
              appointment?.status === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.visit_started_at
    },
    {
      id: 'emr',
      title: t('final.timeline_emr'),
      description: t('misc.vt_elektronnaya_meditsinskaya_k'),
      icon: FileText,
      status: emr && !emr.isDraft ? 'completed' :
              emr && emr.isDraft ? 'current' : 'pending',
      completedAt: emr?.savedAt
    },
    {
      id: 'prescription',
      title: t('final.timeline_prescription'),
      description: t('misc.vt_naznachenie_preparatov'),
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
        <h3 className="text-lg font-semibold">{t('misc.vt_progress_vizita')}</h3>
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
                    size="small"
                  >
                    {step.status === 'completed' ? t('misc.vt_gotovo') :
                     step.status === 'current' ? t('misc.vt_v_protsesse') : t('misc.vt_ozhidanie')}
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
            <div className="font-medium">{t('misc.vt_tekuschiy_status')}</div>
            <div className="text-sm text-gray-600">
              {STATUS_LABELS[appointment?.status] || t('misc.vt_neizvestno')}
            </div>
          </div>
          <Badge variant={STATUS_COLORS[appointment?.status] as unknown as "default" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "outline"}>
            {STATUS_LABELS[appointment?.status]}
          </Badge>
        </div>
      </div>

      {/* Следующий шаг */}
      {appointment?.status !== APPOINTMENT_STATUS.COMPLETED && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-blue-600" />
            <div className="font-medium text-blue-900">{t('misc.vt_sleduyuschiy_shag')}</div>
          </div>
          <div className="text-sm text-blue-700">
            {appointment?.status === APPOINTMENT_STATUS.PENDING && 
              t('misc.vt_ozhidaetsya_oplata_zapisi_dl')}
            {appointment?.status === APPOINTMENT_STATUS.PAID && 
              t('misc.vt_mozhno_nachat_priem_u_vracha')}
            {appointment?.status === APPOINTMENT_STATUS.IN_VISIT && 
              (!emr ? t('misc.vt_sozdayte_emk_dlya_zapisi_pri') :
               emr.isDraft ? t('misc.vt_sohranite_emk_dlya_zavershen') :
               !prescription ? t('misc.vt_oformite_retsept_optsionalno') :
               t('misc.vt_priem_gotov_k_zaversheniyu'))}
          </div>
        </div>
      )}
    </Card>
  );
};

VisitTimeline.propTypes = {
  appointment: PropTypes.object,
  emr: PropTypes.object,
  prescription: PropTypes.object
};

export default VisitTimeline;

