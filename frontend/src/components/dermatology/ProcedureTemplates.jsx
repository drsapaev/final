/**
 * Procedure Templates Component
 * Шаблоны косметологических процедур
 * Согласно MASTER_TODO_LIST строка 267
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Grid,
  Divider,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  Checkbox,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  LocalHospital,
  Add,
  Edit,
  Delete,
  ContentCopy,
  ExpandMore,
  Timer,
  AttachMoney,
  Category,
  CheckCircle,
  Warning,
  Face,
  Spa,
  Healing,
  AutoFixHigh,
} from '@mui/icons-material';
import { api } from '../../api/client';

const ProcedureTemplates = ({ visitId, onSelectProcedure }) => {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState('all');
  
  // Форма для создания/редактирования шаблона
  const [templateForm, setTemplateForm] = useState({
    name: '',
    category: 'cosmetology',
    description: '',
    duration: 30,
    price: '',
    materials: [],
    steps: [],
    contraindications: [],
    aftercare: '',
  });

  // Категории процедур
  const categories = [
    { id: 'all', name: 'Все процедуры', icon: <LocalHospital /> },
    { id: 'injection', name: 'Инъекционные', icon: <Healing /> },
    { id: 'hardware', name: 'Аппаратные', icon: <AutoFixHigh /> },
    { id: 'peeling', name: 'Пилинги', icon: <Face /> },
    { id: 'care', name: 'Уходовые', icon: <Spa /> },
  ];

  // Предустановленные шаблоны
  const defaultTemplates = [
    {
      id: 'botox-forehead',
      name: 'Ботулотоксин - лоб',
      category: 'injection',
      description: 'Коррекция морщин лба',
      duration: 30,
      price: 150000,
      materials: [
        { name: 'Ботулотоксин', unit: '50 ед.', quantity: 1 },
        { name: 'Шприц 1мл', unit: 'шт.', quantity: 2 },
        { name: 'Игла 30G', unit: 'шт.', quantity: 2 },
      ],
      steps: [
        'Демакияж и обработка антисептиком',
        'Разметка точек инъекций',
        'Введение препарата в мышцы лба',
        'Легкий массаж',
        'Нанесение успокаивающего крема',
      ],
      contraindications: [
        'Беременность и лактация',
        'Миастения',
        'Прием антибиотиков',
        'Воспаления в зоне инъекций',
      ],
      aftercare: 'Не трогать зону инъекций 4 часа, не наклоняться, не заниматься спортом 24 часа',
    },
    {
      id: 'mesotherapy-face',
      name: 'Мезотерапия лица',
      category: 'injection',
      description: 'Биоревитализация кожи лица',
      duration: 45,
      price: 200000,
      materials: [
        { name: 'Препарат для мезотерапии', unit: '2мл', quantity: 1 },
        { name: 'Шприц 2мл', unit: 'шт.', quantity: 1 },
        { name: 'Игла 32G', unit: 'шт.', quantity: 5 },
        { name: 'Анестетик', unit: 'мл', quantity: 5 },
      ],
      steps: [
        'Очищение кожи',
        'Нанесение анестетика на 20 минут',
        'Обработка антисептиком',
        'Инъекции по схеме',
        'Нанесение маски',
      ],
      contraindications: [
        'Аллергия на компоненты',
        'Герпес в активной фазе',
        'Онкология',
        'Аутоиммунные заболевания',
      ],
      aftercare: 'Избегать солнца 3 дня, использовать SPF 50+, не посещать сауну 7 дней',
    },
    {
      id: 'chemical-peel',
      name: 'Химический пилинг',
      category: 'peeling',
      description: 'Поверхностный пилинг с гликолевой кислотой',
      duration: 60,
      price: 120000,
      materials: [
        { name: 'Гликолевая кислота 30%', unit: 'мл', quantity: 10 },
        { name: 'Нейтрализатор', unit: 'мл', quantity: 20 },
        { name: 'Постпилинговая маска', unit: 'шт.', quantity: 1 },
      ],
      steps: [
        'Демакияж и очищение',
        'Обезжиривание кожи',
        'Нанесение пилинга на 3-5 минут',
        'Нейтрализация',
        'Нанесение успокаивающей маски',
        'Финальный уход с SPF',
      ],
      contraindications: [
        'Активные воспаления',
        'Купероз',
        'Беременность',
        'Прием ретиноидов',
      ],
      aftercare: 'Использовать увлажняющие средства, SPF 50+ обязательно, не использовать скрабы 7 дней',
    },
  ];

  // Загрузка шаблонов
  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      // В реальном приложении загружаем с сервера
      // const response = await api.get('/procedure-templates');
      // setTemplates(response.data);
      
      // Для демо используем предустановленные
      setTemplates(defaultTemplates);
    } catch (error) {
      console.error('Ошибка загрузки шаблонов:', error);
    }
  };

  // Фильтрация шаблонов по категории
  const filteredTemplates = expandedCategory === 'all'
    ? templates
    : templates.filter(t => t.category === expandedCategory);

  // Выбор шаблона
  const handleSelectTemplate = (template) => {
    setSelectedTemplate(template);
    if (onSelectProcedure) {
      onSelectProcedure({
        name: template.name,
        price: template.price,
        duration: template.duration,
        materials: template.materials,
        steps: template.steps,
        aftercare: template.aftercare,
      });
    }
  };

  // Открыть диалог создания
  const handleCreateNew = () => {
    setEditMode(false);
    setTemplateForm({
      name: '',
      category: 'cosmetology',
      description: '',
      duration: 30,
      price: '',
      materials: [],
      steps: [],
      contraindications: [],
      aftercare: '',
    });
    setDialogOpen(true);
  };

  // Редактировать шаблон
  const handleEdit = (template) => {
    setEditMode(true);
    setTemplateForm(template);
    setDialogOpen(true);
  };

  // Сохранить шаблон
  const handleSave = async () => {
    try {
      if (editMode) {
        // Обновление существующего
        // await api.put(`/procedure-templates/${templateForm.id}`, templateForm);
      } else {
        // Создание нового
        // await api.post('/procedure-templates', templateForm);
      }
      
      loadTemplates();
      setDialogOpen(false);
    } catch (error) {
      console.error('Ошибка сохранения шаблона:', error);
    }
  };

  // Добавить материал
  const addMaterial = () => {
    setTemplateForm(prev => ({
      ...prev,
      materials: [...prev.materials, { name: '', unit: '', quantity: 1 }],
    }));
  };

  // Добавить шаг
  const addStep = () => {
    setTemplateForm(prev => ({
      ...prev,
      steps: [...prev.steps, ''],
    }));
  };

  // Иконка категории
  const getCategoryIcon = (category) => {
    switch (category) {
      case 'injection': return <Healing color="error" />;
      case 'hardware': return <AutoFixHigh color="primary" />;
      case 'peeling': return <Face color="warning" />;
      case 'care': return <Spa color="success" />;
      default: return <LocalHospital />;
    }
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              <LocalHospital sx={{ mr: 1, verticalAlign: 'middle' }} />
              Шаблоны процедур
            </Typography>
            
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleCreateNew}
            >
              Создать шаблон
            </Button>
          </Box>

          {/* Категории */}
          <Box sx={{ mb: 2 }}>
            {categories.map((category) => (
              <Chip
                key={category.id}
                label={category.name}
                icon={category.icon}
                onClick={() => setExpandedCategory(category.id)}
                color={expandedCategory === category.id ? 'primary' : 'default'}
                sx={{ mr: 1, mb: 1 }}
              />
            ))}
          </Box>

          {/* Список шаблонов */}
          <List>
            {filteredTemplates.map((template, index) => (
              <React.Fragment key={template.id}>
                {index > 0 && <Divider />}
                
                <ListItem disablePadding>
                  <ListItemButton onClick={() => handleSelectTemplate(template)}>
                    <ListItemIcon>
                      {getCategoryIcon(template.category)}
                    </ListItemIcon>
                    
                    <ListItemText
                      primary={template.name}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            {template.description}
                          </Typography>
                          <Box sx={{ mt: 0.5 }}>
                            <Chip
                              size="small"
                              icon={<Timer />}
                              label={`${template.duration} мин`}
                              sx={{ mr: 1 }}
                            />
                            <Chip
                              size="small"
                              icon={<AttachMoney />}
                              label={`${(template.price / 1000).toFixed(0)}k сум`}
                              color="success"
                            />
                          </Box>
                        </Box>
                      }
                    />
                    
                    <ListItemSecondaryAction>
                      <IconButton
                        edge="end"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEdit(template);
                        }}
                      >
                        <Edit />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItemButton>
                </ListItem>
              </React.Fragment>
            ))}
          </List>

          {filteredTemplates.length === 0 && (
            <Typography variant="body2" color="text.secondary" align="center" sx={{ py: 4 }}>
              Нет шаблонов в выбранной категории
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Детали выбранного шаблона */}
      {selectedTemplate && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {selectedTemplate.name}
            </Typography>
            
            <Grid container spacing={2}>
              {/* Материалы */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Необходимые материалы:
                </Typography>
                <List dense>
                  {selectedTemplate.materials.map((material, i) => (
                    <ListItem key={i}>
                      <ListItemIcon>
                        <CheckCircle color="success" fontSize="small" />
                      </ListItemIcon>
                      <ListItemText
                        primary={material.name}
                        secondary={`${material.quantity} ${material.unit}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Grid>
              
              {/* Этапы процедуры */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Этапы процедуры:
                </Typography>
                <List dense>
                  {selectedTemplate.steps.map((step, i) => (
                    <ListItem key={i}>
                      <ListItemText
                        primary={`${i + 1}. ${step}`}
                      />
                    </ListItem>
                  ))}
                </List>
              </Grid>
              
              {/* Противопоказания */}
              {selectedTemplate.contraindications.length > 0 && (
                <Grid item xs={12}>
                  <Alert severity="warning">
                    <Typography variant="subtitle2" gutterBottom>
                      Противопоказания:
                    </Typography>
                    {selectedTemplate.contraindications.map((item, i) => (
                      <Typography key={i} variant="body2">
                        • {item}
                      </Typography>
                    ))}
                  </Alert>
                </Grid>
              )}
              
              {/* Постуход */}
              {selectedTemplate.aftercare && (
                <Grid item xs={12}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      Рекомендации после процедуры:
                    </Typography>
                    <Typography variant="body2">
                      {selectedTemplate.aftercare}
                    </Typography>
                  </Alert>
                </Grid>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Диалог создания/редактирования */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editMode ? 'Редактировать шаблон' : 'Создать новый шаблон'}
        </DialogTitle>
        
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                label="Название процедуры"
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Категория</InputLabel>
                <Select
                  value={templateForm.category}
                  onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}
                  label="Категория"
                >
                  <MenuItem value="injection">Инъекционные</MenuItem>
                  <MenuItem value="hardware">Аппаратные</MenuItem>
                  <MenuItem value="peeling">Пилинги</MenuItem>
                  <MenuItem value="care">Уходовые</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Описание"
                value={templateForm.description}
                onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={6}>
              <TextField
                fullWidth
                type="number"
                label="Длительность"
                value={templateForm.duration}
                onChange={(e) => setTemplateForm({ ...templateForm, duration: parseInt(e.target.value) })}
                InputProps={{
                  endAdornment: <InputAdornment position="end">мин</InputAdornment>,
                }}
              />
            </Grid>
            
            <Grid item xs={6}>
              <TextField
                fullWidth
                type="number"
                label="Стоимость"
                value={templateForm.price}
                onChange={(e) => setTemplateForm({ ...templateForm, price: e.target.value })}
                InputProps={{
                  endAdornment: <InputAdornment position="end">сум</InputAdornment>,
                }}
              />
            </Grid>
            
            {/* Материалы */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Материалы
              </Typography>
              {templateForm.materials.map((material, index) => (
                <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                  <Grid item xs={6}>
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Название материала"
                      value={material.name}
                      onChange={(e) => {
                        const newMaterials = [...templateForm.materials];
                        newMaterials[index].name = e.target.value;
                        setTemplateForm({ ...templateForm, materials: newMaterials });
                      }}
                    />
                  </Grid>
                  <Grid item xs={3}>
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Кол-во"
                      value={material.quantity}
                      onChange={(e) => {
                        const newMaterials = [...templateForm.materials];
                        newMaterials[index].quantity = e.target.value;
                        setTemplateForm({ ...templateForm, materials: newMaterials });
                      }}
                    />
                  </Grid>
                  <Grid item xs={3}>
                    <TextField
                      fullWidth
                      size="small"
                      placeholder="Ед."
                      value={material.unit}
                      onChange={(e) => {
                        const newMaterials = [...templateForm.materials];
                        newMaterials[index].unit = e.target.value;
                        setTemplateForm({ ...templateForm, materials: newMaterials });
                      }}
                    />
                  </Grid>
                </Grid>
              ))}
              <Button size="small" startIcon={<Add />} onClick={addMaterial}>
                Добавить материал
              </Button>
            </Grid>
            
            {/* Этапы */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Этапы процедуры
              </Typography>
              {templateForm.steps.map((step, index) => (
                <TextField
                  key={index}
                  fullWidth
                  size="small"
                  sx={{ mb: 1 }}
                  placeholder={`Шаг ${index + 1}`}
                  value={step}
                  onChange={(e) => {
                    const newSteps = [...templateForm.steps];
                    newSteps[index] = e.target.value;
                    setTemplateForm({ ...templateForm, steps: newSteps });
                  }}
                />
              ))}
              <Button size="small" startIcon={<Add />} onClick={addStep}>
                Добавить шаг
              </Button>
            </Grid>
            
            {/* Постуход */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Рекомендации после процедуры"
                value={templateForm.aftercare}
                onChange={(e) => setTemplateForm({ ...templateForm, aftercare: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            Отмена
          </Button>
          <Button variant="contained" onClick={handleSave}>
            {editMode ? 'Сохранить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ProcedureTemplates;
