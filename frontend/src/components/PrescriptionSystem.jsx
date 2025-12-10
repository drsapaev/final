import React, { useState, useEffect } from 'react';
import { Pill, Plus, X, Save, Printer, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, Button, Badge } from './ui/native';
import { APPOINTMENT_STATUS, STATUS_LABELS, STATUS_COLORS } from '../constants/appointmentStatus';

import logger from '../utils/logger';
const PrescriptionSystem = ({ appointment, emr, onSave, onPrint }) => {
  const [prescription, setPrescription] = useState({
    medications: [],         // Список препаратов
    instructions: '',        // Общие инструкции
    doctorNotes: '',         // Заметки врача
    isDraft: true,          // Черновик
    createdAt: null,
    printedAt: null
  });

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    // Загрузка существующего рецепта
    if (appointment?.prescription) {
      setPrescription(appointment.prescription);
    }
  }, [appointment]);

  const handleMedicationAdd = () => {
    const newMedication = {
      id: Date.now(),
      name: '',              // Название препарата
      dosage: '',            // Дозировка
      frequency: '',         // Кратность приема
      duration: '',          // Продолжительность
      instructions: '',      // Инструкции по применению
      quantity: 1            // Количество
    };
    
    setPrescription(prev => ({
      ...prev,
      medications: [...prev.medications, newMedication]
    }));
    setHasUnsavedChanges(true);
  };

  const handleMedicationRemove = (id) => {
    setPrescription(prev => ({
      ...prev,
      medications: prev.medications.filter(m => m.id !== id)
    }));
    setHasUnsavedChanges(true);
  };

  const handleMedicationChange = (id, field, value) => {
    setPrescription(prev => ({
      ...prev,
      medications: prev.medications.map(m => 
        m.id === id ? { ...m, [field]: value } : m
      )
    }));
    setHasUnsavedChanges(true);
  };

  const handleFieldChange = (field, value) => {
    setPrescription(prev => ({
      ...prev,
      [field]: value
    }));
    setHasUnsavedChanges(true);
  };

  const handleSavePrescription = async () => {
    setIsSaving(true);
    try {
      const prescriptionToSave = {
        ...prescription,
        isDraft: false,
        savedAt: new Date().toISOString(),
        appointmentId: appointment.id,
        doctorId: appointment.doctor_id
      };

      await onSave(prescriptionToSave);
      setPrescription(prev => ({ ...prev, isDraft: false }));
      setHasUnsavedChanges(false);
    } catch (error) {
      logger.error('Prescription: Save error:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePrintPrescription = async () => {
    try {
      await onPrint(prescription);
      setPrescription(prev => ({ 
        ...prev, 
        printedAt: new Date().toISOString() 
      }));
    } catch (error) {
      logger.error('Prescription: Print error:', error);
    }
  };

  // Проверки доступности
  const canCreatePrescription = emr && !emr.isDraft && 
    (appointment?.status === APPOINTMENT_STATUS.IN_VISIT || 
     appointment?.status === APPOINTMENT_STATUS.COMPLETED);
  
  const canEdit = canCreatePrescription && appointment?.status !== APPOINTMENT_STATUS.COMPLETED;

  if (!emr) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Сначала создайте ЭМК</h3>
          <p className="text-gray-600">
            Рецепт можно оформить только после сохранения ЭМК
          </p>
        </div>
      </Card>
    );
  }

  if (emr.isDraft) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">ЭМК не сохранена</h3>
          <p className="text-gray-600">
            Сохраните ЭМК перед оформлением рецепта
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок рецепта */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Pill className="w-6 h-6 text-green-600" />
            <div>
              <h2 className="text-xl font-semibold">Рецепт</h2>
              <p className="text-gray-500">
                {appointment?.patient_name} • {appointment?.specialist}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {prescription.isDraft ? (
              <Badge variant="warning">Черновик</Badge>
            ) : (
              <Badge variant="success">
                <CheckCircle className="w-4 h-4 mr-1" />
                Сохранено
              </Badge>
            )}
            
            {prescription.printedAt && (
              <Badge variant="info">Напечатан</Badge>
            )}
            
            {hasUnsavedChanges && (
              <Badge variant="info">Есть изменения</Badge>
            )}
          </div>
        </div>
      </Card>

      {/* Список препаратов */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Назначенные препараты</h3>
          <Button
            size="sm"
            onClick={handleMedicationAdd}
            disabled={!canEdit}
          >
            <Plus className="w-4 h-4 mr-2" />
            Добавить препарат
          </Button>
        </div>

        {prescription.medications.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Препараты не назначены
          </div>
        ) : (
          <div className="space-y-4">
            {prescription.medications.map((medication, index) => (
              <div key={medication.id} className="p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium">Препарат #{index + 1}</h4>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => handleMedicationRemove(medication.id)}
                    disabled={!canEdit}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Название препарата</label>
                    <input
                      type="text"
                      value={medication.name}
                      onChange={(e) => handleMedicationChange(medication.id, 'name', e.target.value)}
                      placeholder="Например: Амоксициллин"
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Дозировка</label>
                    <input
                      type="text"
                      value={medication.dosage}
                      onChange={(e) => handleMedicationChange(medication.id, 'dosage', e.target.value)}
                      placeholder="Например: 500мг"
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Кратность</label>
                    <input
                      type="text"
                      value={medication.frequency}
                      onChange={(e) => handleMedicationChange(medication.id, 'frequency', e.target.value)}
                      placeholder="Например: 3 раза в день"
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Продолжительность</label>
                    <input
                      type="text"
                      value={medication.duration}
                      onChange={(e) => handleMedicationChange(medication.id, 'duration', e.target.value)}
                      placeholder="Например: 7 дней"
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Количество</label>
                    <input
                      type="number"
                      value={medication.quantity}
                      onChange={(e) => handleMedicationChange(medication.id, 'quantity', parseInt(e.target.value) || 1)}
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                  
                  <div className="md:col-span-2 lg:col-span-1">
                    <label className="block text-sm font-medium mb-1">Особые указания</label>
                    <input
                      type="text"
                      value={medication.instructions}
                      onChange={(e) => handleMedicationChange(medication.id, 'instructions', e.target.value)}
                      placeholder="Например: после еды"
                      className="w-full p-2 border border-gray-300 rounded"
                      disabled={!canEdit}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Общие инструкции */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Общие инструкции</h3>
        <textarea
          value={prescription.instructions}
          onChange={(e) => handleFieldChange('instructions', e.target.value)}
          placeholder="Общие рекомендации по приему препаратов..."
          className="w-full h-24 p-3 border border-gray-300 rounded-lg resize-none"
          disabled={!canEdit}
        />
      </Card>

      {/* Заметки врача */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Заметки врача</h3>
        <textarea
          value={prescription.doctorNotes}
          onChange={(e) => handleFieldChange('doctorNotes', e.target.value)}
          placeholder="Внутренние заметки врача..."
          className="w-full h-20 p-3 border border-gray-300 rounded-lg resize-none"
          disabled={!canEdit}
        />
      </Card>

      {/* Предпросмотр рецепта */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Предпросмотр рецепта</h3>
        
        <div className="bg-white border-2 border-dashed border-gray-300 p-6 rounded-lg">
          <div className="text-center space-y-4">
            <div className="font-bold text-lg">РЕЦЕПТ</div>
            <div className="text-sm">
              <div>Пациент: {appointment?.patient_name}</div>
              <div>Дата: {new Date().toLocaleDateString('ru-RU')}</div>
              <div>Врач: {appointment?.specialist}</div>
            </div>
            
            <div className="border-t pt-4">
              {prescription.medications.map((med, index) => (
                <div key={med.id} className="text-left mb-3">
                  <div className="font-medium">
                    {index + 1}. {med.name} {med.dosage}
                  </div>
                  <div className="text-sm text-gray-600">
                    {med.frequency} • {med.duration} • {med.quantity} шт.
                  </div>
                  {med.instructions && (
                    <div className="text-sm text-gray-500 italic">
                      {med.instructions}
                    </div>
                  )}
                </div>
              ))}
            </div>
            
            {prescription.instructions && (
              <div className="border-t pt-4 text-sm">
                <div className="font-medium">Инструкции:</div>
                <div>{prescription.instructions}</div>
              </div>
            )}
            
            <div className="border-t pt-4 text-xs text-gray-500">
              Подпись врача: _________________
            </div>
          </div>
        </div>
      </Card>

      {/* Кнопки действий */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {hasUnsavedChanges && 'Есть несохраненные изменения'}
          </div>
          
          <div className="flex gap-3">
            <Button
              onClick={handleSavePrescription}
              disabled={!canEdit || isSaving || prescription.medications.length === 0}
            >
              <Save className="w-4 h-4 mr-2" />
              {isSaving ? 'Сохранение...' : 'Сохранить рецепт'}
            </Button>
            
            <Button
              variant="outline"
              onClick={handlePrintPrescription}
              disabled={prescription.isDraft}
            >
              <Printer className="w-4 h-4 mr-2" />
              Печать рецепта
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default PrescriptionSystem;

