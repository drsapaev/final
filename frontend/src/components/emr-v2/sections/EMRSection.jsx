/**
 * EMRSection - Base wrapper for EMR sections
 * 
 * Rules (Phase 4):
 * - Section receives data + setField (from parent)
 * - Section does NOT know about API, versions, autosave
 * - Section is testable in isolation
 * - No new logic - just transfer from SingleSheetEMR
 */

import React from 'react';
import './EMRSection.css';

/**
 * EMRSection Component - Collapsible section wrapper
 * 
 * @param {Object} props
 * @param {string} props.title - Section title
 * @param {string} props.icon - Emoji icon
 * @param {React.ReactNode} props.children - Section content
 * @param {boolean} props.defaultOpen - Start expanded (default: true)
 * @param {string} props.badge - Optional badge text
 * @param {React.ReactNode} props.headerAction - Optional action button in header
 * @param {string} props.className - Additional CSS class
 * @param {boolean} props.required - Show required indicator
 * @param {boolean} props.disabled - Section is disabled
 */
export function EMRSection({
    title,
    icon,
    children,
    defaultOpen = true,
    badge,
    headerAction,
    className = '',
    required = false,
    disabled = false,
}) {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    return (
        <section className={`emr-section ${className} ${disabled ? 'emr-section--disabled' : ''}`}>
            <div className="emr-section__header-wrapper">
                <button
                    type="button"
                    className={`emr-section__header ${isOpen ? 'emr-section__header--open' : ''}`}
                    onClick={() => setIsOpen(!isOpen)}
                    aria-expanded={isOpen}
                >
                    {icon && <span className="emr-section__icon">{icon}</span>}
                    <span className="emr-section__title">
                        {title}
                        {required && <span className="emr-section__required">*</span>}
                    </span>
                    {badge && <span className="emr-section__badge">{badge}</span>}
                    <span className={`emr-section__chevron ${isOpen ? 'emr-section__chevron--open' : ''}`}>▼</span>
                </button>
                {headerAction && (
                    <div className="emr-section__header-action" onClick={(e) => e.stopPropagation()}>
                        {headerAction}
                    </div>
                )}
            </div>

            {/* Animated Content Wrapper */}
            <div className={`emr-section__body ${isOpen ? 'emr-section__body--open' : ''}`}>
                <div className="emr-section__body-inner">
                    <div className="emr-section__content">
                        {children}
                    </div>
                </div>
            </div>
        </section>
    );
}

export default EMRSection;
