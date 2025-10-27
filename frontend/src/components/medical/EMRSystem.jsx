import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Save, Plus, X, Camera, Upload, AlertCircle, CheckCircle, Brain } from 'lucide-react';
import { Card, Button, Badge, Box, Typography, Alert, CircularProgress } from '../ui/macos';
import { APPOINTMENT_STATUS, STATUS_LABELS, STATUS_COLORS } from '../../constants/appointmentStatus';
import { AI_ANALYSIS_TYPES, MCP_PROVIDERS, AI_ERROR_MESSAGES, ATTACHMENT_CATEGORIES } from '../../constants/ai';
import { AIButton, AISuggestions, AIAssistant } from '../ai';
import { useEMRAI } from '../../hooks/useEMRAI';
import { useDebounce } from '../../utils/debounce';

const EMRSystem = ({ appointment, onSave, onComplete }) => {
  // Используем AI хук для работы с искусственным интеллектом через MCP
  const {
    loading: aiLoading,
    error: aiError,
    icd10Suggestions,
    clinicalRecommendations,
    getICD10Suggestions,
    analyzeComplaints,
    analyzeSkinLesion,
    analyzeImage,
    clearError
  } = useEMRAI(true, MCP_PROVIDERS.DEEPSEEK); // Используем MCP с DeepSeek по умолчанию

  const [emrData, setEmrData] = useState({
    complaints: '',           // Жалобы
    anamnesis: '',           // Анамнез
    examination: '',         // Объективный осмотр
    diagnosis: '',           // Диагноз
    icd10: '',              // Код МКБ-10
    recommendations: '',     // Рекомендации
    procedures: [],          // Выполненные процедуры
    attachments: [],         // Прикрепленные файлы
    isDraft: true           // Черновик
  });

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showAIAssistant, setShowAIAssistant] = useState(false);
  const [selectedImageForAI, setSelectedImageForAI] = useState(null);
  const [imageAnalysisResult, setImageAnalysisResult] = useState(null);
  const [complaintsAnalysisCache, setComplaintsAnalysisCache] = useState({});
  const [selectedCategory, setSelectedCategory] = useState(ATTACHMENT_CATEGORIES.EXAMINATION);
  const [isDragOver, setIsDragOver] = useState(false);
  const [lastAutoSave, setLastAutoSave] = useState(null);

  useEffect(() => {
    // Загрузка существующего EMR
    if (appointment?.emr) {
      setEmrData(appointment.emr);
    }
  }, [appointment]);

  // Автоматический анализ жалоб при изменении
  useEffect(() => {
    if (emrData.complaints && appointment?.status === APPOINTMENT_STATUS.IN_VISIT) {
      debouncedAnalyzeComplaints(emrData.complaints);
    }
  }, [emrData.complaints, debouncedAnalyzeComplaints, appointment?.status]);

  // Предупреждение о несохраненных изменениях
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = 'У вас есть несохраненные изменения. Вы уверены, что хотите покинуть страницу?';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [hasUnsavedChanges]);

  // Автосохранение черновиков каждые 30 секунд
  useEffect(() => {
    if (appointment?.status !== APPOINTMENT_STATUS.IN_VISIT) return;
    
    const autoSaveInterval = setInterval(() => {
      autoSaveDraft();
    }, 30000); // 30 секунд

    return () => {
      clearInterval(autoSaveInterval);
    };
  }, [hasUnsavedChanges, appointment?.status, emrData]);

  const handleFieldChange = (field, value) => {
    setEmrData(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

  // Debounced анализ жалоб с кэшированием
  const debouncedAnalyzeComplaints = useDebounce(
    useCallback(async (complaints) => {
      if (!complaints || appointment?.status !== APPOINTMENT_STATUS.IN_VISIT) return;
      
      // Проверяем кэш
      const cacheKey = complaints.trim().toLowerCase();
      if (complaintsAnalysisCache[cacheKey]) {
        const cachedResult = complaintsAnalysisCache[cacheKey];
        if (cachedResult.patient_history) {
          handleFieldChange('anamnesis', cachedResult.patient_history);
        }
        if (cachedResult.examinations) {
          const examText = cachedResult.examinations.map(e => `${e.type}: ${e.name}`).join('\n');
          handleFieldChange('examination', examText);
        }
        if (cachedResult.lab_tests) {
          const recommendations = [
            'Лабораторные исследования:',
            ...cachedResult.lab_tests,
            '',
            'Дополнительное обследование:',
            ...(cachedResult.imaging_studies || [])
          ].join('\n');
          handleFieldChange('recommendations', recommendations);
        }
        return;
      }

      // Выполняем анализ и кэшируем результат
      try {
        const result = await analyzeComplaints({
          complaint: complaints,
          patient_age: appointment?.patient?.age,
          patient_gender: appointment?.patient?.gender
        });
        
        if (result) {
          setComplaintsAnalysisCache(prev => ({
            ...prev,
            [cacheKey]: result
          }));
          
          if (result.patient_history) {
            handleFieldChange('anamnesis', result.patient_history);
          }
          if (result.examinations) {
            const examText = result.examinations.map(e => `${e.type}: ${e.name}`).join('\n');
            handleFieldChange('examination', examText);
          }
          if (result.lab_tests) {
            const recommendations = [
              'Лабораторные исследования:',
              ...result.lab_tests,
              '',
              'Дополнительное обследование:',
              ...(result.imaging_studies || [])
            ].join('\n');
            handleFieldChange('recommendations', recommendations);
          }
        }
      } catch (error) {
        console.error('AI analysis error:', error);
      }
    }, [analyzeComplaints, appointment?.status, appointment?.patient?.age, appointment?.patient?.gender, complaintsAnalysisCache]),
    1000 // 1 секунда задержка
  );

  const handleProcedureAdd = () => {
    const newProcedure = {
      id: Date.now(),
      name: '',
      description: '',
      cost: 0
    };
    setEmrData(prev => ({
      ...prev,
      procedures: [...prev.procedures, newProcedure]
    }));
    setHasUnsavedChanges(true);
  };

  const handleProcedureRemove = (id) => {
    setEmrData(prev => ({
      ...prev,
      procedures: prev.procedures.filter(p => p.id !== id)
    }));
    setHasUnsavedChanges(true);
  };

  const handleProcedureChange = (id, field, value) => {
    setEmrData(prev => ({
      ...prev,
      procedures: prev.procedures.map(p => 
        p.id === id ? { ...p, [field]: value } : p
      )
    }));
    setHasUnsavedChanges(true);
  };

  const handleFileUpload = (event) => {
    const files = Array.from(event.target.files);
    const newAttachments = files.map(file => ({
      id: Date.now() + Math.random(),
      name: file.name,
      type: file.type,
      size: file.size,
      file: file,
      category: selectedCategory
    }));

    setEmrData(prev => ({
      ...prev,
      attachments: [...prev.attachments, ...newAttachments]
    }));
    setHasUnsavedChanges(true);
  };

  const handleRemoveAttachment = (attachmentId) => {
    if (window.confirm('Вы уверены, что хотите удалить этот файл?')) {
      setEmrData(prev => ({
        ...prev,
        attachments: prev.attachments.filter(attachment => attachment.id !== attachmentId)
      }));
      setHasUnsavedChanges(true);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    
    if (!canSaveEMR) return;
    
    const files = Array.from(e.dataTransfer.files);
    const newAttachments = files.map(file => ({
      id: Date.now() + Math.random(),
      name: file.name,
      type: file.type,
      size: file.size,
      file: file,
      category: selectedCategory
    }));

    setEmrData(prev => ({
      ...prev,
      attachments: [...prev.attachments, ...newAttachments]
    }));
    setHasUnsavedChanges(true);
  };

  const handleSaveEMR = async () => {
    setIsSaving(true);
    try {
      const emrToSave = {
        ...emrData,
        isDraft: false,
        savedAt: new Date().toISOString(),
        appointmentId: appointment.id
      };

      await onSave(emrToSave);
      setEmrData(prev => ({ ...prev, isDraft: false }));
      setHasUnsavedChanges(false);
    } catch (error) {
      console.error('EMR: Save error:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const autoSaveDraft = async () => {
    if (!hasUnsavedChanges || !canSaveEMR) return;
    
    try {
      const emrToSave = {
        ...emrData,
        isDraft: true,
        autoSavedAt: new Date().toISOString(),
        appointmentId: appointment.id
      };

      await onSave(emrToSave);
      setLastAutoSave(new Date());
      console.log('EMR: Auto-saved draft');
    } catch (error) {
      console.error('EMR: Auto-save error:', error);
    }
  };

  // Функция явного сохранения черновика
  const handleSaveDraft = async () => {
    if (!canSaveEMR) return;
    
    try {
      const emrToSave = {
        ...emrData,
        isDraft: true,
        savedAt: new Date().toISOString(),
        appointmentId: appointment.id
      };

      await onSave(emrToSave);
      setLastAutoSave(new Date());
      setHasUnsavedChanges(false);
      
      // Показать уведомление об успешном сохранении
      if (window.showToast) {
        window.showToast('Черновик сохранен', 'success');
      }
      console.log('EMR: Draft saved manually');
    } catch (error) {
      console.error('EMR: Manual save error:', error);
      if (window.showToast) {
        window.showToast('Ошибка сохранения черновика', 'error');
      }
    }
  };

  const handleCompleteVisit = async () => {
    if (!emrData.isDraft) {
      await onComplete();
    }
  };

  // Debounced автоматический запрос МКБ-10 подсказок при вводе диагноза
  const debouncedICD10Request = useDebounce(
    useCallback(async (complaints, diagnosis) => {
      if ((complaints || diagnosis) && canSaveEMR) {
        await getICD10Suggestions(complaints, diagnosis, appointment?.specialty);
      }
    }, [getICD10Suggestions, canSaveEMR, appointment?.specialty]),
    800 // 800ms задержка
  );

  // Обработка изменения диагноза с автоподсказками
  const handleDiagnosisChange = (value) => {
    handleFieldChange('diagnosis', value);
    debouncedICD10Request(emrData.complaints, value);
  };

  const canStartEMR = appointment?.status === APPOINTMENT_STATUS.PAID;
  const canSaveEMR = appointment?.status === APPOINTMENT_STATUS.IN_VISIT;
  const canComplete = canSaveEMR && !emrData.isDraft;

  if (!canStartEMR) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 32 }}>
          <AlertCircle style={{ width: 48, height: 48, color: 'var(--mac-accent-orange)', margin: '0 auto 16px' }} />
          <Typography variant="h6" gutterBottom>Ожидание оплаты</Typography>
          <Typography variant="body2" color="textSecondary">
            ЭМК можно открыть только после оплаты записи
          </Typography>
          <Badge variant={STATUS_COLORS[appointment?.status]} style={{ marginTop: 16 }}>
            {STATUS_LABELS[appointment?.status]}
          </Badge>
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Отображение AI ошибок */}
      {aiError && (
        <Alert severity="error" style={{ marginBottom: 16 }} onClose={clearError}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle style={{ width: 16, height: 16 }} />
            <span>{aiError}</span>
          </div>
        </Alert>
      )}
      
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <FileText style={{ width: 24, height: 24, color: 'var(--mac-accent-blue)' }} />
            <div>
              <Typography variant="h5">Электронная Медицинская Карта</Typography>
              <Typography variant="body2" color="textSecondary">
                {appointment?.patient_name} • {appointment?.specialist}
              </Typography>
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {emrData.isDraft ? (
              <Badge variant="warning">Черновик</Badge>
            ) : (
              <Badge variant="success">
                <CheckCircle style={{ width: 16, height: 16, marginRight: 4 }} />
                Сохранено
              </Badge>
            )}
            
            {hasUnsavedChanges && (
              <Badge variant="info">Есть изменения</Badge>
            )}
          </div>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">Жалобы пациента</Typography>
            <AIButton
              onClick={() => setShowAIAssistant(true)}
              loading={aiLoading}
              variant="icon"
              tooltip="AI анализ жалоб"
              disabled={!emrData.complaints || !canSaveEMR}
            />
          </div>
          <textarea
            value={emrData.complaints}
            onChange={(e) => handleFieldChange('complaints', e.target.value)}
            placeholder="Опишите жалобы пациента..."
            style={{ width: '100%', height: 128, padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8, resize: 'none' }}
            disabled={!canSaveEMR}
          />
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">Анамнез</Typography>
            <AIButton
              onClick={async () => {
                if (emrData.complaints) {
                  const result = await analyzeComplaints({
                    complaint: emrData.complaints,
                    patient_age: appointment?.patient?.age,
                    patient_gender: appointment?.patient?.gender
                  });
                  if (result && result.patient_history) {
                    handleFieldChange('anamnesis', result.patient_history);
                  }
                }
              }}
              loading={aiLoading}
              variant="icon"
              tooltip="AI помощь с анамнезом"
              disabled={!emrData.complaints || !canSaveEMR}
            />
          </div>
          <textarea
            value={emrData.anamnesis}
            onChange={(e) => handleFieldChange('anamnesis', e.target.value)}
            placeholder="Анамнез заболевания, жизни..."
            style={{ width: '100%', height: 128, padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8, resize: 'none' }}
            disabled={!canSaveEMR}
          />
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">Объективный осмотр</Typography>
            <AIButton
              onClick={async () => {
                if (emrData.complaints) {
                  const result = await analyzeComplaints({
                    complaint: emrData.complaints,
                    patient_age: appointment?.patient?.age,
                    patient_gender: appointment?.patient?.gender
                  });
                  if (result && result.examinations) {
                    const examText = result.examinations.map(e => `${e.type}: ${e.name}`).join('\n');
                    handleFieldChange('examination', examText);
                  }
                }
              }}
              loading={aiLoading}
              variant="icon"
              tooltip="AI рекомендации по осмотру"
              disabled={!emrData.complaints || !canSaveEMR}
            />
          </div>
          <textarea
            value={emrData.examination}
            onChange={(e) => handleFieldChange('examination', e.target.value)}
            placeholder="Результаты осмотра..."
            style={{ width: '100%', height: 128, padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8, resize: 'none' }}
            disabled={!canSaveEMR}
          />
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Typography variant="h6">Диагноз</Typography>
            <AIButton
              onClick={async () => {
                if (emrData.complaints || emrData.diagnosis) {
                  const suggestions = await getICD10Suggestions(emrData.complaints, emrData.diagnosis);
                  // setIcd10Suggestions уже вызывается в хуке
                }
              }}
              loading={aiLoading}
              variant="icon"
              tooltip="AI подсказки МКБ-10"
              disabled={(!emrData.complaints && !emrData.diagnosis) || !canSaveEMR}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input
              type="text"
              value={emrData.diagnosis}
              onChange={(e) => handleDiagnosisChange(e.target.value)}
              placeholder="Клинический диагноз (автоподсказки МКБ-10)"
              style={{ width: '100%', padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8 }}
              disabled={!canSaveEMR}
            />
            <input
              type="text"
              value={emrData.icd10}
              onChange={(e) => handleFieldChange('icd10', e.target.value)}
              placeholder="Код МКБ-10 (например: L70.0)"
              style={{ width: '100%', padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8 }}
              disabled={!canSaveEMR}
            />
            {(icd10Suggestions.length > 0 || clinicalRecommendations) && (
              <AISuggestions
                suggestions={icd10Suggestions}
                clinicalRecommendations={clinicalRecommendations}
                type="icd10"
                onSelect={(item) => {
                  handleFieldChange('icd10', item.code);
                  handleFieldChange('diagnosis', item.name || item.description);
                }}
                title="AI подсказки МКБ-10"
              />
            )}
          </div>
        </Card>
      </div>

      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <Typography variant="h6">Выполненные процедуры</Typography>
          <Button
            size="small"
            onClick={handleProcedureAdd}
            disabled={!canSaveEMR}
          >
            <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
            Добавить процедуру
          </Button>
        </div>

        {emrData.procedures.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--mac-text-secondary)' }}>
            Процедуры не добавлены
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {emrData.procedures.map(procedure => (
              <div key={procedure.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
                <input
                  type="text"
                  value={procedure.name}
                  onChange={(e) => handleProcedureChange(procedure.id, 'name', e.target.value)}
                  placeholder="Название процедуры"
                  style={{ flex: 1, padding: 8, border: '1px solid var(--mac-border)', borderRadius: 4 }}
                  disabled={!canSaveEMR}
                />
                <input
                  type="text"
                  value={procedure.description}
                  onChange={(e) => handleProcedureChange(procedure.id, 'description', e.target.value)}
                  placeholder="Описание"
                  style={{ flex: 1, padding: 8, border: '1px solid var(--mac-border)', borderRadius: 4 }}
                  disabled={!canSaveEMR}
                />
                <input
                  type="number"
                  value={procedure.cost}
                  onChange={(e) => handleProcedureChange(procedure.id, 'cost', parseFloat(e.target.value) || 0)}
                  placeholder="Стоимость"
                  style={{ width: 96, padding: 8, border: '1px solid var(--mac-border)', borderRadius: 4 }}
                  disabled={!canSaveEMR}
                />
                <Button
                  size="small"
                  variant="danger"
                  onClick={() => handleProcedureRemove(procedure.id)}
                  disabled={!canSaveEMR}
                >
                  <X style={{ width: 16, height: 16 }} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Typography variant="h6">Рекомендации</Typography>
          <AIButton
            onClick={async () => {
              if (emrData.diagnosis || emrData.complaints) {
                const result = await analyzeComplaints({
                  complaint: emrData.complaints,
                  diagnosis: emrData.diagnosis,
                  patient_age: appointment?.patient?.age,
                  patient_gender: appointment?.patient?.gender
                });
                if (result && result.lab_tests) {
                  const recommendations = [
                    'Лабораторные исследования:',
                    ...result.lab_tests,
                    '',
                    'Дополнительное обследование:',
                    ...(result.imaging_studies || [])
                  ].join('\n');
                  handleFieldChange('recommendations', recommendations);
                }
              }
            }}
            loading={aiLoading}
            variant="icon"
            tooltip="AI рекомендации по лечению"
            disabled={(!emrData.diagnosis && !emrData.complaints) || !canSaveEMR}
          />
        </div>
        <textarea
          value={emrData.recommendations}
          onChange={(e) => handleFieldChange('recommendations', e.target.value)}
          placeholder="Рекомендации по лечению и наблюдению..."
          style={{ width: '100%', height: 96, padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8, resize: 'none' }}
          disabled={!canSaveEMR}
        />
      </Card>

      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <Typography variant="h6">Прикрепленные файлы</Typography>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                Категория файла
              </label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                style={{
                  padding: '8px 12px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 6,
                  backgroundColor: 'var(--mac-background)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 14
                }}
                disabled={!canSaveEMR}
              >
                <option value={ATTACHMENT_CATEGORIES.EXAMINATION}>Обследование</option>
                <option value={ATTACHMENT_CATEGORIES.DOCUMENTS}>Документы</option>
                <option value={ATTACHMENT_CATEGORIES.BEFORE_AFTER}>До/После</option>
                <option value={ATTACHMENT_CATEGORIES.LAB_RESULTS}>Анализы</option>
              </select>
            </div>
            <label style={{ cursor: 'pointer' }}>
              <input
                type="file"
                multiple
                accept="image/*,.pdf,.doc,.docx"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
                disabled={!canSaveEMR}
              />
              <Button 
                size="small" 
                disabled={!canSaveEMR}
                onClick={(e) => e.preventDefault()}
              >
                <Upload style={{ width: 16, height: 16, marginRight: 8 }} />
                Загрузить файлы
              </Button>
            </label>
          </div>
        </div>

        {emrData.attachments.length === 0 ? (
          <div 
            style={{ 
              textAlign: 'center', 
              padding: 32, 
              color: 'var(--mac-text-secondary)',
              border: isDragOver ? '2px dashed var(--mac-accent-blue)' : '2px dashed var(--mac-border)',
              borderRadius: 8,
              backgroundColor: isDragOver ? 'var(--mac-accent-blue-light)' : 'transparent',
              transition: 'all 0.2s ease'
            }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {isDragOver ? (
              <div>
                <Upload style={{ width: 32, height: 32, margin: '0 auto 16px', color: 'var(--mac-accent-blue)' }} />
                <div>Отпустите файлы для загрузки</div>
              </div>
            ) : (
              <div>
                <Upload style={{ width: 32, height: 32, margin: '0 auto 16px', color: 'var(--mac-text-secondary)' }} />
                <div>Перетащите файлы сюда или используйте кнопку загрузки</div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {emrData.attachments.map(attachment => (
              <div key={attachment.id} style={{ padding: 12, border: '1px solid var(--mac-border)', borderRadius: 8, position: 'relative' }}>
                {/* Миниатюра изображения */}
                {attachment.type?.startsWith('image/') ? (
                  <div style={{ marginBottom: 8 }}>
                    <img
                      src={URL.createObjectURL(attachment.file)}
                      alt={attachment.name}
                      style={{
                        width: '100%',
                        height: 120,
                        objectFit: 'cover',
                        borderRadius: 6,
                        backgroundColor: 'var(--mac-background-secondary)'
                      }}
                    />
                  </div>
                ) : (
                  <div style={{
                    width: '100%',
                    height: 120,
                    backgroundColor: 'var(--mac-background-secondary)',
                    borderRadius: 6,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 8
                  }}>
                    <FileText style={{ width: 32, height: 32, color: 'var(--mac-text-secondary)' }} />
                  </div>
                )}
                
                {/* Информация о файле */}
                <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>
                  {attachment.name}
                </div>
                <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 8 }}>
                  {(attachment.size / 1024).toFixed(1)} KB • {attachment.category}
                </div>
                
                {/* AI анализ для изображений */}
                {attachment.type?.startsWith('image/') && (
                  <AIButton
                    onClick={async () => {
                      setSelectedImageForAI(attachment);
                      try {
                        const result = attachment.category === ATTACHMENT_CATEGORIES.EXAMINATION 
                          ? await analyzeSkinLesion(
                              attachment.file,
                              { location: 'Не указано', size: 'Не указано' },
                              { complaints: emrData.complaints }
                            )
                          : await analyzeImage(
                              attachment.file,
                              'general',
                              { clinicalContext: emrData.complaints }
                            );
                        
                        setImageAnalysisResult(result);
                        
                        if (result && result.findings) {
                          const aiAnalysis = `\n\nAI Анализ изображения "${attachment.name}":\n${result.findings}`;
                          handleFieldChange('examination', emrData.examination + aiAnalysis);
                        }
                      } catch (err) {
                        console.error('Image AI analysis error:', err);
                      }
                    }}
                    loading={aiLoading && selectedImageForAI?.id === attachment.id}
                    variant="text"
                    size="sm"
                    tooltip="AI анализ изображения"
                    disabled={!canSaveEMR}
                  >
                    <Brain style={{ width: 12, height: 12, marginRight: 4 }} />
                    AI
                  </AIButton>
                )}
                
                {/* Кнопка удаления */}
                <button
                  onClick={() => handleRemoveAttachment(attachment.id)}
                  style={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    backgroundColor: 'var(--mac-accent-red)',
                    color: 'white',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    opacity: 0.8,
                    transition: 'opacity 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.target.style.opacity = '1'}
                  onMouseLeave={(e) => e.target.style.opacity = '0.8'}
                  disabled={!canSaveEMR}
                >
                  <X style={{ width: 12, height: 12 }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 14, color: 'var(--mac-text-secondary)' }}>
            {hasUnsavedChanges && "Есть несохраненные изменения"}
            {lastAutoSave && !hasUnsavedChanges && (
              <span style={{ marginLeft: 8 }}>
                Последнее автосохранение: {lastAutoSave.toLocaleTimeString()}
              </span>
            )}
          </div>
          
          <div style={{ display: 'flex', gap: 12 }}>
            <Button
              onClick={handleSaveEMR}
              disabled={!canSaveEMR || isSaving}
            >
              <Save style={{ width: 16, height: 16, marginRight: 8 }} />
              {isSaving ? 'Сохранение...' : 'Сохранить EMR'}
            </Button>
            
            <Button
              variant="secondary"
              onClick={handleSaveDraft}
              disabled={!canSaveEMR}
              style={{ 
                backgroundColor: 'var(--mac-button-secondary)', 
                color: 'var(--mac-text-primary)',
                border: '1px solid var(--mac-border)'
              }}
            >
              <Save style={{ width: 16, height: 16, marginRight: 8 }} />
              Сохранить черновик
            </Button>
            
            <Button
              variant="success"
              onClick={handleCompleteVisit}
              disabled={!canComplete}
            >
              <CheckCircle style={{ width: 16, height: 16, marginRight: 8 }} />
              Завершить прием
            </Button>
          </div>
        </div>
      </Card>

      {showAIAssistant && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 16 }}>
          <div style={{ backgroundColor: 'white', borderRadius: 8, maxWidth: '64rem', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ padding: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <Typography variant="h4">AI Анализ жалоб</Typography>
                <button
                  onClick={() => setShowAIAssistant(false)}
                  style={{ padding: 8, border: 'none', background: 'transparent', cursor: 'pointer', borderRadius: 4 }}
                >
                  <X style={{ width: 20, height: 20 }} />
                </button>
              </div>
              
              <AIAssistant
                analysisType="complaint"
                data={{
                  complaint: emrData.complaints,
                  patient_age: appointment?.patient?.age,
                  patient_gender: appointment?.patient?.gender
                }}
                onResult={(result) => {
                  if (result.recommendations) {
                    const recommendations = result.lab_tests?.join('\n') || '';
                    handleFieldChange('recommendations', recommendations);
                  }
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EMRSystem;

