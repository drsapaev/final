
/**
 * NotesSection - Примечания с "Мой опыт"
 * 
 * ❌ БЕЗ AI - свободное поле
 * ✅ С "Мой опыт" (без привязки к ICD)
 */

import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import EMRSection from './EMRSection';
import React from 'react';
import EMRTextField from './EMRTextField';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '../../../hooks/useDoctorSectionTemplates';
import { useTranslation } from '../../../i18n/useTranslation';

/**
 * NotesSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 */
interface NotesSectionProps {
  value?: string;
  onChange?: ((value: string) => void) | undefined;
  disabled?: boolean;
  defaultOpen?: boolean;
}


export function NotesSection({
    value = '',
    onChange,
    disabled = false,
    defaultOpen = false, // Notes usually collapsed by default
}: NotesSectionProps) {
    const [showMyExperience, setShowMyExperience] = useState(false);

    // Get section templates (NO icd10 for notes)
    const {
        templates,
        loading: templatesLoading,
        hasTemplates
    } = useDoctorSectionTemplates({
        section: 'recommendations', // Reuse recommendations type for notes
        icd10Code: null, // No diagnosis binding
    });

    // Handle template apply
    const handleApplyTemplate = useCallback((text) => {
        if (!text) return;
        const current = value || '';
        const newValue = current.trim()
            ? `${current.trim()}\n\n${text}`
            : text;
        onChange?.(newValue);
    }, [value, onChange]);

    return (
        <EMRSection
            title="Примечания"
            icon="📝"
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
            <EMRTextField
                value={value}
                onChange={onChange}
                placeholder="Дополнительные заметки врача..."
                multiline
                rows={2}
                disabled={disabled}
                id="emr-notes"
            />

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
                section="recommendations"
                icd10Code={null}
                onApply={handleApplyTemplate}
                onClose={() => setShowMyExperience(false)}
                isOpen={showMyExperience}
            />
        </EMRSection>
    );
}

export default NotesSection;

NotesSection.propTypes = {
    value: PropTypes.string,
    onChange: PropTypes.func,
    disabled: PropTypes.bool,
    defaultOpen: PropTypes.bool,
};
