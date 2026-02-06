/**
 * RecommendationsSection - Рекомендации с "Мой опыт"
 * 
 * Phase 4.1: Text section with personalized templates
 */

import React, { useState, useCallback } from 'react';
import { History } from 'lucide-react';
import EMRSection from './EMRSection';
import EMRTextField from './EMRTextField';
import { DoctorTemplatesPanel, DoctorTemplatesButton } from '../DoctorTemplatesPanel';
import { useDoctorSectionTemplates } from '../../../hooks/useDoctorSectionTemplates';

/**
 * RecommendationsSection Component
 * 
 * @param {Object} props
 * @param {string} props.value - Current value
 * @param {Function} props.onChange - Change handler
 * @param {boolean} props.disabled - Read-only mode
 * @param {boolean} props.defaultOpen - Start expanded
 * @param {string} props.icd10Code - ICD-10 code for personalized templates
 */
export function RecommendationsSection({
    value = '',
    onChange,
    disabled = false,
    defaultOpen = true,
    icd10Code = '',
}) {
    const [showMyExperience, setShowMyExperience] = useState(false);

    // Get templates from hook
    const {
        templates,
        loading: templatesLoading,
        hasTemplates
    } = useDoctorSectionTemplates({
        section: 'recommendations',
        icd10Code: icd10Code || null,
    });

    // Handle template apply - append to current value
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
            title="Рекомендации"
            icon="💡"
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
                placeholder="Рекомендации пациенту, режим, диета..."
                multiline
                rows={2}
                disabled={disabled}
                id="emr-recommendations"
            />

            {/* My Experience Panel */}
            <DoctorTemplatesPanel
                section="recommendations"
                icd10Code={icd10Code}
                onApply={handleApplyTemplate}
                onClose={() => setShowMyExperience(false)}
                isOpen={showMyExperience}
            />
        </EMRSection>
    );
}

export default RecommendationsSection;
