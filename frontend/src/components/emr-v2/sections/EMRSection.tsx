/**
 * EMRSection - Base wrapper for EMR sections
 * 
 * Rules (Phase 4):
 * - Section receives data + setField (from parent)
 * - Section does NOT know about API, versions, autosave
 * - Section is testable in isolation
 * - No new logic - just transfer from legacy EMR
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
interface EMRSectionProps {
  title?: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  defaultOpen?: boolean;
  badge?: string;
  headerAction?: React.ReactNode;
  className?: string;
  required?: boolean;
  disabled?: boolean;
  [key: string]: unknown;
}

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
}: EMRSectionProps) {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    // EMRCOLLAPSE-FE-001 (audit 3886, round 21): the collapsed body used to keep
    // its whole interactive subtree mounted, focusable and exposed to screen
    // readers (only grid-template-rows:0fr hid it visually). A stable body id +
    // aria-controls on the toggle plus `inert`/`aria-hidden` on the collapsed
    // body remove collapsed descendants from the tab order and the a11y tree
    // while keeping the element mounted so the CSS grid animation still runs.
    const bodyId = React.useId();

    return (
        <section className={`emr-section ${className} ${disabled ? 'emr-section--disabled' : ''}`}>
            <div className="emr-section__header-wrapper">
                {/* EMRREAD-FE-001 (audit 3886, round 21): the header toggle stays
                    clickable when the section is read-only — the CSS now scopes
                    pointer-events:none to the section BODY, so a signed/completed
                    EMR can still be expanded for review by mouse and touch. */}
                <button
                    type="button"
                    className={`emr-section__header ${isOpen ? 'emr-section__header--open' : ''}`}
                    onClick={() => setIsOpen(!isOpen)}
                    aria-expanded={isOpen}
                    aria-controls={bodyId}
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
                    // EMRORDER-FE-001 (audit 3886, round 19): this wrapper used
                    // to carry onClickCapture={stopPropagation} — a CAPTURE-phase
                    // stop kills the event before it ever reaches the action
                    // button, so every headerAction (e.g. «Заказать анализы» in
                    // LabResultsSection) was dead UI that could never fire its
                    // onClick. The shield was also unnecessary: the action is a
                    // SIBLING of the section-toggle <button>, so a click on the
                    // action can never dispatch through the toggle anyway. A
                    // plain wrapper keeps the actions alive and a11y-clean.
                    <div className="emr-section__header-action">
                        {headerAction}
                    </div>
                )}
            </div>

            {/* Animated Content Wrapper */}
            <div
                id={bodyId}
                className={`emr-section__body ${isOpen ? 'emr-section__body--open' : ''}`}
                inert={!isOpen}
                aria-hidden={!isOpen}
            >
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

