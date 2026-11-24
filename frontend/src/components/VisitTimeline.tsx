
import React from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { CheckCircle, Clock, AlertCircle, CreditCard, User, FileText, Pill } from 'lucide-react';
import { Card, Badge } from './ui/macos';
import { 
  APPOINTMENT_STATUS, 
  STATUS_LABELS, 
  STATUS_COLORS,
  getProgress 
} from '../constants/appointmentStatus';

interface VisitTimelineAppointment {
  created_at?: string;
  paid_at?: string;
  visit_started_at?: string;
  status?: string;
}

interface VisitTimelineRecord {
  /** DERMATIMELINE-FE-001: canonical backend fields (snake_case, per
   * backend/app/schemas/emr.py) — the parent feeds the raw status
   * payload and normalizes its own state to `is_draft`. */
  is_draft?: boolean | null;
  saved_at?: string | null;
  /** Legacy camelCase aliases, still accepted for older callers. */
  isDraft?: boolean;
  savedAt?: string;
}

/** DERMATIMELINE-FE-001: typed adapter at the component boundary — the
 * draft state comes from explicit `=== true` comparisons of the
 * canonical (or legacy alias) field, never from a truthiness fallback on
 * a wrong-cased field, so a true draft is no longer rendered as
 * completed. */
const normalizeTimelineRecord = (record: VisitTimelineRecord | null | undefined) => ({
  isDraft: record?.is_draft === true || record?.isDraft === true,
  savedAt: record?.saved_at ?? record?.savedAt ?? undefined,
});

// DERMATIMELINE-FE-002: queue-only visits feed the timeline the raw
// queue-entry status (the parent assigns row.status into
// currentAppointment.status, and for a visit without an appointment id
// the canonical status refresh touches only the EMR state). The
// appointment pipeline knows nothing about queue statuses, so an ACTIVE
// queue-only visit rendered 0% progress and an "Unknown" stage. The
// canonical SSOT queue state machine (types/state-machines/queue.ts:
// waiting → called → in_service → in_cabinet → served → completed) is
// projected onto the appointment stage it represents, with an explicit
// source-kind split: a queue source projects onto its canonical stage;
// unknown sources stay unknown instead of claiming a false 0% of the
// patient workflow.
const QUEUE_STAGE_PROJECTION: Record<string, string> = {
  waiting: APPOINTMENT_STATUS.PENDING,
  called: APPOINTMENT_STATUS.IN_VISIT,
  in_service: APPOINTMENT_STATUS.IN_VISIT,
  in_cabinet: APPOINTMENT_STATUS.IN_VISIT,
  served: APPOINTMENT_STATUS.COMPLETED,
  skipped: APPOINTMENT_STATUS.NO_SHOW,
  cancelled: APPOINTMENT_STATUS.CANCELLED,
};

type VisitStageSource = 'appointment' | 'queue' | 'unknown';
interface VisitStage {
  sourceKind: VisitStageSource;
  stage?: string;
}

const normalizeVisitStage = (status?: string): VisitStage => {
  if (!status) return { sourceKind: 'unknown' };
  if ((Object.values(APPOINTMENT_STATUS) as string[]).includes(status)) {
    return { sourceKind: 'appointment', stage: status };
  }
  const projected = QUEUE_STAGE_PROJECTION[status];
  if (projected) {
    return { sourceKind: 'queue', stage: projected };
  }
  return { sourceKind: 'unknown' };
};

interface VisitTimelineProps {
  appointment?: VisitTimelineAppointment | null;
  emr?: VisitTimelineRecord | null;
  prescription?: VisitTimelineRecord | null;
}

interface TimelineStep {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  status: 'completed' | 'current' | 'pending' | string;
  completedAt?: string;
}

const VisitTimeline = ({ appointment, emr, prescription }: VisitTimelineProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  // DERMATIMELINE-FE-001: normalize both records once through the typed
  // adapter before any status/next-step decision.
  const emrState = normalizeTimelineRecord(emr);
  const prescriptionState = normalizeTimelineRecord(prescription);
  // DERMATIMELINE-FE-002: normalize the visit stage once (with its
  // source-kind) and drive every step/progress/label decision from it.
  const visitStage = normalizeVisitStage(appointment?.status);
  const stage = visitStage.stage;
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
      status: stage === APPOINTMENT_STATUS.PENDING ? 'current' :
              stage === APPOINTMENT_STATUS.PAID ||
              stage === APPOINTMENT_STATUS.IN_VISIT ||
              stage === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.paid_at
    },
    {
      id: 'visit',
      title: t('final.timeline_doctor_visit'),
      description: t('misc.vt_nachalo_priema'),
      icon: User,
      status: stage === APPOINTMENT_STATUS.IN_VISIT ? 'current' :
              stage === APPOINTMENT_STATUS.COMPLETED ? 'completed' : 'pending',
      completedAt: appointment?.visit_started_at
    },
    {
      id: 'emr',
      title: t('final.timeline_emr'),
      description: t('misc.vt_elektronnaya_meditsinskaya_k'),
      icon: FileText,
      status: emr ? (emrState.isDraft ? 'current' : 'completed') : 'pending',
      completedAt: emrState.savedAt
    },
    {
      id: 'prescription',
      title: t('final.timeline_prescription'),
      description: t('misc.vt_naznachenie_preparatov'),
      icon: Pill,
      status: prescription ? (prescriptionState.isDraft ? 'current' : 'completed') : 'pending',
      completedAt: prescriptionState.savedAt
    }
  ];

  const getStepIcon = (step: TimelineStep) => {
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

  const getStepColor = (step: TimelineStep) => {
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

  const progress = getProgress(stage ?? '');

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold">{t('misc.vt_progress_vizita')}</h3>
        <div className="flex items-center gap-2">
          <div className="text-sm text-gray-600">
            {visitStage.sourceKind === 'unknown' ? '—' : `${Math.round(progress)}%`}
          </div>
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
              {stage ? STATUS_LABELS[stage as keyof typeof STATUS_LABELS] || t('misc.vt_neizvestno') : t('misc.vt_neizvestno')}
            </div>
          </div>
          <Badge variant={stage ? STATUS_COLORS[stage as keyof typeof STATUS_COLORS] as unknown as "default" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "outline" : 'default' as never}>
            {stage ? STATUS_LABELS[stage as keyof typeof STATUS_LABELS] || t('misc.vt_neizvestno') : t('misc.vt_neizvestno')}
          </Badge>
        </div>
      </div>

      {/* Следующий шаг */}
      {stage !== undefined && stage !== APPOINTMENT_STATUS.COMPLETED && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-blue-600" />
            <div className="font-medium text-blue-900">{t('misc.vt_sleduyuschiy_shag')}</div>
          </div>
          <div className="text-sm text-blue-700">
            {stage === APPOINTMENT_STATUS.PENDING &&
              t('misc.vt_ozhidaetsya_oplata_zapisi_dl')}
            {stage === APPOINTMENT_STATUS.PAID &&
              t('misc.vt_mozhno_nachat_priem_u_vracha')}
            {stage === APPOINTMENT_STATUS.IN_VISIT &&
              (!emr ? t('misc.vt_sozdayte_emk_dlya_zapisi_pri') :
               emrState.isDraft ? t('misc.vt_sohranite_emk_dlya_zavershen') :
               !prescription ? t('misc.vt_oformite_retsept_optsionalno') :
               t('misc.vt_priem_gotov_k_zaversheniyu'))}
          </div>
        </div>
      )}
    </Card>
  );
};


export default VisitTimeline;

