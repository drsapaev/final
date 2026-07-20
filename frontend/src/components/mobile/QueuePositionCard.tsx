
import {
  Card, Badge,
} from '../ui/macos';
import { Clock, User } from 'lucide-react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const QueuePositionCard = ({ queueEntry }: any) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  if (!queueEntry) return null;

  const {

    number,
    status,
    peopleBefore,
    estimatedWaitTime,
    doctorName,
    specialty,
    cabinet
  } = queueEntry;

  // Определение цветов и текстов в зависимости от статуса
  const getStatusConfig = (status) => {
    switch (status) {
      case 'waiting':
        return {
          color: 'var(--mac-accent-blue)',
          bgColor: 'var(--mac-accent-bg)',
          text: t('misc.qpc_v_ozhidanii'),
          description: t('misc.qpc_pered_vami_peoplebefore_0_ch', { peopleBefore: peopleBefore || 0 })
        };
      case 'called':
        return {
          color: 'var(--mac-success)',
          bgColor: 'rgba(52, 199, 89, 0.1)',
          text: t('misc.qpc_vas_vyzyvayut'),
          description: t('misc.qpc_prohodite_v_kabinet_cabinet', { cabinet: cabinet || '?' })
        };
      case 'in_service':
      case 'in_cabinet':
        return {
          color: 'var(--mac-warning)',
          bgColor: 'rgba(255, 149, 0, 0.1)',
          text: t('misc.qpc_na_priyome'),
          description: t('misc.qpc_idyot_priyom')
        };
      default:
        return {
          color: 'var(--mac-text-secondary)',
          bgColor: 'var(--mac-bg-secondary)',
          text: t('misc.qpc_status_neizvesten'),
          description: ''
        };
    }
  };

  const config = getStatusConfig(status);

  return (
    <Card className="p-4" style={{ borderLeft: `4px solid ${config.color}` }}>
            <div className="flex justify-between items-start mb-2">
                <div>
                    <h3 className="text-lg font-bold" style={{ color: config.color }}>
                        Талон №{number}
                    </h3>
                    <p className="text-sm font-medium text-gray-700">
                        {specialty} • {doctorName || t('misc.qpc_vrach')}
                    </p>
                </div>
                <Badge style={{ backgroundColor: config.bgColor, color: config.color }}>
                    {config.text}
                </Badge>
            </div>

            <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2">
                    <User size={16} className="text-gray-400" />
                    <span className="text-sm text-gray-600">
                        {config.description}
                    </span>
                </div>
                {status === 'waiting' && estimatedWaitTime > 0 &&
        <div className="flex items-center gap-2">
                        <Clock size={16} className="text-gray-400" />
                        <span className="text-sm text-gray-600">
                            ~{estimatedWaitTime} мин
                        </span>
                    </div>
        }
            </div>

            {status === 'called' &&
      <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-100 animate-pulse">
                    <p className="text-center text-green-700 font-bold mb-2">
                        Пожалуйста, пройдите в кабинет №{cabinet}
                    </p>
                    <p className="text-center text-xs text-green-600">
                        Вас ожидает врач
                    </p>
                </div>
      }
        </Card>);

};


QueuePositionCard.propTypes = {
  ...(QueuePositionCard.propTypes || {}),
  cabinet: PropTypes.any,
  doctorName: PropTypes.any,
  estimatedWaitTime: PropTypes.any,
  number: PropTypes.any,
  peopleBefore: PropTypes.any,
  queueEntry: PropTypes.any,
  specialty: PropTypes.any,
  status: PropTypes.any,
};

export default QueuePositionCard;
