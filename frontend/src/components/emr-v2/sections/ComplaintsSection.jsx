/**
 * ComplaintsSection - Жалобы с "Мой опыт"
 * 
 * ❌ БЕЗ AI - жалобы = слова пациента
 * ✅ С "Мой опыт" (без привязки к ICD)
 * 
 * Rules:
 * - Receives data + setField from parent
 * - No internal state for EMR data
 */

import React, { useState, useCallback } from 'react';
import EMRSection from './EMRSection';
import ComplaintsField from '../../emr/ComplaintsField';
import { api } from '../../../api/client';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '../../../hooks/useDoctorSectionTemplates';

/**
 * ComplaintsSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current complaints value
 * @param {Function} props.onChange - Change handler (receives value)
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.required - Show required indicator
 * @param {boolean} props.defaultOpen - Start expanded
 */
export function ComplaintsSection({
    value = '',
    onChange,
    disabled = false,
    required = true,
    defaultOpen = true,
    doctorId,
    specialty = 'general',
}) {
    const [showMyExperience, setShowMyExperience] = useState(false);

    // Get section templates (NO icd10 for complaints)
    const {
        templates,
        loading: templatesLoading,
        hasTemplates
    } = useDoctorSectionTemplates({
        section: 'complaints',
        icd10Code: null, // No diagnosis binding for complaints
    });

    // 📜 Doctor History Request Handler (NOT AI!)
    // Returns phrases from doctor's past records
    const handleRequestHistory = useCallback(async (text) => {
        if (!doctorId || !text || text.length < 2) return [];

        try {
            // Fetch from doctor's personal phrase history
            const historyResponse = await api.post('/emr/phrase-suggest', {
                field: 'complaints',
                currentText: text,
                doctorId,
                specialty,
                maxSuggestions: 3
            });

            // Format for ComplaintsField with clear source marker
            const historyItems = (historyResponse.data?.suggestions || []).map(s => ({
                id: s.id,
                text: s.text,
                source: '📜 История'  // Clear visual marker
            }));

            return historyItems;

        } catch (e) {
            console.error('Failed to fetch complaints history:', e);
            return [];
        }
    }, [doctorId, specialty]);

    // Handle template apply
    const handleApplyTemplate = useCallback((text) => {
        if (!text) return;
        const current = value || '';
        const newValue = current.trim()
            ? `${current.trim()}, ${text}`
            : text;
        onChange?.(newValue);
    }, [value, onChange]);

    return (
        <EMRSection
            title="Жалобы"
            icon="📋"
            required={required}
            disabled={disabled}
            defaultOpen={defaultOpen}
            headerAction={
                <DoctorTemplatesButton
                    onClick={() => setShowMyExperience(true)}
                    disabled={disabled || templatesLoading}
                    hasTemplates={hasTemplates}
                    count={templates.length}
                />
            }
        >
            <ComplaintsField
                value={value}
                onChange={onChange}
                isEditable={!disabled}
                label=""
                onRequestAI={handleRequestHistory}  // Named "AI" in component, but is history
                aiEnabled={!!doctorId}
            />

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
                section="complaints"
                icd10Code={null}
                onApply={handleApplyTemplate}
                onClose={() => setShowMyExperience(false)}
                isOpen={showMyExperience}
            />
        </EMRSection>
    );
}

export default ComplaintsSection;
