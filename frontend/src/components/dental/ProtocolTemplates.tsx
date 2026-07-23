import { useEffect, useState } from 'react';
import {
  FileText,
  Plus,
  Edit,
  Trash2,
  Copy,

  X,
  Search,


  Clock,

  Scissors,
  Pill,
  Syringe,
  Camera,


  Star } from

'lucide-react';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * Шаблоны протоколов для стоматологической ЭМК
 * Включает стандартные процедуры, материалы, анестезию
 */
const ProtocolTemplates = ({
  onSelectTemplate,
  onClose
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [templates, setTemplates] = useState([
  // Шаблоны процедур
  {
    id: 'caries_treatment',
    name: t('dental.dental_pt_name_caries_treatment'),
    category: 'procedure',
    description: t('dental.dental_pt_desc_caries_treatment'),
    icon: Scissors,
    color: 'blue',
    steps: [
    { type: 'procedure', name: t('dental.dental_pt_step_oral_exam'), duration: 5, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_anesthesia'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_caries_prep'), duration: 20, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_filling'), duration: 15, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_polishing'), duration: 10, required: true }],

    materials: [
    { name: t('dental.dental_pt_mat_composite'), quantity: t('dental.dental_pt_qty_1pc'), required: true },
    { name: t('dental.dental_pt_mat_adhesive'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_cotton'), quantity: t('dental.dental_pt_qty_10pc'), required: false }],

    anesthesia: [
    { drug: t('dental.dental_pt_drug_lidocaine2'), dose: t('dental.dental_pt_qty_1_8ml'), method: t('dental.dental_pt_method_infiltration'), required: true }],

    photos: [
    { type: 'before', description: t('dental.dental_pt_photo_before_treatment'), required: true },
    { type: 'after', description: t('dental.dental_pt_photo_after_treatment'), required: true }],

    prescriptions: [
    { medication: t('dental.dental_pt_rx_ibuprofen'), dosage: t('dental.dental_pt_rx_dosage_400'), instructions: t('dental.dental_pt_rx_instr_pain_3x'), required: false }],

    tags: [t('dental.dental_pt_tag_caries'), t('dental.dental_pt_tag_filling'), t('dental.dental_pt_tag_therapy')],
    estimatedDuration: 60,
    difficulty: 'medium',
    isDefault: true
  },

  {
    id: 'root_canal_treatment',
    name: t('dental.dental_pt_name_root_canal'),
    category: 'procedure',
    description: t('dental.dental_pt_desc_root_canal'),
    icon: Scissors,
    color: 'red',
    steps: [
    { type: 'procedure', name: t('dental.dental_pt_step_diagnostics'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_anesthesia'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_isolation'), duration: 5, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_access_prep'), duration: 15, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_instrumental'), duration: 30, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_medication'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_canal_filling'), duration: 20, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_crown_restore'), duration: 25, required: true }],

    materials: [
    { name: t('dental.dental_pt_mat_endo_files'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_gutta_percha'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_endo_cement'), quantity: t('dental.dental_pt_qty_1pc'), required: true },
    { name: t('dental.dental_pt_mat_antiseptic'), quantity: t('dental.dental_pt_qty_10ml'), required: true }],

    anesthesia: [
    { drug: t('dental.dental_pt_drug_lidocaine2'), dose: t('dental.dental_pt_qty_2ml'), method: t('dental.dental_pt_method_conduction'), required: true }],

    photos: [
    { type: 'before', description: t('dental.dental_pt_photo_before_treatment'), required: true },
    { type: 'during', description: t('dental.dental_pt_photo_during_treatment'), required: false },
    { type: 'after', description: t('dental.dental_pt_photo_after_treatment'), required: true }],

    prescriptions: [
    { medication: t('dental.dental_pt_rx_amoxicillin'), dosage: t('dental.dental_pt_rx_dosage_500'), instructions: t('dental.dental_pt_rx_instr_3x_7d'), required: true },
    { medication: t('dental.dental_pt_rx_ibuprofen'), dosage: t('dental.dental_pt_rx_dosage_400'), instructions: t('dental.dental_pt_rx_instr_pain'), required: false }],

    tags: [t('dental.dental_pt_tag_endo'), t('dental.dental_pt_tag_canals'), t('dental.dental_pt_tag_pulpitis')],
    estimatedDuration: 120,
    difficulty: 'high',
    isDefault: true
  },

  {
    id: 'tooth_extraction',
    name: t('dental.dental_pt_name_tooth_extraction'),
    category: 'surgery',
    description: t('dental.dental_pt_desc_tooth_extraction'),
    icon: Scissors,
    color: 'red',
    steps: [
    { type: 'procedure', name: t('dental.dental_pt_step_exam_diagnosis'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_anesthesia'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_gum_detachment'), duration: 5, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_extraction'), duration: 20, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_socket_curettage'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_suturing'), duration: 10, required: false },
    { type: 'procedure', name: t('dental.dental_pt_step_tampon'), duration: 5, required: true }],

    materials: [
    { name: t('dental.dental_pt_mat_forceps'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_elevators'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_suture'), quantity: t('dental.dental_pt_qty_1m'), required: false },
    { name: t('dental.dental_pt_mat_cotton'), quantity: t('dental.dental_pt_qty_20pc'), required: true }],

    anesthesia: [
    { drug: t('dental.dental_pt_drug_lidocaine2'), dose: t('dental.dental_pt_qty_2ml'), method: t('dental.dental_pt_method_conduction'), required: true }],

    photos: [
    { type: 'before', description: t('dental.dental_pt_photo_before_extraction'), required: true },
    { type: 'after', description: t('dental.dental_pt_photo_after_extraction'), required: true }],

    prescriptions: [
    { medication: t('dental.dental_pt_rx_amoxicillin'), dosage: t('dental.dental_pt_rx_dosage_500'), instructions: t('dental.dental_pt_rx_instr_3x_5d'), required: true },
    { medication: t('dental.dental_pt_rx_ibuprofen'), dosage: t('dental.dental_pt_rx_dosage_400'), instructions: t('dental.dental_pt_rx_instr_pain'), required: true }],

    tags: [t('dental.dental_pt_tag_extraction'), t('dental.dental_pt_tag_surgery'), t('dental.dental_pt_tag_tooth')],
    estimatedDuration: 60,
    difficulty: 'medium',
    isDefault: true
  },

  {
    id: 'professional_hygiene',
    name: t('dental.dental_pt_name_prof_hygiene'),
    category: 'hygiene',
    description: t('dental.dental_pt_desc_prof_hygiene'),
    icon: Scissors,
    color: 'green',
    steps: [
    { type: 'procedure', name: t('dental.dental_pt_step_oral_exam'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_tartar_removal'), duration: 30, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_teeth_polishing'), duration: 20, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_fluoridation'), duration: 10, required: false },
    { type: 'procedure', name: t('dental.dental_pt_step_hygiene_training'), duration: 15, required: true }],

    materials: [
    { name: t('dental.dental_pt_mat_scaler'), quantity: t('dental.dental_pt_qty_1pc'), required: true },
    { name: t('dental.dental_pt_mat_polish_paste'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_fluoride_gel'), quantity: t('dental.dental_pt_qty_1pc'), required: false }],

    anesthesia: [],
    photos: [
    { type: 'before', description: t('dental.dental_pt_photo_before_cleaning'), required: true },
    { type: 'after', description: t('dental.dental_pt_photo_after_cleaning'), required: true }],

    prescriptions: [],
    tags: [t('dental.dental_pt_tag_hygiene'), t('dental.dental_pt_tag_cleaning'), t('dental.dental_pt_tag_prevention')],
    estimatedDuration: 75,
    difficulty: 'low',
    isDefault: true
  },

  {
    id: 'crown_preparation',
    name: t('dental.dental_pt_name_crown_prep'),
    category: 'prosthetics',
    description: t('dental.dental_pt_desc_crown_prep'),
    icon: Scissors,
    color: 'purple',
    steps: [
    { type: 'procedure', name: t('dental.dental_pt_step_exam_planning'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_anesthesia'), duration: 10, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_tooth_prep'), duration: 30, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_impressions'), duration: 15, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_temp_crown_make'), duration: 20, required: true },
    { type: 'procedure', name: t('dental.dental_pt_step_temp_crown_fix'), duration: 10, required: true }],

    materials: [
    { name: t('dental.dental_pt_mat_impression_mass'), quantity: t('dental.dental_pt_qty_1set'), required: true },
    { name: t('dental.dental_pt_mat_temp_cement'), quantity: t('dental.dental_pt_qty_1pc'), required: true },
    { name: t('dental.dental_pt_mat_temp_crown_plastic'), quantity: t('dental.dental_pt_qty_1set'), required: true }],

    anesthesia: [
    { drug: t('dental.dental_pt_drug_lidocaine2'), dose: t('dental.dental_pt_qty_1_8ml'), method: t('dental.dental_pt_method_infiltration'), required: true }],

    photos: [
    { type: 'before', description: t('dental.dental_pt_photo_before_prep'), required: true },
    { type: 'after', description: t('dental.dental_pt_photo_after_prep'), required: true }],

    prescriptions: [
    { medication: t('dental.dental_pt_rx_ibuprofen'), dosage: t('dental.dental_pt_rx_dosage_400'), instructions: t('dental.dental_pt_rx_instr_pain'), required: false }],

    tags: [t('dental.dental_pt_tag_prosthetics'), t('dental.dental_pt_tag_crown'), t('dental.dental_pt_tag_prep')],
    estimatedDuration: 95,
    difficulty: 'high',
    isDefault: true
  }]
  );

  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterDifficulty, setFilterDifficulty] = useState('all');
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [, setIsEditing] = useState(false);
  const [, setEditingTemplate] = useState(null);

  // Фильтрация шаблонов
  const filteredTemplates = templates.filter((template) => {
    const matchesSearch = !searchQuery ||
    template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    template.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory = filterCategory === 'all' || template.category === filterCategory;
    const matchesDifficulty = filterDifficulty === 'all' || template.difficulty === filterDifficulty;

    return matchesSearch && matchesCategory && matchesDifficulty;
  });

  // Категории шаблонов
  const categories = [
  { id: 'all', label: t('dental.dental_pt_cat_all'), icon: FileText },
  { id: 'procedure', label: t('dental.dental_pt_cat_procedure'), icon: Scissors },
  { id: 'surgery', label: t('dental.dental_pt_cat_surgery'), icon: Scissors },
  { id: 'hygiene', label: t('dental.dental_pt_cat_hygiene'), icon: Scissors },
  { id: 'prosthetics', label: t('dental.dental_pt_cat_prosthetics'), icon: Scissors }];


  // Уровни сложности
  const difficulties = [
  { id: 'all', label: t('dental.dental_pt_diff_all'), color: 'gray' },
  { id: 'low', label: t('dental.dental_pt_diff_low'), color: 'green' },
  { id: 'medium', label: t('dental.dental_pt_diff_medium'), color: 'yellow' },
  { id: 'high', label: t('dental.dental_pt_diff_high'), color: 'red' }];


  // Обработчики
  const handleSelectTemplate = (template) => {
    if (onSelectTemplate) {
      onSelectTemplate(template);
    }
    onClose();
  };

  useEffect(() => {
    const handlers = [];

    document.querySelectorAll('button[data-protocol-template-select="true"]').forEach((button) => {
      const templateId = button.getAttribute('data-template-id');
      if (!templateId) {
        return;
      }

      const handler = (event) => {
        event.stopPropagation();
        const template = templates.find((item) => item.id === templateId);
        if (template) {
          handleSelectTemplate(template);
        }
      };

      button.addEventListener('click', handler);
      handlers.push([button, handler]);
    });

    return () => {
      handlers.forEach(([button, handler]) => {
        button.removeEventListener('click', handler);
      });
    };
  }, [handleSelectTemplate, templates, filteredTemplates, selectedTemplate]);

  const handleEditTemplate = (template) => {
    setEditingTemplate(template);
    setIsEditing(true);
  };

  const handleDeleteTemplate = (templateId) => {
    setTemplates((prev) => prev.filter((t) => t.id !== templateId));
  };











  const handleDuplicateTemplate = (template) => {
    const newTemplate = {
      ...template,
      id: Date.now().toString(),
      name: `${template.name} ${t('dental.dental_pt_copy_suffix')}`,
      isDefault: false
    };
    setTemplates((prev) => [...prev, newTemplate]);
  };

  // Рендер карточки шаблона
  const renderTemplateCard = (template) =>
  <div key={template.id} className="border rounded-lg p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
        template.color === 'blue' ? 'bg-blue-100 text-blue-600' :
        template.color === 'red' ? 'bg-red-100 text-red-600' :
        template.color === 'green' ? 'bg-green-100 text-green-600' :
        template.color === 'purple' ? 'bg-purple-100 text-purple-600' :
        'bg-gray-100 text-gray-600'}`
        }>
            <template.icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-semibold text-lg">{template.name}</h3>
            <p className="text-sm text-gray-600">{template.description}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-1">
          {template.isDefault &&
        <Star className="h-4 w-4 text-yellow-500" />
        }
          <div className={`w-3 h-3 rounded-full ${
        template.difficulty === 'low' ? 'bg-green-500' :
        template.difficulty === 'medium' ? 'bg-yellow-500' :
        template.difficulty === 'high' ? 'bg-red-500' :
        'bg-gray-500'}`
        } title={difficulties.find((d) => d.id === template.difficulty)?.label} />
        </div>
      </div>
      
      <div className="space-y-2 mb-4">
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {template.estimatedDuration} {t('dental.dental_pt_unit_min')}
          </div>
          <div className="flex items-center gap-1">
            <Scissors className="h-4 w-4" />
            {template.steps.length} {t('dental.dental_pt_unit_steps')}
          </div>
          <div className="flex items-center gap-1">
            <Pill className="h-4 w-4" />
            {template.materials.length} {t('dental.dental_pt_unit_materials')}
          </div>
        </div>
        
        <div className="flex items-center gap-1 flex-wrap">
          {template.tags.map((tag) =>
        <span key={tag} className="text-xs bg-gray-100 px-2 py-1 rounded">
              {tag}
            </span>
        )}
        </div>
      </div>
      
      <div className="flex gap-2">
        <button
        type="button"
        data-protocol-template-select="true"
        data-template-id={template.id}
        className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm">
        
          {t('dental.dental_pt_btn_use')}
        </button>
        <button
        onClick={() => handleEditTemplate(template)}
        className="px-3 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
        aria-label={t('dental.dental_pt_aria_edit_template', { name: template.name })}
        title={t('dental.dental_pt_btn_edit')}>
        
          <Edit className="h-4 w-4" />
        </button>
        <button
        onClick={() => handleDuplicateTemplate(template)}
        className="px-3 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
        aria-label={t('dental.dental_pt_aria_duplicate_template', { name: template.name })}
        title={t('dental.dental_pt_btn_duplicate')}>
        
          <Copy className="h-4 w-4" />
        </button>
        {!template.isDefault &&
      <button
        onClick={() => handleDeleteTemplate(template.id)}
        className="px-3 py-2 border border-gray-300 text-red-700 rounded-md hover:bg-red-50"
        aria-label={t('dental.dental_pt_aria_delete_template', { name: template.name })}
        title={t('dental.dental_pt_btn_delete')}>
        
            <Trash2 className="h-4 w-4" />
          </button>
      }
      </div>
    </div>;


  // Рендер детального просмотра шаблона
  const renderTemplateDetails = (template) =>
  <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{template.name}</h2>
        <button
        onClick={() => setSelectedTemplate(null)}
        aria-label={t('dental.dental_pt_aria_close_view', { name: template.name })}
        className="p-2 text-gray-500 hover:text-gray-700">
        
          <X className="h-5 w-5" />
        </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Шаги процедуры */}
        <div>
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Scissors className="h-4 w-4" />
            {t('dental.dental_pt_section_steps')}
          </h3>
          <div className="space-y-2">
            {template.steps.map((step, index) =>
          <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                <div className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{step.name}</div>
                  <div className="text-sm text-gray-600">
                    {step.duration} {t('dental.dental_pt_unit_min')} {step.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
              </div>
          )}
          </div>
        </div>
        
        {/* Материалы */}
        <div>
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <Pill className="h-4 w-4" />
            {t('dental.dental_pt_section_materials')}
          </h3>
          <div className="space-y-2">
            {template.materials.map((material, index) =>
          <div key={index} className="flex items-center gap-3 p-2 bg-gray-50 rounded">
                <div className="w-6 h-6 bg-green-500 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{material.name}</div>
                  <div className="text-sm text-gray-600">
                    {material.quantity} {material.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
              </div>
          )}
          </div>
        </div>
        
        {/* Анестезия */}
        {template.anesthesia.length > 0 &&
      <div>
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Syringe className="h-4 w-4" />
              {t('dental.dental_pt_section_anesthesia')}
            </h3>
            <div className="space-y-2">
              {template.anesthesia.map((anesthesia, index) =>
          <div key={index} className="p-2 bg-gray-50 rounded">
                  <div className="font-medium">{anesthesia.drug}</div>
                  <div className="text-sm text-gray-600">
                    {anesthesia.dose} - {anesthesia.method}
                  </div>
                </div>
          )}
            </div>
          </div>
      }
        
        {/* Фотофиксация */}
        {template.photos.length > 0 &&
      <div>
            <h3 className="font-semibold mb-3 flex items-center gap-2">
              <Camera className="h-4 w-4" />
              {t('dental.dental_pt_section_photos')}
            </h3>
            <div className="space-y-2">
              {template.photos.map((photo, index) =>
          <div key={index} className="p-2 bg-gray-50 rounded">
                  <div className="font-medium">{photo.description}</div>
                  <div className="text-sm text-gray-600">
                    {photo.type} {photo.required && <span className="text-red-500">*</span>}
                  </div>
                </div>
          )}
            </div>
          </div>
      }
      </div>
      
      <div className="flex gap-2">
        <button
        type="button"
        data-protocol-template-select="true"
        data-template-id={template.id}
        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
        
          {t('dental.dental_pt_btn_use_template')}
        </button>
        <button
        onClick={() => handleEditTemplate(template)}
        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">
        
          {t('dental.dental_pt_btn_edit')}
        </button>
      </div>
    </div>;


  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">{t('dental.dental_pt_title')}</h2>
            <p className="text-gray-600 text-sm">
              {t('dental.dental_pt_subtitle', { count: filteredTemplates.length })}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
              
              <Plus className="h-4 w-4" />
              {t('dental.dental_pt_btn_create')}
            </button>
            <button
              onClick={onClose}
              aria-label={t('dental.dental_pt_aria_close_modal')}
              className="p-2 text-gray-500 hover:text-gray-700">
              
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Панель поиска и фильтров */}
        <div className="p-4 border-b bg-gray-50">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Поиск */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder={t('dental.dental_pt_search_placeholder')}
                  aria-label={t('dental.dental_pt_aria_search')}
                  value={searchQuery}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                
              </div>
            </div>
            
            {/* Фильтры */}
            <div className="flex gap-2">
              <select
                value={filterCategory}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFilterCategory(e.target.value)}
                aria-label={t('dental.dental_pt_aria_filter_category')}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                
                {categories.map((category) =>
                <option key={category.id} value={category.id}>
                    {category.label}
                  </option>
                )}
              </select>
              
              <select
                value={filterDifficulty}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFilterDifficulty(e.target.value)}
                aria-label={t('dental.dental_pt_aria_filter_difficulty')}
                className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                
                {difficulties.map((difficulty) =>
                <option key={difficulty.id} value={difficulty.id}>
                    {difficulty.label}
                  </option>
                )}
              </select>
            </div>
          </div>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {selectedTemplate ?
          renderTemplateDetails(selectedTemplate) :

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {filteredTemplates.map((template) =>
            <div
              key={template.id}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedTemplate(template)}
              onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setSelectedTemplate(template);
                }
              }}>
                  {renderTemplateCard(template)}
                </div>
            )}
            </div>
          }
        </div>
      </div>
    </div>);

};


ProtocolTemplates.propTypes = {
  ...(ProtocolTemplates.propTypes || {}),
  onClose: PropTypes.any,
  onSelectTemplate: PropTypes.any,
};

export default ProtocolTemplates;
