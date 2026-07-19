
import React from 'react';
import { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import EMRSectionRaw from './EMRSection';
import EMRTextFieldRaw from './EMRTextField';
import VitalsWidget from './VitalsWidget';
import { DoctorTemplatesPanel as DTPRaw, DoctorTemplatesButton as DTBRaw } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '../../../hooks/useDoctorSectionTemplates';
import { useTranslation } from '../../../i18n/useTranslation';

const EMRSection = EMRSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;
const EMRTextField = EMRTextFieldRaw as unknown as React.ComponentType<Record<string, unknown>>;
const DoctorTemplatesPanel = DTPRaw as unknown as React.ComponentType<Record<string, unknown>>;
const DoctorTemplatesButton = DTBRaw as unknown as React.ComponentType<Record<string, unknown>>;

/**
 * AnamnesisVitaeSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 */
export function AnamnesisVitaeSection({
    value = '',
    onChange,
    disabled = false,
    defaultOpen = true,
    vitals = {},
    onVitalsChange
}) {
    const [showMyExperience, setShowMyExperience] = useState(false);

    // Get section templates (NO icd10 for anamnesis_vitae)
    const {
        templates,
        loading: templatesLoading,
        hasTemplates
    } = useDoctorSectionTemplates({
        section: 'anamnesis', // Uses same table, different content
        icd10Code: null, // No diagnosis binding for life history
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
            title="Анамнез жизни и параметры"
            icon="👤"
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
            {/* Vitals Widget */}
            <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
                <h4 style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-2)' }}>
                    Витальные показатели
                </h4>
                <VitalsWidget
                    vitals={vitals}
                    onChange={onVitalsChange}
                    disabled={disabled}
                />
            </div>

            <EMRTextField
                value={value}
                onChange={onChange}
                placeholder="Хронические заболевания, аллергии, наследственность..."
                multiline
                rows={3}
                disabled={disabled}
                id="emr-anamnesis-vitae"
            />

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
                section="anamnesis"
                icd10Code={null}
                onApply={handleApplyTemplate}
                onClose={() => setShowMyExperience(false)}
                isOpen={showMyExperience}
            />
        </EMRSection>
    );
}

export default AnamnesisVitaeSection;

AnamnesisVitaeSection.propTypes = {
    value: PropTypes.string,
    onChange: PropTypes.func,
    disabled: PropTypes.bool,
    defaultOpen: PropTypes.bool,
    vitals: PropTypes.object,
    onVitalsChange: PropTypes.func,
};
