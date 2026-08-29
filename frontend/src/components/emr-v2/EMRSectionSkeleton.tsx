/**
 * EMRSectionSkeleton — initial-load skeleton stack for the EMR v2 section
 * layout (PR-UI-12 increment 3, plan §PR-UI-12 item 1:
 * "EMR sections — каждый раздел skeleton loading").
 *
 * Shown by EMRContainerV2 while the EMR snapshot is being fetched for the
 * FIRST time (`isLoading && !data`): each skeleton card mirrors one clinical
 * section's footprint (header bar + text lines), replacing the previous
 * empty-fields flash during the initial visit load.
 *
 * NOT shown on subsequent field refreshes (autosave/saving keeps the real
 * sections mounted) — skeleton is an initial-load state only.
 *
 * A11y:
 *   - The wrapper carries `role="status"` + `aria-live="polite"` +
 *     `aria-busy="true"` so screen readers announce the loading state once.
 *   - Every decorative skeleton block is `aria-hidden="true"`.
 *   - A visually-hidden text label is provided for assistive technology.
 *
 * Visual:
 *   - All styling lives in `EMRContainerV2.css` under `.emr-skeleton*`
 *     classes (canonical macos variables WITH fallbacks — ratchet-safe).
 */

import React from 'react';

export interface EMRSectionSkeletonProps {
  /** Number of section skeletons to render. Default: 6 (mirrors the default-open + collapsed section stack). */
  sections?: number;
  /** Accessible label announced by screen readers. */
  ariaLabel?: string;
}

const EMRSectionSkeleton = ({
  sections = 6,
  ariaLabel = 'Загрузка карты приёма…'
}: EMRSectionSkeletonProps): React.ReactElement => (
  <div className="emr-skeleton-stack" role="status" aria-live="polite" aria-busy="true" aria-label={ariaLabel}>
    {Array.from({ length: sections }, (_, index) => (
      <div key={index} className="emr-skeleton-section" aria-hidden="true">
        <div className="emr-skeleton-section__header">
          <span className="emr-skeleton-bone emr-skeleton-bone--icon" />
          <span className="emr-skeleton-bone emr-skeleton-bone--title" />
          <span className="emr-skeleton-bone emr-skeleton-bone--badge" />
        </div>
        <div className="emr-skeleton-section__body">
          <span className="emr-skeleton-bone emr-skeleton-bone--line" />
          <span className="emr-skeleton-bone emr-skeleton-bone--line" />
          <span className="emr-skeleton-bone emr-skeleton-bone--line emr-skeleton-bone--short" />
        </div>
      </div>
    ))}
  </div>
);

export default EMRSectionSkeleton;
