import React, { useState, useEffect } from 'react';
import { FileText, Save, Plus, X, Camera, Upload, AlertCircle, CheckCircle, Brain } from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';
import { APPOINTMENT_STATUS, STATUS_LABELS, STATUS_COLORS } from '../../constants/appointmentStatus';
import { AIButton, AISuggestions, AIAssistant } from '../ai';
import { useEMRAI } from '../../hooks/useEMRAI';
import { Box, Grid, Divider } from '@mui/material';

const EMRSystem = ({ appointment, onSave, onComplete }) => {
  // Используем AI хук для работы с искусственным интеллектом
  const {
    loading: aiLoading,
    error: aiError,
    icd10Suggestions,
    getICD10Suggestions,
    analyzeComplaints,
    clearError
  } = useEMRAI();

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

  useEffect(() => {
    // Загрузка существующего EMR
    if (appointment?.emr) {
      setEmrData(appointment.emr);
    }
  }, [appointment]);

  const handleFieldChange = (field, value) => {
    setEmrData(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

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
      category: 'examination' // examination, before, after, documents
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

  const handleCompleteVisit = async () => {
    if (!emrData.isDraft) {
      await onComplete();
    }
  };

  const canStartEMR = appointment?.status === APPOINTMENT_STATUS.PAID;
  const canSaveEMR = appointment?.status === APPOINTMENT_STATUS.IN_VISIT;
  const canComplete = canSaveEMR && !emrData.isDraft;

  if (!canStartEMR) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Ожидание оплаты</h3>
          <p className="text-gray-600">
            ЭМК можно открыть только после оплаты записи
          </p>
          <Badge variant={STATUS_COLORS[appointment?.status]} className="mt-4">
            {STATUS_LABELS[appointment?.status]}
          </Badge>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок EMR */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-xl font-semibold">Электронная Медицинская Карта</h2>
              <p className="text-gray-500">
                {appointment?.patient_name} • {appointment?.specialist}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {emrData.isDraft ? (
              <Badge variant="warning">Черновик</Badge>
            ) : (
              <Badge variant="success">
                <CheckCircle className="w-4 h-4 mr-1" />
                Сохранено
              </Badge>
            )}
            
            {hasUnsavedChanges && (
              <Badge variant="info">Есть изменения</Badge>
            )}
          </div>
        </div>
      </Card>

      {/* Основные поля EMR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Жалобы */}
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">Жалобы пациента</h3>
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
            className="w-full h-32 p-3 border border-gray-300 rounded-lg resize-none"
            disabled={!canSaveEMR}
          />
        </Card>

        {/* Анамнез */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Анамнез</h3>
          <textarea
            value={emrData.anamnesis}
            onChange={(e) => handleFieldChange('anamnesis', e.target.value)}
            placeholder="Анамнез заболевания, жизни..."
            className="w-full h-32 p-3 border border-gray-300 rounded-lg resize-none"
            disabled={!canSaveEMR}
          />
        </Card>

        {/* Объективный осмотр */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Объективный осмотр</h3>
          <textarea
            value={emrData.examination}
            onChange={(e) => handleFieldChange('examination', e.target.value)}
            placeholder="Результаты осмотра..."
            className="w-full h-32 p-3 border border-gray-300 rounded-lg resize-none"
            disabled={!canSaveEMR}
          />
        </Card>

        {/* Диагноз и МКБ-10 */}
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">Диагноз</h3>
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
          <div className="space-y-3">
            <input
              type="text"
              value={emrData.diagnosis}
              onChange={(e) => handleFieldChange('diagnosis', e.target.value)}
              placeholder="Клинический диагноз"
              className="w-full p-3 border border-gray-300 rounded-lg"
              disabled={!canSaveEMR}
            />
            <input
              type="text"
              value={emrData.icd10}
              onChange={(e) => handleFieldChange('icd10', e.target.value)}
              placeholder="Код МКБ-10 (например: L70.0)"
              className="w-full p-3 border border-gray-300 rounded-lg"
              disabled={!canSaveEMR}
            />
            {icd10Suggestions.length > 0 && (
              <AISuggestions
                suggestions={icd10Suggestions}
                type="icd10"
                onSelect={(item) => {
                  handleFieldChange('icd10', item.code);
                  handleFieldChange('diagnosis', item.name);
                  setIcd10Suggestions([]);
                }}
                title="AI подсказки МКБ-10"
              />
            )}
          </div>
        </Card>
      </div>

      {/* Процедуры */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Выполненные процедуры</h3>
          <Button
            size="sm"
            onClick={handleProcedureAdd}
            disabled={!canSaveEMR}
          >
            <Plus className="w-4 h-4 mr-2" />
            Добавить процедуру
          </Button>
        </div>

        {emrData.procedures.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Процедуры не добавлены
          </div>
        ) : (
          <div className="space-y-3">
            {emrData.procedures.map(procedure => (
              <div key={procedure.id} className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg">
                <input
                  type="text"
                  value={procedure.name}
                  onChange={(e) => handleProcedureChange(procedure.id, 'name', e.target.value)}
                  placeholder="Название процедуры"
                  className="flex-1 p-2 border border-gray-300 rounded"
                  disabled={!canSaveEMR}
                />
                <input
                  type="text"
                  value={procedure.description}
                  onChange={(e) => handleProcedureChange(procedure.id, 'description', e.target.value)}
                  placeholder="Описание"
                  className="flex-1 p-2 border border-gray-300 rounded"
                  disabled={!canSaveEMR}
                />
                <input
                  type="number"
                  value={procedure.cost}
                  onChange={(e) => handleProcedureChange(procedure.id, 'cost', parseFloat(e.target.value) || 0)}
                  placeholder="Стоимость"
                  className="w-24 p-2 border border-gray-300 rounded"
                  disabled={!canSaveEMR}
                />
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => handleProcedureRemove(procedure.id)}
                  disabled={!canSaveEMR}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Рекомендации */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Рекомендации</h3>
        <textarea
          value={emrData.recommendations}
          onChange={(e) => handleFieldChange('recommendations', e.target.value)}
          placeholder="Рекомендации по лечению и наблюдению..."
          className="w-full h-24 p-3 border border-gray-300 rounded-lg resize-none"
          disabled={!canSaveEMR}
        />
      </Card>

      {/* Прикрепленные файлы */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Прикрепленные файлы</h3>
          <label className="cursor-pointer">
            <input
              type="file"
              multiple
              accept="image/*,.pdf,.doc,.docx"
              onChange={handleFileUpload}
              className="hidden"
              disabled={!canSaveEMR}
            />
            <Button 
              size="sm" 
              disabled={!canSaveEMR}
              onClick={(e) => {
                // Предотвращаем двойной клик
                e.preventDefault();
              }}
            >
              <Upload className="w-4 h-4 mr-2" />
              Загрузить файлы
            </Button>
          </label>
        </div>

        {emrData.attachments.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Файлы не прикреплены
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {emrData.attachments.map(attachment => (
              <div key={attachment.id} className="p-3 border border-gray-200 rounded-lg">
                <div className="text-sm font-medium truncate">{attachment.name}</div>
                <div className="text-xs text-gray-500">
                  {(attachment.size / 1024).toFixed(1)} KB
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Кнопки действий */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {hasUnsavedChanges && "Есть несохраненные изменения"}
          </div>
          
          <div className="flex gap-3">
            <Button
              onClick={handleSaveEMR}
              disabled={!canSaveEMR || isSaving}
            >
              <Save className="w-4 h-4 mr-2" />
              {isSaving ? 'Сохранение...' : 'Сохранить EMR'}
            </Button>
            
            <Button
              variant="success"
              onClick={handleCompleteVisit}
              disabled={!canComplete}
            >
              <CheckCircle className="w-4 h-4 mr-2" />
              Завершить прием
            </Button>
          </div>
        </div>
      </Card>

      {/* AI Assistant Modal */}
      {showAIAssistant && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-semibold">AI Анализ жалоб</h2>
                <button
                  onClick={() => setShowAIAssistant(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
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
                  // Автоматически заполняем рекомендации если есть
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
