
/**
 * PrescriptionEditor - Виджет назначений
 * 
 * Позволяет врачу:
 * 1. Добавлять препараты из списка (или драфт)
 * 2. Указывать дозировку, кратность, длительность
 * 3. Просматривать список назначений
 * 4. Удалять/Редактировать
 */

import { useEffect, useRef, useState } from 'react';
import { Plus, Trash2, Pill } from 'lucide-react';
import './PrescriptionEditor.css';
import { Input } from '../../ui/macos';
import { useTranslation } from '@/i18n/useTranslation';

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
  /**
   * EMRPRES-FE-001 (audit 3886, round 19): canonical visit identity that
   * owns the uncommitted draft form. When the parent re-renders this
   * component for ANOTHER visit/patient (in-place prop change, e.g. the
   * dermatologist panel without a remount key), the half-typed medication
   * draft of the previous visit is discarded so «Добавить» can never commit
   * visit A's drug into visit B's structured list.
   */
  visitKey?: string | number | null;
  [key: string]: unknown;
}

// EMRPRES-FE-003 (audit 3886, round 19): Date.now()-derived ids collide when
// two Add events land in the same millisecond (or under a mocked/frozen
// clock) — the delete filter then removed BOTH rows and React saw duplicate
// keys. Client ids are now monotonic per module instance + carry a random
// suffix, so they stay unique even with a frozen clock and across remounts.
let rxClientSeq = 0;
function nextClientId(): string {
  rxClientSeq += 1;
  return `rx-${Date.now().toString(36)}-${rxClientSeq}-${Math.random().toString(36).slice(2, 8)}`;
}

// EMRPRES-FE-004 (audit 3886, round 19): the DTO explicitly permits alias
// fields (name|drug, dose|dosage, frequency|freq). Canonicalize at the
// display boundary; the original record is never mutated.
function displayName(p: PrescriptionItem): string {
  return String(p.name ?? p.drug ?? '');
}
function displayDose(p: PrescriptionItem): string {
  return String(p.dose ?? p.dosage ?? '');
}
function displayFrequency(p: PrescriptionItem): string {
  return String(p.frequency ?? p.freq ?? '');
}

type TFunc = (key: string, options?: Record<string, unknown>) => string;

// Mock DB препаратов
const getMockDrugs = (t: TFunc) => [
{ name: t('misc.pe_drug_amoxicillin'), defaultDose: t('misc.pe_drug_amoxicillin_dose'), defaultFreq: t('misc.pe_drug_amoxicillin_freq') },
{ name: t('misc.pe_drug_ibuprofen'), defaultDose: t('misc.pe_drug_ibuprofen_dose'), defaultFreq: t('misc.pe_drug_ibuprofen_freq') },
{ name: t('misc.pe_drug_bisoprolol'), defaultDose: t('misc.pe_drug_bisoprolol_dose'), defaultFreq: t('misc.pe_drug_bisoprolol_freq') },
{ name: t('misc.pe_drug_lisinopril'), defaultDose: t('misc.pe_drug_lisinopril_dose'), defaultFreq: t('misc.pe_drug_lisinopril_freq') },
{ name: t('misc.pe_drug_atorvastatin'), defaultDose: t('misc.pe_drug_atorvastatin_dose'), defaultFreq: t('misc.pe_drug_atorvastatin_freq') },
{ name: t('misc.pe_drug_omeprazole'), defaultDose: t('misc.pe_drug_omeprazole_dose'), defaultFreq: t('misc.pe_drug_omeprazole_freq') },
{ name: t('misc.pe_drug_paracetamol'), defaultDose: t('misc.pe_drug_paracetamol_dose'), defaultFreq: t('misc.pe_drug_paracetamol_freq') }];

interface DrugSuggestion {
  name: string;
  defaultDose: string;
  defaultFreq: string;
}


const PrescriptionEditor = ({
  prescriptions = [],
  onChange,
  isEditable = true,
  onFieldTouch,
  visitKey
}: PrescriptionEditorProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as TFunc;
  const [isAdding, setIsAdding] = useState(false);
  const [newItem, setNewItem] = useState({
    name: '',
    dose: '',
    frequency: '',
    duration: '',
    note: ''
  });
  const [suggestions, setSuggestions] = useState<DrugSuggestion[]>([]);

  // EMRPRES-FE-001 (audit 3886, round 19): the draft form belongs to the
  // visit it was started in. A visit-identity change (different patient/
  // visit reusing this mounted component) resets the uncommitted draft:
  // half-typed values of visit A can neither stay visible nor be committed
  // into visit B's list. A temporary read-only phase inside the SAME visit
  // (autosave locking the fields) intentionally keeps the draft — only a
  // context switch discards it.
  const lastVisitKeyRef = useRef<string | number | null | undefined>(visitKey);
  useEffect(() => {
    if (lastVisitKeyRef.current === visitKey) return;
    lastVisitKeyRef.current = visitKey;
    setNewItem({ name: '', dose: '', frequency: '', duration: '', note: '' });
    setIsAdding(false);
    setSuggestions([]);
  }, [visitKey]);

  // Handlers
  const handleInputChange = (field: string, value: string) => {
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

  const handleSelectDrug = (drug: DrugSuggestion) => {
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

    // EMRPRES-FE-003: collision-resistant client id (see nextClientId).
    const updated = [...prescriptions, { ...newItem, id: nextClientId() }];
    onChange?.(updated);
    onFieldTouch?.('prescriptions');

    // Reset
    setNewItem({ name: '', dose: '', frequency: '', duration: '', note: '' });
    setIsAdding(false);
  };

  // EMRPRES-FE-002 (audit 3886, round 19): deletion no longer requires an
  // id. The old handler was `p.id !== undefined && handleDelete(p.id)`, so
  // valid ID-less imported/legacy prescriptions rendered a working-looking
  // Trash button that silently did nothing. Rows are now removed by exact
  // object identity from the current list — duplicates by name (or rows
  // sharing a colliding id) can no longer delete each other.
  const handleDeleteItem = (item: PrescriptionItem) => {
    const updated = prescriptions.filter((p) => p !== item);
    onChange?.(updated);
    onFieldTouch?.('prescriptions');
  };

  return (
    <div className={`prescription-editor ${!isEditable ? 'prescription-editor--readonly' : ''}`}>
            {/* LIST */}
            {prescriptions.length > 0 &&
      <div className="prescription-list">
                    {prescriptions.map((p, idx) =>
        <div key={p.id ?? `row-${idx}`} className="prescription-item">
                            <Pill size={16} className="prescription-item__icon" />
                            <div className="prescription-item__content">
                                <span className="prescription-item__name">{displayName(p)}</span>
                                <span className="prescription-item__details">
                                    {displayDose(p) && `${displayDose(p)} `}
                                    {displayFrequency(p) && `• ${displayFrequency(p)} `}
                                    {p.duration && `• ${p.duration}`}
                                </span>
                            </div>
                            {isEditable &&
          <div className="prescription-item__actions">
                                    <button
              className="prescription-action-btn prescription-action-btn--delete"
              onClick={() => handleDeleteItem(p)}
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
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleInputChange('name', e.target.value)}
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
                  onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
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
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleInputChange('dose', e.target.value)}
                placeholder={t('misc.pe_500_mg')} />
              
                                </div>
                                <div className="prescription-input-group">
                                    <label className="prescription-label">{t('misc.pe_kratnost')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription frequency"
                value={newItem.frequency}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleInputChange('frequency', e.target.value)}
                placeholder={t('misc.pe_3_r_d')} />
              
                                </div>
                                <div className="prescription-input-group prescription-input-group--small">
                                    <label className="prescription-label">{t('misc.pe_dlit')}</label>
                                    <Input
                className="prescription-input"
                aria-label="Prescription duration"
                value={newItem.duration}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleInputChange('duration', e.target.value)}
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

