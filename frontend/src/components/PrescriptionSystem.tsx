
import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Pill, Plus, X, Save, Printer, AlertCircle, CheckCircle } from 'lucide-react';
import { Card, Button, Badge,
  Input } from './ui/macos';
import logger from '../utils/logger';
import { useTranslation } from '../i18n/useTranslation';
import React from "react";
const createEmptyPrescription = () => ({
  medications: [], // Список препаратов
  instructions: '', // Общие инструкции
  doctorNotes: '', // Заметки врача
  isDraft: true, // Черновик
  createdAt: null,
  printedAt: null
});

const PrescriptionSystem = ({
  appointment,
  emr,
  prescription: initialPrescription,
  canCreatePrescription,
  onSave,
  onPrint
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [prescription, setPrescription] = useState(() => createEmptyPrescription());

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    // Загрузка существующего рецепта
    const sourcePrescription = initialPrescription || appointment?.prescription;

    if (sourcePrescription) {
      setPrescription({
        ...createEmptyPrescription(),
        ...sourcePrescription
      });
      setHasUnsavedChanges(false);
      return;
    }

    setPrescription(createEmptyPrescription());
    setHasUnsavedChanges(false);
  }, [appointment, initialPrescription]);

  const handleMedicationAdd = () => {
    const newMedication = {
      id: Date.now(),
      name: '', // Название препарата
      dosage: '', // Дозировка
      frequency: '', // Кратность приема
      duration: '', // Продолжительность
      instructions: '', // Инструкции по применению
      quantity: 1 // Количество
    };

    setPrescription((prev) => ({
      ...prev,
      medications: [...prev.medications, newMedication]
    }));
    setHasUnsavedChanges(true);
  };

  const handleMedicationRemove = (id) => {
    setPrescription((prev) => ({
      ...prev,
      medications: prev.medications.filter((m) => m.id !== id)
    }));
    setHasUnsavedChanges(true);
  };

  const handleMedicationChange = (id, field, value) => {
    setPrescription((prev) => ({
      ...prev,
      medications: prev.medications.map((m) =>
      m.id === id ? { ...m, [field]: value } : m
      )
    }));
    setHasUnsavedChanges(true);
  };

  const handleFieldChange = (field, value) => {
    setPrescription((prev) => ({
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
      setPrescription((prev) => ({ ...prev, isDraft: false }));
      setHasUnsavedChanges(false);
    } catch (error) {
      logger.error('Prescription: Save error:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePrintPrescription = async () => {
    try {
      if (typeof onPrint !== 'function') {
        logger.warn('Prescription: Print skipped because onPrint handler is missing');
        return;
      }

      await onPrint(prescription);
      setPrescription((prev) => ({
        ...prev,
        printedAt: new Date().toISOString()
      }));
    } catch (error) {
      logger.error('Prescription: Print error:', error);
    }
  };

  // Проверки доступности
  const prescriptionEligible = canCreatePrescription === true;
  const canEdit = prescriptionEligible;
  const prescriptionEligibilityLabel = prescriptionEligible
    ? t('misc.ps_available')
    : t('misc.ps_unavailable');

  if (!emr && !prescriptionEligible) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">{t('misc.ps_create_emr_first')}</h3>
          <p className="text-gray-600">
            {t('misc.ps_create_emr_first_desc')}
          </p>
        </div>
      </Card>);

  }

  if (emr?.isDraft && !prescriptionEligible) {
    return (
      <Card className="p-6">
        <div className="text-center py-8">
          <AlertCircle className="w-12 h-12 text-orange-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">{t('misc.ps_emr_not_saved')}</h3>
          <p className="text-gray-600">
            {t('misc.ps_emr_not_saved_desc')}
          </p>
        </div>
      </Card>);

  }

  return (
    <div className="space-y-6">
      {/* Заголовок рецепта */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Pill className="w-6 h-6 text-green-600" />
            <div>
              <h2 className="text-xl font-semibold">{t('misc.ps_title')}</h2>
              <p className="text-gray-500">
                {appointment?.patient_name} • {appointment?.specialist}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                {prescriptionEligibilityLabel}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Badge variant={prescriptionEligible ? 'success' : 'warning'}>
              {prescriptionEligible ? t('misc.ps_available_short') : t('misc.ps_unavailable_short')}
            </Badge>
            {prescription.isDraft ?
            <Badge variant="warning">{t('misc.ps_draft')}</Badge> :

            <Badge variant="success">
                <CheckCircle className="w-4 h-4 mr-1" />
                {t('misc.ps_saved')}
              </Badge>
            }

            {prescription.printedAt &&
            <Badge variant="info">{t('misc.ps_printed')}</Badge>
            }

            {hasUnsavedChanges &&
            <Badge variant="info">{t('misc.ps_has_changes')}</Badge>
            }
          </div>
        </div>
      </Card>

      {/* Список препаратов */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{t('misc.ps_medications_title')}</h3>
          <Button
            size="small"
            onClick={handleMedicationAdd}
            disabled={!canEdit}>

            <Plus className="w-4 h-4 mr-2" />
            {t('misc.ps_add_medication')}
          </Button>
        </div>

        {prescription.medications.length === 0 ?
        <div className="text-center py-8 text-gray-500">
            {t('misc.ps_no_medications')}
          </div> :

        <div className="space-y-4">
            {prescription.medications.map((medication, index) =>
          <div key={medication.id} className="p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-medium">{t('misc.ps_medication_n', { n: index + 1 })}</h4>
                  <Button
                size="small"
                variant="danger"
                onClick={() => handleMedicationRemove(medication.id)}
                type="button"
                title={t('misc.ps_remove_medication', { n: index + 1 })}
                aria-label={t('misc.ps_remove_medication', { n: index + 1 })}
                disabled={!canEdit}>
                
                    <X aria-hidden="true" className="w-4 h-4" />
                  </Button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_name')}</label>
                    <Input
                  type="text"
                  aria-label={`Medication ${index + 1} name`}
                  value={medication.name}
                  onChange={(e) => handleMedicationChange(medication.id, 'name', e.target.value)}
                  placeholder={t('misc.ps_med_name_ph')}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_dosage')}</label>
                    <Input
                  type="text"
                  aria-label={`Medication ${index + 1} dosage`}
                  value={medication.dosage}
                  onChange={(e) => handleMedicationChange(medication.id, 'dosage', e.target.value)}
                  placeholder={t('misc.ps_med_dosage_ph')}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_frequency')}</label>
                    <Input
                  type="text"
                  aria-label={`Medication ${index + 1} frequency`}
                  value={medication.frequency}
                  onChange={(e) => handleMedicationChange(medication.id, 'frequency', e.target.value)}
                  placeholder={t('misc.ps_med_frequency_ph')}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_duration')}</label>
                    <Input
                  type="text"
                  aria-label={`Medication ${index + 1} duration`}
                  value={medication.duration}
                  onChange={(e) => handleMedicationChange(medication.id, 'duration', e.target.value)}
                  placeholder={t('misc.ps_med_duration_ph')}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_quantity')}</label>
                    <Input
                  type="number"
                  aria-label={`Medication ${index + 1} quantity`}
                  value={medication.quantity}
                  onChange={(e) => handleMedicationChange(medication.id, 'quantity', parseInt(e.target.value) || 1)}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                  
                  <div className="md:col-span-2 lg:col-span-1">
                    <label className="block text-sm font-medium mb-1">{t('misc.ps_med_special')}</label>
                    <Input
                  type="text"
                  aria-label={`Medication ${index + 1} special instructions`}
                  value={medication.instructions}
                  onChange={(e) => handleMedicationChange(medication.id, 'instructions', e.target.value)}
                  placeholder={t('misc.ps_med_special_ph')}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={!canEdit} />
                
                  </div>
                </div>
              </div>
          )}
          </div>
        }
      </Card>

      {/* Общие инструкции */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">{t('misc.ps_general_instructions')}</h3>
        <textarea
          aria-label="Prescription general instructions"
          value={prescription.instructions}
          onChange={(e) => handleFieldChange('instructions', e.target.value)}
          placeholder={t('misc.ps_general_instructions_ph')}
          className="w-full h-24 p-3 border border-gray-300 rounded-lg resize-none"
          disabled={!canEdit} />
        
      </Card>

      {/* Заметки врача */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">{t('misc.ps_doctor_notes')}</h3>
        <textarea
          aria-label="Prescription doctor notes"
          value={prescription.doctorNotes}
          onChange={(e) => handleFieldChange('doctorNotes', e.target.value)}
          placeholder={t('misc.ps_doctor_notes_ph')}
          className="w-full h-20 p-3 border border-gray-300 rounded-lg resize-none"
          disabled={!canEdit} />
        
      </Card>

      {/* Предпросмотр рецепта */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">{t('misc.ps_preview')}</h3>

        <div className="bg-white border-2 border-dashed border-gray-300 p-6 rounded-lg">
          <div className="text-center space-y-4">
            <div className="font-bold text-lg">{t('misc.ps_rx_title')}</div>
            <div className="text-sm">
              <div>{t('misc.ps_patient')}: {appointment?.patient_name}</div>
              <div>{t('misc.ps_date')}: {new Date().toLocaleDateString('ru-RU')}</div>
              <div>{t('misc.ps_doctor')}: {appointment?.specialist}</div>
            </div>

            <div className="border-t pt-4">
              {prescription.medications.map((med, index) =>
              <div key={med.id} className="text-left mb-3">
                  <div className="font-medium">
                    {index + 1}. {med.name} {med.dosage}
                  </div>
                  <div className="text-sm text-gray-600">
                    {med.frequency} • {med.duration} • {med.quantity} {t('misc.ps_pcs')}.
                  </div>
                  {med.instructions &&
                <div className="text-sm text-gray-500 italic">
                      {med.instructions}
                    </div>
                }
                </div>
              )}
            </div>

            {prescription.instructions &&
            <div className="border-t pt-4 text-sm">
                <div className="font-medium">{t('misc.ps_instructions_label')}</div>
                <div>{prescription.instructions}</div>
              </div>
            }

            <div className="border-t pt-4 text-xs text-gray-500">
              {t('misc.ps_doctor_signature')}
            </div>
          </div>
        </div>
      </Card>

      {/* Кнопки действий */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {hasUnsavedChanges && t('misc.ps_unsaved_changes')}
          </div>

          <div className="flex gap-3">
            <Button
              onClick={handleSavePrescription}
              disabled={!canEdit || isSaving || prescription.medications.length === 0}>

              <Save className="w-4 h-4 mr-2" />
              {isSaving ? t('misc.ps_saving') : t('misc.ps_save')}
            </Button>

            <Button
              variant="outline"
              onClick={handlePrintPrescription}
              disabled={prescription.isDraft || typeof onPrint !== 'function'}>

              <Printer className="w-4 h-4 mr-2" />
              {t('misc.ps_print')}
            </Button>
          </div>
        </div>
      </Card>
    </div>);

};

PrescriptionSystem.propTypes = {
  appointment: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    doctor_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    status: PropTypes.string,
    patient_name: PropTypes.string,
    specialist: PropTypes.string,
    prescription: PropTypes.shape({
      medications: PropTypes.arrayOf(PropTypes.object),
      instructions: PropTypes.string,
      doctorNotes: PropTypes.string,
      isDraft: PropTypes.bool,
      printedAt: PropTypes.string
    })
  }),
  emr: PropTypes.shape({
    isDraft: PropTypes.bool
  }),
  prescription: PropTypes.shape({
    medications: PropTypes.arrayOf(PropTypes.object),
    instructions: PropTypes.string,
    doctorNotes: PropTypes.string,
    isDraft: PropTypes.bool,
    printedAt: PropTypes.string
  }),
  canCreatePrescription: PropTypes.bool,
  onSave: PropTypes.func,
  onPrint: PropTypes.func
};

export default PrescriptionSystem;
