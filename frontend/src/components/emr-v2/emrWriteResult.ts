/**
 * Shared EMR write-outcome predicate.
 *
 * Extracted from EMRContainerV2 (audit 3886: persistEMRAndRefresh /
 * persistAndSignEMR consumed it privately) so the EMR leave guard
 * (useEMRLeaveGuard, RETRO-3971-04 residual remediation) can apply the
 * EXACT same success/rejection contract when deciding whether a
 * «Save and leave» transition actually persisted the clinical draft.
 * A local copy in the hook would drift from the container's contract;
 * one shared predicate keeps the two paths honest by construction.
 */

export function isRejectedEMRWrite(value: unknown): boolean {
    if (!value || typeof value !== 'object') return true;
    const result = value as Record<string, unknown>;
    return result.accessDenied === true ||
        result.conflict === true ||
        result.signed === true ||
        result.success === false ||
        result.status === 'error' ||
        (result.error !== undefined && result.error !== null);
}
