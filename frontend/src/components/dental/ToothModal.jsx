/**
 * Tooth Modal Component
 * Модальное окно для работы с зубом
 * Согласно MASTER_TODO_LIST строка 285
 */
import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Select,
  Textarea,
} from '../ui/macos';
import {
  Activity,
  CheckCircle,
  History,
  Hospital,
  Plus,
  Trash2,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import PropTypes from 'prop-types';

const iconSize = 15;

function clonePlainObject(value) {
  if (!value || typeof value !== 'object') {
    return {};
  }

  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }

  return JSON.parse(JSON.stringify(value));
}

async function loadExistingEmrDraft(visitId) {
  const response = await api.get(`/v2/emr/${visitId}`, {
    silent: true,
    validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
  });

  return response.status === 404 ? null : response.data;
}

function buildToothEmrPayload(existingEmr, toothNumber, toothData) {
  const data = clonePlainObject(existingEmr?.data);
  const specialtyData = clonePlainObject(data.specialty_data);
  const toothStatus = clonePlainObject(specialtyData.tooth_status);

  toothStatus[toothNumber] = clonePlainObject(toothData);

  return {
    data: {
      ...data,
      specialty: data.specialty || 'dentistry',
      specialty_data: {
        ...specialtyData,
        tooth_status: toothStatus,
      },
      tooth_status: toothStatus,
    },
    row_version: existingEmr?.row_version ?? 0,
    is_draft: true,
  };
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 'var(--mac-spacing-3)',
  },
  title: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 600,
  },
  content: {
    display: 'grid',
    gap: '20px',
    maxHeight: '72vh',
    overflow: 'auto',
  },
  section: {
    display: 'grid',
    gap: '10px',
  },
  sectionTitle: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-lg)',
    fontWeight: 600,
  },
  buttonGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 'var(--mac-spacing-2)',
  },
  twoColumnGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '14px',
  },
  list: {
    display: 'grid',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    padding: 0,
    listStyle: 'none',
  },
  listItem: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) auto',
    gap: '10px',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid var(--mac-border)',
  },
  listItemStatic: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr)',
    gap: '10px',
    alignItems: 'start',
    padding: '8px 0',
    borderBottom: '1px solid var(--mac-border)',
  },
  listIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    color: 'var(--mac-accent-blue)',
    background: 'rgba(0, 122, 255, 0.08)',
  },
  itemTitle: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 600,
  },
  itemMeta: {
    margin: '3px 0 0',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)',
  },
  iconButton: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    color: 'var(--mac-danger, #ff3b30)',
    background: 'var(--mac-card-bg)',
    cursor: 'pointer',
  },
  checkboxRow: {
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr)',
    gap: '10px',
    alignItems: 'center',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-sm)',
  },
  divider: {
    height: '1px',
    background: 'var(--mac-border)',
  },
  totalTitle: {
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 600,
  },
  totalCaption: {
    display: 'block',
    marginTop: '6px',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)',
  },
};

const COPY = {
  toothPrefix: 'Зуб №',
  quadrantSuffix: 'квадрант',
  proceduresTitle: 'Процедуры',
  materialLabel: 'Материал',
  noMaterial: 'Без материала',
  nextVisitLabel: 'Следующий визит',
  notesLabel: 'Примечания',
  notesPlaceholder: 'Особенности лечения, рекомендации...',
  followUpLabel: 'Требуется контрольный осмотр',
  historyTitle: 'История лечения',
  totalCostLabel: 'Общая стоимость',
  includesLabel: 'Включает',
  materialPrefix: 'материал',
  currencySuffix: 'сум',
  cancelAction: 'Отмена',
  saveAction: 'Сохранить',
  deleteAction: 'Удалить',
};
// Процедуры для зуба
const TOOTH_PROCEDURES = {
  EXAMINATION: { id: 'examination', name: 'Осмотр', price: 20000 },
  CLEANING: { id: 'cleaning', name: 'Чистка', price: 50000 },
  FILLING: { id: 'filling', name: 'Пломба', price: 150000 },
  ROOT_CANAL: { id: 'root_canal', name: 'Лечение каналов', price: 300000 },
  CROWN: { id: 'crown', name: 'Коронка', price: 500000 },
  EXTRACTION: { id: 'extraction', name: 'Удаление', price: 100000 },
  IMPLANT: { id: 'implant', name: 'Имплантация', price: 1500000 },
  BRIDGE: { id: 'bridge', name: 'Мостовидный протез', price: 800000 },
  VENEER: { id: 'veneer', name: 'Винир', price: 600000 },
};

// Материалы
const MATERIALS = {
  COMPOSITE: { id: 'composite', name: 'Композит', price: 50000 },
  CERAMIC: { id: 'ceramic', name: 'Керамика', price: 200000 },
  METAL_CERAMIC: { id: 'metal_ceramic', name: 'Металлокерамика', price: 150000 },
  ZIRCONIA: { id: 'zirconia', name: 'Цирконий', price: 300000 },
  GOLD: { id: 'gold', name: 'Золото', price: 500000 },
};

const ToothModal = ({
  open,
  onClose,
  toothNumber,
  toothData = {},
  onSave,
  visitId
}) => {
  const [formData, setFormData] = useState({
    status: '',
    procedures: [],
    material: '',
    notes: '',
    price: 0,
    nextVisitDate: '',
    requiresFollowUp: false,
  });
  
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && toothData) {
      setFormData({
        status: toothData.status || '',
        procedures: toothData.procedures || [],
        material: toothData.material || '',
        notes: toothData.notes || '',
        price: toothData.price || 0,
        nextVisitDate: toothData.nextVisitDate || '',
        requiresFollowUp: toothData.requiresFollowUp || false,
      });

      setHistory([]);
    }
  }, [open, toothData]);

  // Добавление процедуры
  const addProcedure = (procedureId) => {
    const procedure = TOOTH_PROCEDURES[procedureId];
    if (!procedure) return;
    
    const newProcedure = {
      ...procedure,
      id: `${procedure.id}_${Date.now()}`,
      date: new Date().toISOString(),
    };
    
    setFormData(prev => ({
      ...prev,
      procedures: [...prev.procedures, newProcedure],
      price: prev.price + procedure.price,
    }));
  };

  // Удаление процедуры
  const removeProcedure = (procedureId) => {
    setFormData(prev => {
      const procedure = prev.procedures.find(p => p.id === procedureId);
      return {
        ...prev,
        procedures: prev.procedures.filter(p => p.id !== procedureId),
        price: prev.price - (procedure?.price || 0),
      };
    });
  };

  // Расчет общей стоимости
  const calculateTotalPrice = () => {
    let total = formData.procedures.reduce((sum, proc) => sum + (proc.price || 0), 0);
    
    if (formData.material) {
      const material = MATERIALS[formData.material];
      if (material) {
        total += material.price;
      }
    }
    
    return total;
  };

  // Сохранение данных
  const handleSave = async () => {
    setLoading(true);
    
    try {
      const dataToSave = {
        ...formData,
        toothNumber,
        price: calculateTotalPrice(),
        updatedAt: new Date().toISOString(),
      };
      
      if (visitId) {
        const existingEmr = await loadExistingEmrDraft(visitId);
        await api.post(
          `/v2/emr/${visitId}`,
          buildToothEmrPayload(existingEmr, toothNumber, dataToSave)
        );
      }
      
      onSave && onSave(toothNumber, dataToSave);
      onClose();
      
    } catch (error) {
      logger.error('Ошибка сохранения данных зуба:', error);
    } finally {
      setLoading(false);
    }
  };

  // Название зуба
  const getToothName = (number) => {
    const names = {
      11: 'Центральный резец',
      12: 'Боковой резец',
      13: 'Клык',
      14: 'Первый премоляр',
      15: 'Второй премоляр',
      16: 'Первый моляр',
      17: 'Второй моляр',
      18: 'Третий моляр (зуб мудрости)',
    };
    
    const baseNumber = parseInt(number.toString().slice(1));
    return names[`1${baseNumber}`] || `Зуб №${number}`;
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <div style={styles.header}>
          <h2 style={styles.title}>
            <Hospital size={18} aria-hidden="true" />
            {COPY.toothPrefix}{toothNumber} - {getToothName(toothNumber)}
          </h2>
          <Badge variant="primary" size="small">
            {`${Math.floor(toothNumber / 10)} ${COPY.quadrantSuffix}`}
          </Badge>
        </div>
      </DialogTitle>

      <DialogContent style={styles.content}>
        <section style={styles.section}>
          <h3 style={styles.sectionTitle}>{COPY.proceduresTitle}</h3>

          <div style={styles.buttonGrid}>
            {Object.entries(TOOTH_PROCEDURES).map(([key, procedure]) => (
              <Button
                key={key}
                type="button"
                size="small"
                variant="outline"
                onClick={() => addProcedure(key)}
              >
                <Plus size={iconSize} aria-hidden="true" />
                {procedure.name}
              </Button>
            ))}
          </div>

          {formData.procedures.length > 0 && (
            <ul style={styles.list}>
              {formData.procedures.map((procedure) => (
                <li key={procedure.id} style={styles.listItem}>
                  <span style={styles.listIcon} aria-hidden="true">
                    <Activity size={16} />
                  </span>
                  <div>
                    <p style={styles.itemTitle}>{procedure.name}</p>
                    <p style={styles.itemMeta}>{`${(procedure.price / 1000).toFixed(0)}k ${COPY.currencySuffix}`}</p>
                  </div>
                  <button
                    type="button"
                    aria-label={COPY.deleteAction}
                    title={COPY.deleteAction}
                    style={styles.iconButton}
                    onClick={() => removeProcedure(procedure.id)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div style={styles.twoColumnGrid}>
          <Select
            label={COPY.materialLabel}
            value={formData.material}
            onChange={(value) => setFormData({ ...formData, material: value })}
            options={[
              { value: '', label: COPY.noMaterial },
              ...Object.entries(MATERIALS).map(([key, material]) => ({
                value: key,
                label: `${material.name} - ${(material.price / 1000).toFixed(0)}k ${COPY.currencySuffix}`,
              })),
            ]}
          />

          <Input
            type="date"
            label={COPY.nextVisitLabel}
            value={formData.nextVisitDate}
            onChange={(e) => setFormData({ ...formData, nextVisitDate: e.target.value })}
            style={{ width: '100%', boxSizing: 'border-box' }}
          />
        </div>

        <Textarea
          label={COPY.notesLabel}
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          placeholder={COPY.notesPlaceholder}
          minRows={3}
          textareaStyle={{ width: '100%', boxSizing: 'border-box' }}
        />

        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            aria-label={COPY.followUpLabel}
            checked={formData.requiresFollowUp}
            onChange={(e) => setFormData({ ...formData, requiresFollowUp: e.target.checked })}
          />
          <span>{COPY.followUpLabel}</span>
        </label>

        {history.length > 0 && (
          <section style={styles.section}>
            <div style={styles.divider} />
            <h3 style={styles.sectionTitle}>
              <History size={16} aria-hidden="true" />
              {COPY.historyTitle}
            </h3>

            <ul style={styles.list}>
              {history.map((record, index) => (
                <li key={index} style={styles.listItemStatic}>
                  <span style={styles.listIcon} aria-hidden="true">
                    <CheckCircle size={15} />
                  </span>
                  <div>
                    <p style={styles.itemTitle}>{record.procedure}</p>
                    <p style={styles.itemMeta}>
                      {new Date(record.date).toLocaleDateString()} - {record.doctor}
                    </p>
                    {record.notes && <p style={styles.itemMeta}>{record.notes}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <Alert severity="info">
          <h3 style={styles.totalTitle}>
            {COPY.totalCostLabel}: {(calculateTotalPrice() / 1000).toFixed(0)}k {COPY.currencySuffix}
          </h3>
          {formData.procedures.length > 0 && (
            <span style={styles.totalCaption}>
              {COPY.includesLabel}: {formData.procedures.map(p => p.name).join(', ')}
              {formData.material && `, ${COPY.materialPrefix}: ${MATERIALS[formData.material]?.name}`}
            </span>
          )}
        </Alert>
      </DialogContent>

      <DialogActions>
        <Button type="button" onClick={onClose}>
          {COPY.cancelAction}
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleSave}
          disabled={loading || formData.procedures.length === 0}
          loading={loading}
        >
          {COPY.saveAction}
        </Button>
      </DialogActions>
    </Dialog>
  );
};


ToothModal.propTypes = {
  ...(ToothModal.propTypes || {}),
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  open: PropTypes.any,
  patientId: PropTypes.any,
  toothData: PropTypes.any,
  toothNumber: PropTypes.any,
  visitId: PropTypes.any,
};

export default ToothModal;

