/**
 * FamilyRelationsCard - Компонент для отображения семейных связей пациента
 * 
 * Функции:
 * - Показывает родственников пациента
 * - Указывает основной контакт (для детей/пожилых без телефона)
 * - Позволяет добавлять/удалять связи (регистраторам и админам)
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
    Card,
    CardContent,
    Typography,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction,
    IconButton,
    Chip,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    FormControlLabel,
    Checkbox,
    CircularProgress,
    Alert,
    Divider,
    Box
} from '@mui/material';
import {
    PersonAdd,
    Delete,
    Phone,
    Star,
    StarBorder,
    FamilyRestroom,
    ChildCare,
    Elderly,
    People
} from '@mui/icons-material';
import apiClient from '../../api/client';

// Типы связей с иконками и названиями
const RELATION_TYPES = {
    parent: { label: 'Родитель', icon: <FamilyRestroom /> },
    child: { label: 'Ребёнок', icon: <ChildCare /> },
    guardian: { label: 'Опекун', icon: <Elderly /> },
    spouse: { label: 'Супруг(а)', icon: <People /> },
    sibling: { label: 'Брат/сестра', icon: <People /> },
    other: { label: 'Другое', icon: <People /> },
};

/**
 * Карточка семейных связей
 */
export default function FamilyRelationsCard({
    patientId,
    patientName,
    canEdit = false,  // Может ли пользователь редактировать связи
    onFamilyChange,   // Callback при изменении связей
}) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [family, setFamily] = useState([]);
    const [isRelativeOf, setIsRelativeOf] = useState([]);
    const [dialogOpen, setDialogOpen] = useState(false);

    // Загрузка данных о семье
    const loadFamily = useCallback(async () => {
        if (!patientId) return;

        setLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/patients/${patientId}/family`);
            setFamily(response.data.family || []);
            setIsRelativeOf(response.data.is_relative_of || []);
        } catch (err) {
            console.error('Error loading family:', err);
            setError('Не удалось загрузить информацию о семье');
        } finally {
            setLoading(false);
        }
    }, [patientId]);

    useEffect(() => {
        loadFamily();
    }, [loadFamily]);

    // Удаление связи
    const handleDeleteRelation = async (relationId) => {
        if (!window.confirm('Удалить эту семейную связь?')) return;

        try {
            await apiClient.delete(`/patients/${patientId}/family/${relationId}`);
            await loadFamily();
            onFamilyChange?.();
        } catch (err) {
            console.error('Error deleting relation:', err);
            setError('Не удалось удалить связь');
        }
    };

    // Render relation item
    const renderRelation = (rel, showPatient = false) => {
        const person = showPatient ? rel.patient : rel.related_patient;
        const typeInfo = RELATION_TYPES[rel.relation_type] || RELATION_TYPES.other;

        return (
            <ListItem key={rel.relation_id} divider>
                <ListItemIcon>
                    {typeInfo.icon}
                </ListItemIcon>
                <ListItemText
                    primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <span>{person?.full_name || 'Неизвестно'}</span>
                            {rel.is_primary_contact && (
                                <Chip
                                    icon={<Star fontSize="small" />}
                                    label="Основной контакт"
                                    size="small"
                                    color="primary"
                                />
                            )}
                        </Box>
                    }
                    secondary={
                        <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Chip label={typeInfo.label} size="small" variant="outlined" />
                            {person?.phone && (
                                <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Phone fontSize="small" color="action" />
                                    {person.phone}
                                </Box>
                            )}
                            {rel.description && (
                                <span style={{ color: '#666' }}>— {rel.description}</span>
                            )}
                        </Box>
                    }
                />
                {canEdit && (
                    <ListItemSecondaryAction>
                        <IconButton
                            edge="end"
                            aria-label="delete"
                            onClick={() => handleDeleteRelation(rel.relation_id)}
                            size="small"
                        >
                            <Delete fontSize="small" />
                        </IconButton>
                    </ListItemSecondaryAction>
                )}
            </ListItem>
        );
    };

    if (loading) {
        return (
            <Card sx={{ mb: 2 }}>
                <CardContent sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                    <CircularProgress size={24} />
                </CardContent>
            </Card>
        );
    }

    const hasFamily = family.length > 0 || isRelativeOf.length > 0;

    return (
        <Card sx={{ mb: 2 }}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6" component="div" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <FamilyRestroom color="primary" />
                        Семья и родственники
                    </Typography>
                    {canEdit && (
                        <Button
                            size="small"
                            startIcon={<PersonAdd />}
                            onClick={() => setDialogOpen(true)}
                        >
                            Добавить
                        </Button>
                    )}
                </Box>

                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
                )}

                {!hasFamily ? (
                    <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                        Нет связанных родственников
                    </Typography>
                ) : (
                    <>
                        {family.length > 0 && (
                            <>
                                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                                    Родственники пациента:
                                </Typography>
                                <List dense>
                                    {family.map(rel => renderRelation(rel, false))}
                                </List>
                            </>
                        )}

                        {isRelativeOf.length > 0 && (
                            <>
                                <Divider sx={{ my: 2 }} />
                                <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                                    Является родственником для:
                                </Typography>
                                <List dense>
                                    {isRelativeOf.map(rel => renderRelation(rel, true))}
                                </List>
                            </>
                        )}
                    </>
                )}
            </CardContent>

            {/* Dialog for adding new relation */}
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
        </Card>
    );
}


/**
 * Диалог добавления новой связи
 */
function AddRelationDialog({ open, onClose, patientId, patientName, onSuccess }) {
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [selectedPatient, setSelectedPatient] = useState(null);
    const [relationType, setRelationType] = useState('parent');
    const [description, setDescription] = useState('');
    const [isPrimaryContact, setIsPrimaryContact] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Поиск пациентов
    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        try {
            const response = await apiClient.get('/patients', {
                params: { search: searchQuery, limit: 10 }
            });
            // Исключаем текущего пациента из результатов
            setSearchResults(
                (response.data || []).filter(p => p.id !== patientId)
            );
        } catch (err) {
            console.error('Search error:', err);
        }
    };

    // Создание связи
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
                    is_primary_contact: isPrimaryContact,
                }
            });

            // Reset form
            setSearchQuery('');
            setSearchResults([]);
            setSelectedPatient(null);
            setRelationType('parent');
            setDescription('');
            setIsPrimaryContact(false);

            onSuccess();
        } catch (err) {
            console.error('Error creating relation:', err);
            setError(err.response?.data?.detail || 'Не удалось создать связь');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Добавить родственника для {patientName}</DialogTitle>
            <DialogContent>
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
                )}

                {/* Поиск пациента */}
                <Box sx={{ display: 'flex', gap: 1, mb: 2, mt: 1 }}>
                    <TextField
                        label="Поиск по ФИО или телефону"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                        fullWidth
                        size="small"
                    />
                    <Button variant="outlined" onClick={handleSearch}>
                        Найти
                    </Button>
                </Box>

                {/* Результаты поиска */}
                {searchResults.length > 0 && !selectedPatient && (
                    <List dense sx={{ mb: 2, maxHeight: 200, overflow: 'auto', border: '1px solid #ddd', borderRadius: 1 }}>
                        {searchResults.map(patient => (
                            <ListItem
                                key={patient.id}
                                button
                                onClick={() => setSelectedPatient(patient)}
                            >
                                <ListItemText
                                    primary={`${patient.last_name} ${patient.first_name} ${patient.middle_name || ''}`}
                                    secondary={patient.phone || 'Без телефона'}
                                />
                            </ListItem>
                        ))}
                    </List>
                )}

                {/* Выбранный пациент */}
                {selectedPatient && (
                    <Alert
                        severity="info"
                        sx={{ mb: 2 }}
                        action={
                            <Button color="inherit" size="small" onClick={() => setSelectedPatient(null)}>
                                Изменить
                            </Button>
                        }
                    >
                        Выбран: {selectedPatient.last_name} {selectedPatient.first_name}
                        {selectedPatient.phone && ` (${selectedPatient.phone})`}
                    </Alert>
                )}

                {/* Тип связи */}
                <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Тип связи</InputLabel>
                    <Select
                        value={relationType}
                        onChange={(e) => setRelationType(e.target.value)}
                        label="Тип связи"
                    >
                        {Object.entries(RELATION_TYPES).map(([key, { label }]) => (
                            <MenuItem key={key} value={key}>{label}</MenuItem>
                        ))}
                    </Select>
                </FormControl>

                {/* Описание */}
                <TextField
                    label="Описание (необязательно)"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                    placeholder="Например: Бабушка по маминой линии"
                />

                {/* Основной контакт */}
                <FormControlLabel
                    control={
                        <Checkbox
                            checked={isPrimaryContact}
                            onChange={(e) => setIsPrimaryContact(e.target.checked)}
                        />
                    }
                    label={
                        <Box>
                            <Typography variant="body2">Основной контакт</Typography>
                            <Typography variant="caption" color="text.secondary">
                                Для пациентов без телефона (дети, пожилые)
                            </Typography>
                        </Box>
                    }
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Отмена</Button>
                <Button
                    onClick={handleSubmit}
                    variant="contained"
                    disabled={loading || !selectedPatient}
                >
                    {loading ? <CircularProgress size={20} /> : 'Добавить'}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
