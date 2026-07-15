import { useTranslation } from '../../i18n/useTranslation';
/**
 * FamilyRelationsCard - component for patient family relationship display.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Input,
  Checkbox } from '../ui/macos';
import {
  Baby,
  Phone,
  Star,
  Trash2,
  UserPlus,
  UserRoundCog,
  Users
} from 'lucide-react';
import apiClient from '../../api/client';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const RELATION_TYPES = {
  parent: { label: 'Родитель', Icon: Users },
  child: { label: 'Ребёнок', Icon: Baby },
  guardian: { label: 'Опекун', Icon: UserRoundCog },
  spouse: { label: 'Супруг(а)', Icon: Users },
  sibling: { label: 'Брат/сестра', Icon: Users },
  other: { label: 'Другое', Icon: Users }
};

const styles = {
  card: {
    marginBottom: 'var(--mac-spacing-4)'
  },
  loading: {
    display: 'flex',
    justifyContent: 'center',
    padding: '24px 0'
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 'var(--mac-spacing-3)',
    marginBottom: 'var(--mac-spacing-4)'
  },
  title: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)'
  },
  sectionTitle: {
    margin: '0 0 8px',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-semibold)'
  },
  list: {
    display: 'grid',
    gap: 'var(--mac-spacing-2)',
    margin: 0,
    padding: 0,
    listStyle: 'none'
  },
  relationItem: {
    display: 'grid',
    gridTemplateColumns: '28px minmax(0, 1fr) auto',
    gap: '10px',
    alignItems: 'start',
    padding: 'var(--mac-spacing-3) 0',
    borderBottom: '1px solid var(--mac-border)'
  },
  relationIcon: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    color: 'var(--mac-accent-blue)',
    background: 'var(--mac-accent-bg)'
  },
  relationMain: {
    display: 'grid',
    gap: 'var(--mac-spacing-2)',
    minWidth: 0
  },
  relationName: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 'var(--mac-spacing-2)',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-base)',
    fontWeight: 'var(--mac-font-weight-semibold)'
  },
  relationMeta: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 'var(--mac-spacing-2)',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)'
  },
  phone: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-1)'
  },
  description: {
    color: 'var(--mac-text-tertiary)'
  },
  empty: {
    padding: '16px 0',
    margin: 0,
    textAlign: 'center',
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-sm)'
  },
  divider: {
    height: '1px',
    margin: '16px 0',
    background: 'var(--mac-border)'
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
    cursor: 'pointer'
  },
  fieldGroup: {
    display: 'grid',
    gap: 'var(--mac-spacing-2)',
    marginBottom: '14px'
  },
  label: {
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)',
    fontWeight: 'var(--mac-font-weight-semibold)'
  },
  input: {
    width: '100%',
    minHeight: '34px',
    padding: '7px 10px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    color: 'var(--mac-text-primary)',
    background: 'var(--mac-card-bg)',
    font: 'inherit'
  },
  textarea: {
    width: '100%',
    minHeight: '72px',
    padding: '8px 10px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    color: 'var(--mac-text-primary)',
    background: 'var(--mac-card-bg)',
    font: 'inherit',
    resize: 'vertical'
  },
  searchRow: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) auto',
    gap: 'var(--mac-spacing-2)',
    alignItems: 'end',
    marginBottom: '14px',
    marginTop: 'var(--mac-spacing-1)'
  },
  searchResults: {
    display: 'grid',
    gap: 'var(--mac-spacing-1)',
    maxHeight: '200px',
    overflow: 'auto',
    margin: '0 0 14px',
    padding: 'var(--mac-spacing-2)',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    listStyle: 'none'
  },
  searchResultButton: {
    width: '100%',
    display: 'grid',
    gap: 'var(--mac-spacing-1)',
    padding: 'var(--mac-spacing-2)',
    border: '1px solid transparent',
    borderRadius: 'var(--mac-radius-sm)',
    color: 'var(--mac-text-primary)',
    background: 'transparent',
    textAlign: 'left',
    cursor: 'pointer'
  },
  resultPhone: {
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)'
  },
  selectedPatient: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 'var(--mac-spacing-3)'
  },
  checkboxRow: {
    display: 'grid',
    gridTemplateColumns: 'auto minmax(0, 1fr)',
    gap: '10px',
    alignItems: 'start',
    marginTop: 'var(--mac-spacing-1)'
  },
  checkboxText: {
    display: 'grid',
    gap: 'var(--mac-spacing-1)',
    color: 'var(--mac-text-primary)',
    fontSize: 'var(--mac-font-size-sm)'
  },
  helpText: {
    color: 'var(--mac-text-secondary)',
    fontSize: 'var(--mac-font-size-xs)'
  },
  spinner: {
    width: '24px',
    height: '24px',
    border: '3px solid var(--mac-border)',
    borderTopColor: 'var(--mac-accent-blue)',
    borderRadius: '50%',
    animation: 'family-card-spin 0.8s linear infinite'
  }
};

export default function FamilyRelationsCard({
  patientId,
  patientName,
  canEdit = false,
  onFamilyChange
}) {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [family, setFamily] = useState([]);
  const [isRelativeOf, setIsRelativeOf] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadFamily = useCallback(async () => {
    if (!patientId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.get(`/patients/${patientId}/family`);
      setFamily(response.data.family || []);
      setIsRelativeOf(response.data.is_relative_of || []);
    } catch (err) {
      logger.error('Error loading family:', err);
      setError('Не удалось загрузить информацию о семье');
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    loadFamily();
  }, [loadFamily]);

  const handleDeleteRelation = async (relationId) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление семейной связи',
      message: 'Удалить эту семейную связь?',
      description: 'Это действие необратимо.',
      confirmLabel: t('misc.delete'),
      cancelLabel: t('misc.cancel'),
      intent: 'danger',
    });
    if (!ok) return;

    try {
      await apiClient.delete(`/patients/${patientId}/family/${relationId}`);
      await loadFamily();
      onFamilyChange?.();
    } catch (err) {
      logger.error('Error deleting relation:', err);
      setError('Не удалось удалить связь');
    }
  };

  const renderRelation = (rel, showPatient = false) => {
    const person = showPatient ? rel.patient : rel.related_patient;
    const typeInfo = RELATION_TYPES[rel.relation_type] || RELATION_TYPES.other;
    const TypeIcon = typeInfo.Icon;

    return (
      <li key={rel.relation_id} style={styles.relationItem}>
        <span style={styles.relationIcon} aria-hidden="true">
          <TypeIcon size={16} />
        </span>
        <div style={styles.relationMain}>
          <div style={styles.relationName}>
            <span>{person?.full_name || 'Неизвестно'}</span>
            {rel.is_primary_contact && (
              <Badge variant="primary" size="small">
                <Star size={12} aria-hidden="true" />
                Основной контакт
              </Badge>
            )}
          </div>
          <div style={styles.relationMeta}>
            <Badge variant="outline" size="small">{typeInfo.label}</Badge>
            {person?.phone && (
              <span style={styles.phone}>
                <Phone size={13} aria-hidden="true" />
                {person.phone}
              </span>
            )}
            {rel.description && <span style={styles.description}>— {rel.description}</span>}
          </div>
        </div>
        {canEdit && (
          <button
            type="button"
            aria-label="delete"
            style={styles.iconButton}
            onClick={() => handleDeleteRelation(rel.relation_id)}
          >
            <Trash2 size={15} aria-hidden="true" />
          </button>
        )}
      </li>
    );
  };

  if (loading) {
    return (
      <Card style={styles.card}>
        <CardContent style={styles.loading}>
          <span style={styles.spinner} aria-label="Loading family relationships" />
          <style>{'@keyframes family-card-spin { to { transform: rotate(360deg); } }'}</style>
        </CardContent>
      </Card>
    );
  }

  const hasFamily = family.length > 0 || isRelativeOf.length > 0;

  return (
    <Card style={styles.card}>
      <CardContent>
        <div style={styles.header}>
          <h2 style={styles.title}>
            <Users size={19} color="var(--mac-accent-blue)" aria-hidden="true" />
            Семья и родственники
          </h2>
          {canEdit && (
            <Button size="small" onClick={() => setDialogOpen(true)}>
              <UserPlus size={14} aria-hidden="true" />
              Добавить
            </Button>
          )}
        </div>

        {error && <Alert severity="error" style={{ marginBottom: '14px' }}>{error}</Alert>}

        {!hasFamily ? (
          <p style={styles.empty}>Нет связанных родственников</p>
        ) : (
          <>
            {family.length > 0 && (
              <section aria-label="Patient relatives">
                <h3 style={styles.sectionTitle}>Родственники пациента:</h3>
                <ul style={styles.list}>{family.map((rel) => renderRelation(rel, false))}</ul>
              </section>
            )}

            {isRelativeOf.length > 0 && (
              <section aria-label="Patient is relative of">
                {family.length > 0 && <div style={styles.divider} />}
                <h3 style={styles.sectionTitle}>Является родственником для:</h3>
                <ul style={styles.list}>{isRelativeOf.map((rel) => renderRelation(rel, true))}</ul>
              </section>
            )}
          </>
        )}
      </CardContent>

      <AddRelationDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        patientId={patientId}
        patientName={patientName}
        onSuccess={() => {
          setDialogOpen(false);
          loadFamily();
          onFamilyChange?.();
        }}
      />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </Card>
  );
}

FamilyRelationsCard.propTypes = {
  canEdit: PropTypes.bool,
  onFamilyChange: PropTypes.func,
  patientId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  patientName: PropTypes.string
};

function AddRelationDialog({ open, onClose, patientId, patientName, onSuccess }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [relationType, setRelationType] = useState('parent');
  const [description, setDescription] = useState('');
  const [isPrimaryContact, setIsPrimaryContact] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const response = await apiClient.get('/patients', {
        params: { search: searchQuery, limit: 10 }
      });
      setSearchResults(
        (response.data || []).filter((p) => p.id !== patientId)
      );
    } catch (err) {
      logger.error('Search error:', err);
    }
  };

  const handleSubmit = async () => {
    if (!selectedPatient) {
      setError('Выберите родственника');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.post(`/patients/${patientId}/family`, null, {
        params: {
          related_patient_id: selectedPatient.id,
          relation_type: relationType,
          description: description || undefined,
          is_primary_contact: isPrimaryContact
        }
      });

      setSearchQuery('');
      setSearchResults([]);
      setSelectedPatient(null);
      setRelationType('parent');
      setDescription('');
      setIsPrimaryContact(false);

      onSuccess();
    } catch (err) {
      logger.error('Error creating relation:', err);
      setError(err.response?.data?.detail || 'Не удалось создать связь');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Добавить родственника для {patientName}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" style={{ marginBottom: '14px' }}>{error}</Alert>}

        <div style={styles.searchRow}>
          <label style={styles.fieldGroup}>
            <span style={styles.label}>Поиск по ФИО или телефону</span>
            <Input
              aria-label="Search patient by name or phone"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
              style={styles.input}
            />
          </label>
          <Button type="button" variant="outline" onClick={handleSearch}>
            Найти
          </Button>
        </div>

        {searchResults.length > 0 && !selectedPatient && (
          <ul style={styles.searchResults}>
            {searchResults.map((patient) => (
              <li key={patient.id}>
                <button
                  type="button"
                  style={styles.searchResultButton}
                  onClick={() => setSelectedPatient(patient)}
                >
                  <span>{patient.last_name} {patient.first_name} {patient.middle_name || ''}</span>
                  <span style={styles.resultPhone}>{patient.phone || 'Без телефона'}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {selectedPatient && (
          <Alert severity="info" style={{ marginBottom: '14px' }}>
            <span style={styles.selectedPatient}>
              <span>
                Выбран: {selectedPatient.last_name} {selectedPatient.first_name}
                {selectedPatient.phone && ` (${selectedPatient.phone})`}
              </span>
              <Button type="button" variant="link" size="small" onClick={() => setSelectedPatient(null)}>
                Изменить
              </Button>
            </span>
          </Alert>
        )}

        <label style={styles.fieldGroup}>
          <span style={styles.label}>Тип связи</span>
          <select
            value={relationType}
            onChange={(event) => setRelationType(event.target.value)}
            style={styles.input}
          >
            {Object.entries(RELATION_TYPES).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </label>

        <label style={styles.fieldGroup}>
          <span style={styles.label}>Описание (необязательно)</span>
          <textarea
            aria-label="Family relation description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            style={styles.textarea}
            placeholder="Например: Бабушка по маминой линии"
          />
        </label>

        <label style={styles.checkboxRow}>
          <Checkbox aria-label="Mark as primary contact" checked={isPrimaryContact} onChange={(event) => setIsPrimaryContact(event.target.checked)}
          />
          <span style={styles.checkboxText}>
            <span>Основной контакт</span>
            <span style={styles.helpText}>Для пациентов без телефона (дети, пожилые)</span>
          </span>
        </label>
      </DialogContent>
      <DialogActions>
        <Button type="button" onClick={onClose}>Отмена</Button>
        <Button
          type="button"
          variant="primary"
          loading={loading}
          disabled={loading || !selectedPatient}
          onClick={handleSubmit}
        >
          Добавить
        </Button>
      </DialogActions>
    </Dialog>
  );
}

AddRelationDialog.propTypes = {
  onClose: PropTypes.func,
  onSuccess: PropTypes.func,
  open: PropTypes.bool,
  patientId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  patientName: PropTypes.string
};
