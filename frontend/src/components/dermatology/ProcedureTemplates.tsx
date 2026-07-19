
/**
 * Procedure Templates Component
 * Шаблоны косметологических процедур
 * Согласно MASTER_TODO_LIST строка 267
 */
import { useState, useEffect, useCallback, useRef } from 'react';
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
  Select as SelectRaw,
  Option,
  Textarea,
} from '../ui/macos';
import {
  Hospital,
  Plus,
  Edit,



  Clock,
  DollarSign,

  CheckCircle,



  Sparkles } from
'lucide-react';


import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
const Select = SelectRaw as unknown as React.ComponentType<Record<string, unknown>>;
const ProcedureTemplates = ({ onSelectProcedure }: any) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
    aftercare: ''
  });

  // Категории процедур
  const categories = [
  { id: 'all', name: t('derma.derma_proc_category_all'), icon: <Hospital /> },
  { id: 'injection', name: t('derma.derma_proc_category_injection'), icon: <Sparkles /> },
  { id: 'hardware', name: t('derma.derma_proc_category_hardware'), icon: <Sparkles /> },
  { id: 'peeling', name: t('derma.derma_proc_category_peeling'), icon: <Sparkles /> },
  { id: 'care', name: t('derma.derma_proc_category_care'), icon: <Sparkles /> }];


  // Предустановленные шаблоны
  const defaultTemplates = [
  {
    id: 'botox-forehead',
    name: t('derma.derma_proc_tpl_botox_forehead_name'),
    category: 'injection',
    description: t('derma.derma_proc_tpl_botox_forehead_desc'),
    duration: 30,
    price: 150000,
    materials: [
    { name: t('derma.derma_proc_tpl_botox_forehead_mat_botulinum'), unit: t('derma.derma_proc_unit_50u'), quantity: 1 },
    { name: t('derma.derma_proc_tpl_botox_forehead_mat_syringe_1ml'), unit: t('derma.derma_proc_unit_pc'), quantity: 2 },
    { name: t('derma.derma_proc_tpl_botox_forehead_mat_needle_30g'), unit: t('derma.derma_proc_unit_pc'), quantity: 2 }],

    steps: [
    t('derma.derma_proc_tpl_botox_forehead_step_1'),
    t('derma.derma_proc_tpl_botox_forehead_step_2'),
    t('derma.derma_proc_tpl_botox_forehead_step_3'),
    t('derma.derma_proc_tpl_botox_forehead_step_4'),
    t('derma.derma_proc_tpl_botox_forehead_step_5')],

    contraindications: [
    t('derma.derma_proc_tpl_botox_forehead_contra_1'),
    t('derma.derma_proc_tpl_botox_forehead_contra_2'),
    t('derma.derma_proc_tpl_botox_forehead_contra_3'),
    t('derma.derma_proc_tpl_botox_forehead_contra_4')],

    aftercare: t('derma.derma_proc_tpl_botox_forehead_aftercare')
  },
  {
    id: 'mesotherapy-face',
    name: t('derma.derma_proc_tpl_meso_face_name'),
    category: 'injection',
    description: t('derma.derma_proc_tpl_meso_face_desc'),
    duration: 45,
    price: 200000,
    materials: [
    { name: t('derma.derma_proc_tpl_meso_face_mat_drug'), unit: t('derma.derma_proc_unit_2ml'), quantity: 1 },
    { name: t('derma.derma_proc_tpl_meso_face_mat_syringe_2ml'), unit: t('derma.derma_proc_unit_pc'), quantity: 1 },
    { name: t('derma.derma_proc_tpl_meso_face_mat_needle_32g'), unit: t('derma.derma_proc_unit_pc'), quantity: 5 },
    { name: t('derma.derma_proc_tpl_meso_face_mat_anesthetic'), unit: t('derma.derma_proc_unit_ml'), quantity: 5 }],

    steps: [
    t('derma.derma_proc_tpl_meso_face_step_1'),
    t('derma.derma_proc_tpl_meso_face_step_2'),
    t('derma.derma_proc_tpl_meso_face_step_3'),
    t('derma.derma_proc_tpl_meso_face_step_4'),
    t('derma.derma_proc_tpl_meso_face_step_5')],

    contraindications: [
    t('derma.derma_proc_tpl_meso_face_contra_1'),
    t('derma.derma_proc_tpl_meso_face_contra_2'),
    t('derma.derma_proc_tpl_meso_face_contra_3'),
    t('derma.derma_proc_tpl_meso_face_contra_4')],

    aftercare: t('derma.derma_proc_tpl_meso_face_aftercare')
  },
  {
    id: 'chemical-peel',
    name: t('derma.derma_proc_tpl_chem_peel_name'),
    category: 'peeling',
    description: t('derma.derma_proc_tpl_chem_peel_desc'),
    duration: 60,
    price: 120000,
    materials: [
    { name: t('derma.derma_proc_tpl_chem_peel_mat_glycolic'), unit: t('derma.derma_proc_unit_ml'), quantity: 10 },
    { name: t('derma.derma_proc_tpl_chem_peel_mat_neutralizer'), unit: t('derma.derma_proc_unit_ml'), quantity: 20 },
    { name: t('derma.derma_proc_tpl_chem_peel_mat_postmask'), unit: t('derma.derma_proc_unit_pc'), quantity: 1 }],

    steps: [
    t('derma.derma_proc_tpl_chem_peel_step_1'),
    t('derma.derma_proc_tpl_chem_peel_step_2'),
    t('derma.derma_proc_tpl_chem_peel_step_3'),
    t('derma.derma_proc_tpl_chem_peel_step_4'),
    t('derma.derma_proc_tpl_chem_peel_step_5'),
    t('derma.derma_proc_tpl_chem_peel_step_6')],

    contraindications: [
    t('derma.derma_proc_tpl_chem_peel_contra_1'),
    t('derma.derma_proc_tpl_chem_peel_contra_2'),
    t('derma.derma_proc_tpl_chem_peel_contra_3'),
    t('derma.derma_proc_tpl_chem_peel_contra_4')],

    aftercare: t('derma.derma_proc_tpl_chem_peel_aftercare')
  }];


  const defaultTemplatesRef = useRef(defaultTemplates);

  const loadTemplates = useCallback(async () => {
    try {
      // В реальном приложении загружаем с сервера
      // const response = await api.get('/procedure-templates') as any;
      // setTemplates(response.data);

      // Для демо используем предустановленные
      setTemplates(defaultTemplatesRef.current);
    } catch (error) {
      logger.error('Ошибка загрузки шаблонов:', error);
    }
  }, []);

  // Загрузка шаблонов
  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Фильтрация шаблонов по категории
  const filteredTemplates = expandedCategory === 'all' ?
  templates :
  templates.filter((t) => t.category === expandedCategory);

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
        aftercare: template.aftercare
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
      aftercare: ''
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
      }loadTemplates();setDialogOpen(false);} catch (error) {
      logger.error('Ошибка сохранения шаблона:', error);
    }
  };

  // Добавить материал
  const addMaterial = () => {
    setTemplateForm((prev) => ({
      ...prev,
      materials: [...prev.materials, { name: '', unit: '', quantity: 1 }]
    }));
  };

  // Добавить шаг
  const addStep = () => {
    setTemplateForm((prev) => ({
      ...prev,
      steps: [...prev.steps, '']
    }));
  };

  // Иконка категории
  const getCategoryIcon = (category) => {
    switch (category) {
      case 'injection':return <Sparkles />;
      case 'hardware':return <Sparkles />;
      case 'peeling':return <Sparkles />;
      case 'care':return <Sparkles />;
      default:return <Hospital />;
    }
  };

  return (
    <Box>
      <Card>
        <CardContent>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">
              <Hospital style={{ marginRight: 8, verticalAlign: 'middle' }} />
              {t('derma.derma_proc_title')}
            </Typography>
            
            <Button
              variant="primary"
              onClick={handleCreateNew}>
              
              <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
              {t('derma.derma_proc_create_button')}
            </Button>
          </div>

          {/* Категории */}
          <div style={{ marginBottom: 16 }}>
            {categories.map((category) =>
            <Badge
              key={category.id}
              variant={expandedCategory === category.id ? 'primary' : 'info'}
              style={{ marginRight: 8, marginBottom: 8, cursor: 'pointer' }}
              onClick={() => setExpandedCategory(category.id)}>
              
                {category.icon}
                {category.name}
              </Badge>
            )}
          </div>

          {/* Список шаблонов */}
          <div>
            {filteredTemplates.map((template) =>
            <div key={template.id} style={{ marginBottom: 16 }}>
                <div style={{
                padding: 16,
                border: '1px solid var(--mac-border)',
                borderRadius: 8,
                backgroundColor: 'var(--mac-bg-primary)',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              role="button"
              tabIndex={0}
              onClick={() => handleSelectTemplate(template)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  handleSelectTemplate(template);
                }
              }}>
                
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
                          {t('derma.derma_proc_duration_display', { duration: template.duration })}
                        </Badge>
                        <Badge variant="success">
                          <DollarSign style={{ width: 12, height: 12, marginRight: 4 }} />
                          {t('derma.derma_proc_price_display', { price: (template.price / 1000).toFixed(0) })}
                        </Badge>
                      </div>
                    </div>
                    
                    <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEdit(template);
                    }}
                    aria-label={t('derma.derma_proc_edit_aria', { name: template.name })}
                    style={{
                      padding: 'var(--mac-spacing-2)',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 4,
                      background: 'transparent',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                    
                      <Edit style={{ width: 16, height: 16 }} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {filteredTemplates.length === 0 &&
          <Typography variant="body2" color="textSecondary" style={{ textAlign: 'center', padding: '32px 0' }}>
              {t('derma.derma_proc_empty_category')}
            </Typography>
          }
        </CardContent>
      </Card>

      {/* Детали выбранного шаблона */}
      {selectedTemplate &&
      <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              {selectedTemplate.name}
            </Typography>
            
            <Grid container spacing={2}>
              {/* Материалы */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>
                  {t('derma.derma_proc_materials_title')}
                </Typography>
                <List
                items={selectedTemplate.materials.map((material) => ({
                  label: `${material.name} - ${material.quantity} ${material.unit}`,
                  icon: CheckCircle
                }))}
                size="small" />
              
              </Grid>
              
              {/* Этапы процедуры */}
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>
                  {t('derma.derma_proc_steps_title')}
                </Typography>
                <List
                items={selectedTemplate.steps.map((step, i) => `${i + 1}. ${step}`)}
                size="small" />
              
              </Grid>
              
              {/* Противопоказания */}
              {selectedTemplate.contraindications.length > 0 &&
            <Grid item xs={12}>
                  <Alert severity="warning">
                    <Typography variant="subtitle2" gutterBottom>
                      {t('derma.derma_proc_contraindications_title')}
                    </Typography>
                    {selectedTemplate.contraindications.map((item, i) =>
                <Typography key={i} variant="body2">
                        • {item}
                      </Typography>
                )}
                  </Alert>
                </Grid>
            }
              
              {/* Постуход */}
              {selectedTemplate.aftercare &&
            <Grid item xs={12}>
                  <Alert severity="info">
                    <Typography variant="subtitle2" gutterBottom>
                      {t('derma.derma_proc_aftercare_title')}
                    </Typography>
                    <Typography variant="body2">
                      {selectedTemplate.aftercare}
                    </Typography>
                  </Alert>
                </Grid>
            }
            </Grid>
          </CardContent>
        </Card>
      }

      {/* Диалог создания/редактирования */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="md"
        fullWidth>
        
        <DialogTitle>
          {editMode ? t('derma.derma_proc_dialog_edit_title') : t('derma.derma_proc_dialog_create_title')}
        </DialogTitle>
        
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} md={8}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('derma.derma_proc_field_name')}</div>
              <Input
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })} />
              
            </Grid>
            
            <Grid item xs={12} md={4}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('derma.derma_proc_field_category')}</div>
              <Select
                value={templateForm.category}
                onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}>
                
                <Option value="injection">{t('derma.derma_proc_category_injection')}</Option>
                <Option value="hardware">{t('derma.derma_proc_category_hardware')}</Option>
                <Option value="peeling">{t('derma.derma_proc_category_peeling')}</Option>
                <Option value="care">{t('derma.derma_proc_category_care')}</Option>
              </Select>
            </Grid>
            
            <Grid item xs={12}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('common.description')}</div>
              <Textarea
                value={templateForm.description}
                onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                rows={3} />
              
            </Grid>
            
            <Grid item xs={6}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('derma.derma_proc_field_duration')}</div>
              <Input
                type="number"
                value={templateForm.duration}
                onChange={(e) => setTemplateForm({ ...templateForm, duration: parseInt(e.target.value || '0', 10) })} />
              
            </Grid>
            
            <Grid item xs={6}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('derma.derma_proc_field_price')}</div>
              <Input
                type="number"
                value={templateForm.price}
                onChange={(e) => setTemplateForm({ ...templateForm, price: e.target.value })} />
              
            </Grid>
            
            {/* Материалы */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                {t('derma.derma_proc_field_materials')}
              </Typography>
              {templateForm.materials.map((material, index) =>
              <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                  <Grid item xs={6}>
                    <Input
                    placeholder={t('derma.derma_proc_ph_material_name')}
                    value={material.name}
                    onChange={(e) => {
                      const newMaterials = [...templateForm.materials];
                      newMaterials[index].name = e.target.value;
                      setTemplateForm({ ...templateForm, materials: newMaterials });
                    }} />
                  
                  </Grid>
                  <Grid item xs={3}>
                    <Input
                    placeholder={t('derma.derma_proc_ph_material_qty')}
                    value={material.quantity}
                    onChange={(e) => {
                      const newMaterials = [...templateForm.materials];
                      newMaterials[index].quantity = e.target.value;
                      setTemplateForm({ ...templateForm, materials: newMaterials });
                    }} />
                  
                  </Grid>
                  <Grid item xs={3}>
                    <Input
                    placeholder={t('derma.derma_proc_ph_material_unit')}
                    value={material.unit}
                    onChange={(e) => {
                      const newMaterials = [...templateForm.materials];
                      newMaterials[index].unit = e.target.value;
                      setTemplateForm({ ...templateForm, materials: newMaterials });
                    }} />
                  
                  </Grid>
                </Grid>
              )}
              <Button size="small" onClick={addMaterial}>
                <Plus style={{ width: 14, height: 14, marginRight: 6 }} /> {t('derma.derma_proc_add_material')}
              </Button>
            </Grid>
            
            {/* Этапы */}
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                {t('derma.derma_proc_steps_label')}
              </Typography>
              {templateForm.steps.map((step, index) =>
              <Input
                key={index}
                sx={{ mb: 1 }}
                placeholder={t('derma.derma_proc_ph_step', { n: index + 1 })}
                value={step}
                onChange={(e) => {
                  const newSteps = [...templateForm.steps];
                  newSteps[index] = e.target.value;
                  setTemplateForm({ ...templateForm, steps: newSteps });
                }} />

              )}
              <Button size="small" onClick={addStep}>
                <Plus style={{ width: 14, height: 14, marginRight: 6 }} /> {t('derma.derma_proc_add_step')}
              </Button>
            </Grid>
            
            {/* Постуход */}
            <Grid item xs={12}>
              <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 6 }}>{t('derma.derma_proc_field_aftercare')}</div>
              <Textarea
                rows={3}
                value={templateForm.aftercare}
                onChange={(e) => setTemplateForm({ ...templateForm, aftercare: e.target.value })} />
              
            </Grid>
          </Grid>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            {t('derma.derma_proc_cancel')}
          </Button>
          <Button variant="contained" onClick={handleSave}>
            {editMode ? t('derma.derma_proc_save') : t('derma.derma_proc_create')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>);

};


ProcedureTemplates.propTypes = {
  ...(ProcedureTemplates.propTypes || {}),
  onSelectProcedure: PropTypes.any,
};

export default ProcedureTemplates;