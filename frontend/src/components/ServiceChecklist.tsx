import PropTypes from 'prop-types';
import { Checkbox } from './ui/macos';
import { useTranslation } from '../i18n/useTranslation';
import React from 'react';

interface ChecklistService {
  id: string;
  name: string;
  price: number;
  group: string;
}

interface ServiceChecklistProps {
  value?: string[];
  onChange?: (value: string[]) => void;
  department?: string;
}

const ServiceChecklist = ({ value = [], onChange, department }: ServiceChecklistProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const services: Record<string, ChecklistService[]> = {
    cardio: [
      { id: 'cardio_consultation', name: t('misc.sc_konsultatsiya_kardiologa'), price: 60000, group: t('misc.sc_kardiologiya') },
      { id: 'cardio_ekg', name: t('misc.sc_ekg'), price: 25000, group: t('misc.sc_kardiologiya') },
      { id: 'cardio_echo', name: t('misc.sc_ehokg'), price: 120000, group: t('misc.sc_kardiologiya') },
      { id: 'cardio_holter', name: t('misc.sc_holter_monitoring'), price: 200000, group: t('misc.sc_kardiologiya') }
    ],
    derma: [
      { id: 'derma_consultation', name: t('misc.sc_konsultatsiya_dermatologa'), price: 50000, group: t('misc.sc_dermatologiya') },
      { id: 'derma_biopsy', name: t('misc.sc_biopsiya_kozhi'), price: 150000, group: t('misc.sc_dermatologiya') },
      { id: 'cosm_cleaning', name: t('misc.sc_chistka_litsa'), price: 80000, group: t('misc.sc_kosmetologiya') },
      { id: 'cosm_botox', name: t('misc.sc_inektsii_botoksa'), price: 300000, group: t('misc.sc_kosmetologiya') },
      { id: 'cosm_laser', name: t('misc.sc_lazernaya_terapiya'), price: 250000, group: t('misc.sc_kosmetologiya') }
    ],
    dental: [
      { id: 'dental_consultation', name: t('misc.sc_konsultatsiya_stomatologa'), price: 40000, group: t('misc.sc_stomatologiya') },
      { id: 'dental_treatment', name: t('misc.sc_lechenie_kariesa'), price: 100000, group: t('misc.sc_stomatologiya') },
      { id: 'dental_extraction', name: t('misc.sc_udalenie_zuba'), price: 80000, group: t('misc.sc_stomatologiya') },
      { id: 'dental_prosthetics', name: t('misc.sc_protezirovanie'), price: 500000, group: t('misc.sc_stomatologiya') }
    ],
    lab: [
      { id: 'lab_blood', name: t('misc.sc_obschiy_analiz_krovi'), price: 30000, group: t('misc.sc_laboratornye') },
      { id: 'lab_urine', name: t('misc.sc_obschiy_analiz_mochi'), price: 20000, group: t('misc.sc_laboratornye') },
      { id: 'lab_biochem', name: t('misc.sc_biohimiya_krovi'), price: 80000, group: t('misc.sc_laboratornye') },
      { id: 'lab_biopsy', name: t('misc.sc_biopsiya'), price: 150000, group: t('misc.sc_laboratornye') }
    ],
    procedures: [
      { id: 'proc_injection', name: t('misc.sc_inektsiya'), price: 15000, group: t('misc.sc_protsedury') },
      { id: 'proc_infusion', name: t('misc.sc_kapelnitsa'), price: 50000, group: t('misc.sc_protsedury') },
      { id: 'proc_physio', name: t('misc.sc_fizioterapiya'), price: 35000, group: t('misc.sc_protsedury') },
      { id: 'proc_massage', name: t('misc.sc_massazh'), price: 40000, group: t('misc.sc_protsedury') }
    ]
  };

  const depServices = (department && services[department.toLowerCase()]) || [];
  const groups = [...new Set(depServices.map(s => s.group))];
  const totalCost = depServices.filter(s => value.includes(s.id)).reduce((sum, s) => sum + s.price, 0);

  return (
    <div style={{ border: '1px solid #e5e5e5', borderRadius: 'var(--mac-radius-md)', padding: 'var(--mac-spacing-3)', marginBottom: 'var(--mac-spacing-3)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--mac-spacing-2)' }}>
        <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>{t('misc.sc_uslugi')}</span>
        <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-success)', fontWeight: 'var(--mac-font-weight-semibold)' }}>{totalCost.toLocaleString()} UZS</span>
      </div>
      {groups.map(group => (
        <div key={group} style={{ marginBottom: 'var(--mac-spacing-2)' }}>
          <div style={{ fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{group}</div>
          {depServices.filter(s => s.group === group).map(service => (
            <label key={service.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', marginBottom: 'var(--mac-spacing-1)' }}>
              <Checkbox aria-label={t('misc.sc_vybrat_uslugu_service_name', { name: service.name })} checked={value.includes(service.id)} onChange={(checked: boolean) => {
                  const newValue = checked
                    ? [...value, service.id]
                    : value.filter(id => id !== service.id);
                  onChange?.(newValue);
                }}
              />
              <span style={{ fontSize: 'var(--mac-font-size-xs)', flex: 1 }}>{service.name}</span>
              <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>{service.price.toLocaleString()} UZS</span>
            </label>
          ))}
        </div>
      ))}
    </div>
  );
};


ServiceChecklist.propTypes = {
  ...(ServiceChecklist.propTypes || {}),
  department: PropTypes.any,
  onChange: PropTypes.any,
  toLowerCase: PropTypes.any,
  value: PropTypes.any,
};

export default ServiceChecklist;
