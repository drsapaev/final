/**
 * Tooth Modal Component
 * Модальное окно для работы с зубом
 * Согласно MASTER_TODO_LIST строка 285
 */
import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Input,
  Select,
  Option,
  Badge,
  Alert,
  Checkbox,
  Textarea,
} from '../ui/macos';
import {
  Hospital,
  Plus,
  Trash2,
  History,
  DollarSign,
  Calendar,
  FileText,
  AlertTriangle,
  CheckCircle,
  Wrench,
  Heart,
} from 'lucide-react';
import { api } from '../../api/client';

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
  patientId,
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
      
      // Загружаем историю зуба
      loadToothHistory();
    }
  }, [open, toothData, toothNumber]);

  // Загрузка истории процедур
  const loadToothHistory = async () => {
    if (!toothNumber || !patientId) return;
    
    try {
      const response = await api.get(`/patients/${patientId}/teeth/${toothNumber}/history`);
      setHistory(response.data || []);
    } catch (error) {
      console.error('Ошибка загрузки истории зуба:', error);
      setHistory([]);
    }
  };

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
      
      // Сохраняем на сервере
      if (visitId) {
        await api.post(`/visits/${visitId}/teeth/${toothNumber}`, dataToSave);
      }
      
      onSave && onSave(toothNumber, dataToSave);
      onClose();
      
    } catch (error) {
      console.error('Ошибка сохранения данных зуба:', error);
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
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">
            <Hospital sx={{ mr: 1, verticalAlign: 'middle' }} />
            Зуб №{toothNumber} - {getToothName(toothNumber)}
          </Typography>
          <Chip 
            label={`${Math.floor(toothNumber / 10)} квадрант`}
            size="small"
            color="primary"
          />
        </Box>
      </DialogTitle>
      
      <DialogContent dividers>
        <Grid container spacing={3}>
          {/* Процедуры */}
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Процедуры
            </Typography>
            
            <Box sx={{ mb: 2 }}>
              <Grid container spacing={1}>
                {Object.entries(TOOTH_PROCEDURES).map(([key, procedure]) => (
                  <Grid item key={key}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<Add />}
                      onClick={() => addProcedure(key)}
                    >
                      {procedure.name}
                    </Button>
                  </Grid>
                ))}
              </Grid>
            </Box>
            
            {formData.procedures.length > 0 && (
              <List dense>
                {formData.procedures.map((procedure) => (
                  <ListItem
                    key={procedure.id}
                    secondaryAction={
                      <IconButton edge="end" onClick={() => removeProcedure(procedure.id)}>
                        <Delete />
                      </IconButton>
                    }
                  >
                    <ListItemIcon>
                      <Healing color="primary" />
                    </ListItemIcon>
                    <ListItemText
                      primary={procedure.name}
                      secondary={`${(procedure.price / 1000).toFixed(0)}k сум`}
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Grid>

          {/* Материал */}
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Материал</InputLabel>
              <Select
                value={formData.material}
                onChange={(e) => setFormData({ ...formData, material: e.target.value })}
                label="Материал"
              >
                <MenuItem value="">Без материала</MenuItem>
                {Object.entries(MATERIALS).map(([key, material]) => (
                  <MenuItem key={key} value={key}>
                    {material.name} - {(material.price / 1000).toFixed(0)}k сум
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Следующий визит */}
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              type="date"
              label="Следующий визит"
              value={formData.nextVisitDate}
              onChange={(e) => setFormData({ ...formData, nextVisitDate: e.target.value })}
              InputLabelProps={{ shrink: true }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <CalendarToday />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>

          {/* Примечания */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Примечания"
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Особенности лечения, рекомендации..."
            />
          </Grid>

          {/* Требуется контроль */}
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.requiresFollowUp}
                  onChange={(e) => setFormData({ ...formData, requiresFollowUp: e.target.checked })}
                />
              }
              label="Требуется контрольный осмотр"
            />
          </Grid>

          {/* История */}
          {history.length > 0 && (
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle1" gutterBottom>
                <History sx={{ mr: 1, verticalAlign: 'middle' }} />
                История лечения
              </Typography>
              
              <List dense>
                {history.map((record, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <CheckCircle color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={record.procedure}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            {new Date(record.date).toLocaleDateString()} - {record.doctor}
                          </Typography>
                          {record.notes && (
                            <Typography variant="caption" color="text.secondary">
                              {record.notes}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </Grid>
          )}

          {/* Стоимость */}
          <Grid item xs={12}>
            <Alert severity="info">
              <Typography variant="h6">
                Общая стоимость: {(calculateTotalPrice() / 1000).toFixed(0)}k сум
              </Typography>
              {formData.procedures.length > 0 && (
                <Typography variant="caption">
                  Включает: {formData.procedures.map(p => p.name).join(', ')}
                  {formData.material && `, материал: ${MATERIALS[formData.material]?.name}`}
                </Typography>
              )}
            </Alert>
          </Grid>
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>
          Отмена
        </Button>
        <Button 
          variant="contained" 
          onClick={handleSave}
          disabled={loading || formData.procedures.length === 0}
        >
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ToothModal;

