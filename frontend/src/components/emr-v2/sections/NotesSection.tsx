
/**
 * NotesSection - Примечания с "Мой опыт"
 * 
 * ❌ БЕЗ AI - свободное поле
 * ✅ С "Мой опыт" (без привязки к ICD)
 */

import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import EMRSectionRaw from './EMRSection';
import React from 'react';
const EMRSection = EMRSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;
import EMRTextFieldRaw from './EMRTextField';
const EMRTextField = EMRTextFieldRaw as unknown as React.ComponentType<Record<string, unknown>>;
import { DoctorTemplatesPanel as DTPRaw, DoctorTemplatesButton as DTBRaw } from '../DoctorTemplatesPanel';
const DoctorTemplatesPanel = DTPRaw as unknown as React.ComponentType<Record<string, unknown>>;
const DoctorTemplatesButton = DTBRaw as unknown as React.ComponentType<Record<string, unknown>>;
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
export function NotesSection({
    value = '',
    onChange,
    disabled = false,
    defaultOpen = false, // Notes usually collapsed by default
}) {
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
