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
  Button,
  Input,
  Alert,
  Badge,
  Grid,
  List,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  Option,
  Checkbox,
  Textarea,
} from '../ui/macos';
import {
  Hospital,
  Plus,
  Edit,
  Trash2,
  Copy,
  ChevronDown,
  Clock,
  DollarSign,
  Tag,
  CheckCircle,
  AlertTriangle,
  Search,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const ProcedureTemplates = ({ visitId, onSelectProcedure }) => {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState('all');
  
  // Форма для создания/редактирования шаблона
  const [templateForm, setTemplateForm] = useState({
    name: '',
    category: 'injection',
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
    { id: 'all', name: 'Все процедуры', icon: <Hospital /> },
    { id: 'injection', name: 'Инъекционные', icon: <Sparkles /> },
    { id: 'hardware', name: 'Аппаратные', icon: <Sparkles /> },
    { id: 'peeling', name: 'Пилинги', icon: <Sparkles /> },
    { id: 'care', name: 'Уходовые', icon: <Sparkles /> },
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
      logger.error('Ошибка загрузки шаблонов:', error);
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
      category: 'injection',
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
      logger.error('Ошибка сохранения шаблона:', error);
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
      case 'injection': return <Sparkles />;
      case 'hardware': return <Sparkles />;
      case 'peeling': return <Sparkles />;
      case 'care': return <Sparkles />;
      default: return <Hospital />;
    }
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">
              <Hospital style={{ marginRight: 8, verticalAlign: 'middle' }} />
              Шаблоны процедур
            </Typography>
            
            <Button
              variant="primary"
              onClick={handleCreateNew}
            >
              <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
              Создать шаблон
            </Button>
          </div>

          {/* Категории */}
          <div style={{ marginBottom: 16 }}>
            {categories.map((category) => (
              <Badge
                key={category.id}
                variant={expandedCategory === category.id ? 'primary' : 'info'}
                style={{ marginRight: 8, marginBottom: 8, cursor: 'pointer' }}
                onClick={() => setExpandedCategory(category.id)}
              >
                {category.icon}
                {category.name}
              </Badge>
            ))}
          </div>

          {/* Список шаблонов */}
          <div>
            {filteredTemplates.map((template, index) => (
              <div key={template.id} style={{ marginBottom: 16 }}>
                <div style={{
                  padding: 16,
                  border: '1px solid var(--mac-border)',
                  borderRadius: 8,
                  backgroundColor: 'var(--mac-bg-primary)',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onClick={() => handleSelectTemplate(template)}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                    <div style={{ marginTop: 4 }}>
                      {getCategoryIcon(template.category)}
                    </div>
                    
                    <div style={{ flex: 1 }}>
                      <Typography variant="h6" style={{ marginBottom: 4 }}>
                        {template.name}
                      </Typography>
                      <Typography variant="caption" color="textSecondary" style={{ display: 'block', marginBottom: 8 }}>
                        {template.description}
                      </Typography>
                      
                      <div style={{ display: 'flex', gap: 8 }}>
                        <Badge variant="info">
                          <Clock style={{ width: 12, height: 12, marginRight: 4 }} />
                          {template.duration} мин
                        </Badge>
                        <Badge variant="success">
                          <DollarSign style={{ width: 12, height: 12, marginRight: 4 }} />
                          {(template.price / 1000).toFixed(0)}k сум
                        </Badge>
                      </div>
                    </div>
                    
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEdit(template);
                      }}
                      style={{
                        padding: '8px',
                        border: '1px solid var(--mac-border)',
                        borderRadius: 4,
                        background: 'transparent',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <Edit style={{ width: 16, height: 16 }} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredTemplates.length === 0 && (
            <Typography variant="body2" color="textSecondary" style={{ textAlign: 'center', padding: '32px 0' }}>
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
                <List 
                  items={selectedTemplate.materials.map(material => ({
                    label: `${material.name} - ${material.quantity} ${material.unit}`,
                    icon: CheckCircle
                  }))}
                  size="sm"
                />
              </Grid>
              
              {/* Этапы процедуры */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>
                  Этапы процедуры:
                </Typography>
                <List 
                  items={selectedTemplate.steps.map((step, i) => `${i + 1}. ${step}`)}
                  size="sm"
                />
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
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Название процедуры</div>
              <Input
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
              />
            </Grid>
            
            <Grid item xs={12} md={4}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Категория</div>
              <Select
                value={templateForm.category}
                onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}
              >
                <Option value="injection">Инъекционные</Option>
                <Option value="hardware">Аппаратные</Option>
                <Option value="peeling">Пилинги</Option>
                <Option value="care">Уходовые</Option>
              </Select>
            </Grid>
            
            <Grid item xs={12}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Описание</div>
              <Textarea
                value={templateForm.description}
                onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                rows={3}
              />
            </Grid>
            
            <Grid item xs={6}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Длительность (мин)</div>
              <Input
                type="number"
                value={templateForm.duration}
                onChange={(e) => setTemplateForm({ ...templateForm, duration: parseInt(e.target.value || '0', 10) })}
              />
            </Grid>
            
            <Grid item xs={6}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Стоимость (сум)</div>
              <Input
                type="number"
                value={templateForm.price}
                onChange={(e) => setTemplateForm({ ...templateForm, price: e.target.value })}
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
                    <Input
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
                    <Input
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
                    <Input
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
              <Button size="small" onClick={addMaterial}>
                <Plus style={{ width: 14, height: 14, marginRight: 6 }} /> Добавить материал
              </Button>
            </Grid>
            
            {/* Этапы */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Этапы процедуры
              </Typography>
              {templateForm.steps.map((step, index) => (
                <Input
                  key={index}
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
              <Button size="small" onClick={addStep}>
                <Plus style={{ width: 14, height: 14, marginRight: 6 }} /> Добавить шаг
              </Button>
            </Grid>
            
            {/* Постуход */}
            <Grid item xs={12}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>Рекомендации после процедуры</div>
              <Textarea
                rows={3}
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

