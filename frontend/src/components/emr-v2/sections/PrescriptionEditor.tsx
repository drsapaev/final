
/**
 * PrescriptionEditor - Виджет назначений
 * 
 * Позволяет врачу:
 * 1. Добавлять препараты из списка (или драфт)
 * 2. Указывать дозировку, кратность, длительность
 * 3. Просматривать список назначений
 * 4. Удалять/Редактировать
 */

import { useState } from 'react';
import PropTypes from 'prop-types';
import { Plus, Trash2, Pill } from 'lucide-react';
import './PrescriptionEditor.css';
import { Input } from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';

// === Domain types ===
export interface PrescriptionItem {
  id?: string | number;
  name?: string;
  drug?: string;
  dose?: string;
  dosage?: string;
  frequency?: string;
  freq?: string;
  duration?: string;
  note?: string;
  [key: string]: unknown;
}

export interface PrescriptionEditorProps {
  /** Current list of prescriptions (controlled). */
  prescriptions?: PrescriptionItem[];
  /** Called whenever the list changes (add/edit/delete). */
  onChange?: (prescriptions: PrescriptionItem[]) => void;
  /** Whether the editor is editable (read-only when false). */
  isEditable?: boolean;
  /** Called when the field is first touched. */
  onFieldTouch?: (fieldName?: string) => void;
  [key: string]: unknown;
}

// Mock DB препаратов
const getMockDrugs = (t) => [
{ name: t('misc.pe_drug_amoxicillin'), defaultDose: t('misc.pe_drug_amoxicillin_dose'), defaultFreq: t('misc.pe_drug_amoxicillin_freq') },
{ name: t('misc.pe_drug_ibuprofen'), defaultDose: t('misc.pe_drug_ibuprofen_dose'), defaultFreq: t('misc.pe_drug_ibuprofen_freq') },
{ name: t('misc.pe_drug_bisoprolol'), defaultDose: t('misc.pe_drug_bisoprolol_dose'), defaultFreq: t('misc.pe_drug_bisoprolol_freq') },
{ name: t('misc.pe_drug_lisinopril'), defaultDose: t('misc.pe_drug_lisinopril_dose'), defaultFreq: t('misc.pe_drug_lisinopril_freq') },
{ name: t('misc.pe_drug_atorvastatin'), defaultDose: t('misc.pe_drug_atorvastatin_dose'), defaultFreq: t('misc.pe_drug_atorvastatin_freq') },
{ name: t('misc.pe_drug_omeprazole'), defaultDose: t('misc.pe_drug_omeprazole_dose'), defaultFreq: t('misc.pe_drug_omeprazole_freq') },
{ name: t('misc.pe_drug_paracetamol'), defaultDose: t('misc.pe_drug_paracetamol_dose'), defaultFreq: t('misc.pe_drug_paracetamol_freq') }];


const PrescriptionEditor = ({
  prescriptions = [],
  onChange,
  isEditable = true,
  onFieldTouch
}: PrescriptionEditorProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [isAdding, setIsAdding] = useState(false);
  const [newItem, setNewItem] = useState({
    name: '',
    dose: '',
    frequency: '',
    duration: '',
    note: ''
  });
  const [suggestions, setSuggestions] = useState([]);

  // Handlers
  const handleInputChange = (field, value) => {
    setNewItem((prev) => ({ ...prev, [field]: value }));

    // Search drugs
    if (field === 'name') {
      if (value.length > 1) {
        const matches = getMockDrugs(t).filter((d) =>
        d.name.toLowerCase().includes(value.toLowerCase())
        );
        setSuggestions(matches);
      } else {
        setSuggestions([]);
      }
    }
  };

  const handleSelectDrug = (drug) => {
    setNewItem((prev) => ({
      ...prev,
      name: drug.name,
      dose: drug.defaultDose,
      frequency: drug.defaultFreq
    }));
    setSuggestions([]);
  };

  const handleAdd = () => {
    if (!newItem.name) return;

    const updated = [...prescriptions, { ...newItem, id: Date.now() }];
    onChange?.(updated);
    onFieldTouch?.('prescriptions');

    // Reset
    setNewItem({ name: '', dose: '', frequency: '', duration: '', note: '' });
    setIsAdding(false);
  };

  const handleDelete = (id) => {
    const updated = prescriptions.filter((p) => p.id !== id);
    onChange?.(updated);
    onFieldTouch?.('prescriptions');
  };

  return (
    <div className={`prescription-editor ${!isEditable ? 'prescription-editor--readonly' : ''}`}>
            {/* LIST */}
            {prescriptions.length > 0 &&
      <div className="prescription-list">
                    {prescriptions.map((p, idx) =>
        <div key={p.id || idx} className="prescription-item">
                            <Pill size={16} className="prescription-item__icon" />
                            <div className="prescription-item__content">
                                <span className="prescription-item__name">{p.name}</span>
                                <span className="prescription-item__details">
                                    {p.dose && `${p.dose} `}
                                    {p.frequency && `• ${p.frequency} `}
                                    {p.duration && `• ${p.duration}`}
                                </span>
                            </div>
                            {isEditable &&
          <div className="prescription-item__actions">
                                    <button
              className="prescription-action-btn prescription-action-btn--delete"
              onClick={() => handleDelete(p.id)}
              title={t('misc.pe_udalit')}
              aria-label={t('misc.pe_udalit_naznachenie')}>
              
                                        <Trash2 size={14} />
                                    </button>
                                </div>
          }
                        </div>
        )}
                </div>
      }

            {/* ADD FORM */}
            {isEditable &&
      <>
                    {!isAdding ?
        <button
          className="prescription-toggle-btn"
          onClick={() => setIsAdding(true)}>
          
                            <Plus size={14} />
                            Добавить назначение
                        </button> :

        <div className="prescription-form">
                            <div className="prescription-form__row" style={{ position: 'relative' }}>
                                <div className="prescription-input-group">
                                    <label className="prescription-label">{t('misc.pe_preparat')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription medicine name"
                value={newItem.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder={t('misc.pe_nazvanie')}
                autoFocus />
              
                                    {suggestions.length > 0 &&
              <div className="prescription-suggestions">
                                            {suggestions.map((s, i) =>
                <div
                  key={i}
                  className="prescription-suggestion-item"
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectDrug(s)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleSelectDrug(s);
                    }
                  }}>
                  
                                                    {s.name}
                                                </div>
                )}
                                        </div>
              }
                                </div>
                            </div>

                            <div className="prescription-form__row">
                                <div className="prescription-input-group prescription-input-group--small">
                                    <label className="prescription-label">{t('misc.pe_doza')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription dose"
                value={newItem.dose}
                onChange={(e) => handleInputChange('dose', e.target.value)}
                placeholder={t('misc.pe_500_mg')} />
              
                                </div>
                                <div className="prescription-input-group">
                                    <label className="prescription-label">{t('misc.pe_kratnost')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription frequency"
                value={newItem.frequency}
                onChange={(e) => handleInputChange('frequency', e.target.value)}
                placeholder={t('misc.pe_3_r_d')} />
              
                                </div>
                                <div className="prescription-input-group prescription-input-group--small">
                                    <label className="prescription-label">{t('misc.pe_dlit')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription duration"
                value={newItem.duration}
                onChange={(e) => handleInputChange('duration', e.target.value)}
                placeholder={t('misc.pe_7_dney')} />
              
                                </div>
                            </div>

                            <button className="prescription-add-btn" onClick={handleAdd}>
                                Добавить
                            </button>
                            <button className="prescription-cancel-btn" onClick={() => setIsAdding(false)}>
                                Отмена
                            </button>
                        </div>
        }
                </>
      }
        </div>);

};

export default PrescriptionEditor;

PrescriptionEditor.propTypes = {
  prescriptions: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    name: PropTypes.string,
    dose: PropTypes.string,
    frequency: PropTypes.string,
    duration: PropTypes.string,
    note: PropTypes.string,
  })),
  onChange: PropTypes.func,
  isEditable: PropTypes.bool,
  onFieldTouch: PropTypes.func,
};
