/**
 * Treatment Planner Component  
 * План лечения с этапами
 * Согласно MASTER_TODO_LIST строка 286
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Input,
  Alert,
  Badge,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Option,
  Textarea,
} from '../ui/macos';
import {
  Calendar,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  Clock,
  DollarSign,
  Hospital,
  Printer,
  Share,
  FileText,
} from 'lucide-react';
import { api } from '../../api/client';

const TreatmentPlanner = ({ patientId, visitId, teethData = {}, onUpdate }) => {
  const [treatmentPlan, setTreatmentPlan] = useState({
    name: '',
    stages: [],
    totalCost: 0,
    totalDuration: 0,
  });
  
  const [stageDialog, setStageDialog] = useState(false);
  const [stageForm, setStageForm] = useState({
    name: '',
    description: '',
    teeth: [],
    date: '',
    duration: 1,
    cost: 0,
    priority: 'medium',
  });

  const PRIORITIES = {
    high: { label: 'Высокий', color: 'error' },
    medium: { label: 'Средний', color: 'warning' },
    low: { label: 'Низкий', color: 'info' },
  };

  const handleSaveStage = () => {
    const stage = {
      ...stageForm,
      id: `stage_${Date.now()}`,
      status: 'planned',
    };
    
    setTreatmentPlan(prev => ({
      ...prev,
      stages: [...prev.stages, stage],
      totalCost: prev.totalCost + stage.cost,
      totalDuration: prev.totalDuration + stage.duration,
    }));
    
    setStageDialog(false);
    setStageForm({
      name: '',
      description: '',
      teeth: [],
      date: '',
      duration: 1,
      cost: 0,
      priority: 'medium',
    });
  };

  const handleDeleteStage = (stageId) => {
    setTreatmentPlan(prev => {
      const stage = prev.stages.find(s => s.id === stageId);
      return {
        ...prev,
        stages: prev.stages.filter(s => s.id !== stageId),
        totalCost: prev.totalCost - (stage?.cost || 0),
        totalDuration: prev.totalDuration - (stage?.duration || 0),
      };
    });
  };

  const savePlan = async () => {
    try {
      await api.post(`/visits/${visitId}/treatment-plan`, treatmentPlan);
      onUpdate && onUpdate(treatmentPlan);
    } catch (error) {
      console.error('Ошибка сохранения плана:', error);
    }
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6">
              <Assignment sx={{ mr: 1, verticalAlign: 'middle' }} />
              План лечения
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" startIcon={<Add />} onClick={() => setStageDialog(true)}>
                Добавить этап
              </Button>
              <Button size="small" startIcon={<Print />} onClick={() => window.print()}>
                Печать
              </Button>
            </Box>
          </Box>

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Название плана"
                value={treatmentPlan.name}
                onChange={(e) => setTreatmentPlan({ ...treatmentPlan, name: e.target.value })}
              />
            </Grid>
          </Grid>

          <Paper sx={{ p: 2, mb: 3, bgcolor: 'background.default' }}>
            <Grid container spacing={2}>
              <Grid item xs={4}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4">{treatmentPlan.stages.length}</Typography>
                  <Typography variant="caption" color="text.secondary">Этапов</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4">{treatmentPlan.totalDuration}</Typography>
                  <Typography variant="caption" color="text.secondary">Визитов</Typography>
                </Box>
              </Grid>
              <Grid item xs={4}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4">{(treatmentPlan.totalCost / 1000).toFixed(0)}k</Typography>
                  <Typography variant="caption" color="text.secondary">Стоимость (сум)</Typography>
                </Box>
              </Grid>
            </Grid>
          </Paper>

          {treatmentPlan.stages.length > 0 ? (
            <List>
              {treatmentPlan.stages.map((stage, index) => (
                <React.Fragment key={stage.id}>
                  {index > 0 && <Divider />}
                  <ListItem>
                    <ListItemIcon>
                      <Hospital color="primary" />
                    </ListItemIcon>
                    <ListItemText
                      primary={stage.name}
                      secondary={
                        <Box>
                          <Typography variant="body2">{stage.description}</Typography>
                          <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                            <Chip size="small" icon={<CalendarToday />} label={stage.date || 'Не назначено'} />
                            <Chip size="small" icon={<Clock />} label={`${stage.duration} визит`} />
                            <Chip size="small" icon={<AttachMoney />} label={`${(stage.cost / 1000).toFixed(0)}k`} />
                            <Chip size="small" label={PRIORITIES[stage.priority].label} color={PRIORITIES[stage.priority].color} />
                          </Box>
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <IconButton onClick={() => handleDeleteStage(stage.id)}>
                        <Delete />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          ) : (
            <Alert severity="info">
              План лечения пуст. Добавьте этапы лечения.
            </Alert>
          )}

          {treatmentPlan.stages.length > 0 && (
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Button variant="contained" size="large" onClick={savePlan}>
                Сохранить план
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>

      <Dialog open={stageDialog} onClose={() => setStageDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Добавить этап лечения</DialogTitle>
        
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Название этапа"
                value={stageForm.name}
                onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Описание"
                value={stageForm.description}
                onChange={(e) => setStageForm({ ...stageForm, description: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="date"
                label="Дата"
                value={stageForm.date}
                onChange={(e) => setStageForm({ ...stageForm, date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Приоритет</InputLabel>
                <Select
                  value={stageForm.priority}
                  onChange={(e) => setStageForm({ ...stageForm, priority: e.target.value })}
                  label="Приоритет"
                >
                  {Object.entries(PRIORITIES).map(([key, priority]) => (
                    <MenuItem key={key} value={key}>
                      {priority.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Визитов"
                value={stageForm.duration}
                onChange={(e) => setStageForm({ ...stageForm, duration: parseInt(e.target.value) || 1 })}
              />
            </Grid>
            
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Стоимость (сум)"
                value={stageForm.cost}
                onChange={(e) => setStageForm({ ...stageForm, cost: parseInt(e.target.value) || 0 })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setStageDialog(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSaveStage} disabled={!stageForm.name}>
            Добавить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TreatmentPlanner;

