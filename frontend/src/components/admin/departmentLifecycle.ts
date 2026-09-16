/**
 * RQ-13 UI-slice (S-11 browser, D-06 APPROVED 2026-09-15): SSOT for the
 * department lifecycle consequence texts and the delete-guard 409 parser.
 *
 * One contract, not two behaviors: the table switch, the bulk buttons and
 * the delete flows all render their operator-facing consequences from this
 * module. The backend already enforces the D-06 contract (RQ-13.a deacti-
 * vation hides linked profiles; reactivation restores only the 1:1 profile;
 * single delete returns 409 `department_has_queue_history` with live
 * impact — and bulk delete returns the same guard shape with per-department
 * rows). The UI's job is to tell the operator what will happen BEFORE it
 * happens, and to surface the server impact instead of a generic failure.
 *
 * Pure functions only — no React, no API client. `t` is the translation
 * function signature `(key, options?) => string`.
 */

export interface DepartmentDeleteBlockProfile {
  profile_key?: string;
  daily_queues?: number;
  entries_waiting?: number;
  entries_total?: number;
}

export interface DepartmentDeleteBlockRow {
  department_id?: number | string;
  name?: string;
  waiting_patients?: number;
  profiles?: DepartmentDeleteBlockProfile[];
}

export interface DepartmentDeleteBlockDetail {
  error?: string;
  message?: string;
  waiting_patients?: number;
  profiles?: DepartmentDeleteBlockProfile[];
  blocked?: DepartmentDeleteBlockRow[];
}

export interface DepartmentDeleteBlockInfo {
  /** Total waiting patients across all blocking profiles. */
  waiting: number;
  /** Number of departments named in the bulk blocked report (0 for single). */
  blockedCount: number;
  /** Profile keys that still own queue history (deduplicated, in order). */
  profileKeys: string[];
  /** Raw server message, if any (already localized server-side). */
  serverMessage: string | null;
}

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

const GUARD_ERROR = 'department_has_queue_history';

const _num = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) && value > 0 ? Math.floor(value) : 0;

const _profilesFrom = (value: unknown): DepartmentDeleteBlockProfile[] =>
  Array.isArray(value) ? (value as DepartmentDeleteBlockProfile[]) : [];

/**
 * Normalize the 409 `detail` payload of the department-delete guard.
 * Accepts both the single-delete shape (`profiles` at top level) and the
 * bulk shape (`blocked[]` rows with per-department `profiles`). Returns
 * null for anything that is not this guard's payload — callers fall back
 * to the generic error message.
 */
export function parseDepartmentDeleteBlock(detail: unknown): DepartmentDeleteBlockInfo | null {
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  const d = detail as DepartmentDeleteBlockDetail;
  if (d.error !== GUARD_ERROR) return null;

  const topProfiles = _profilesFrom(d.profiles);
  const blockedRows = Array.isArray(d.blocked) ? d.blocked : [];
  const hasBlockedShape =
    blockedRows.length > 0 &&
    blockedRows.every((row) => !row || typeof row !== 'object' || Array.isArray(row.profiles));
  if (topProfiles.length === 0 && !hasBlockedShape) return null;

  const profileKeys: string[] = [];
  const collect = (profiles: DepartmentDeleteBlockProfile[]) => {
    profiles.forEach((p) => {
      const key = typeof p?.profile_key === 'string' ? p.profile_key : '';
      if (key && !profileKeys.includes(key)) profileKeys.push(key);
    });
  };
  let waiting = _num(d.waiting_patients);
  collect(topProfiles);
  let blockedCount = 0;
  if (hasBlockedShape) {
    blockedRows.forEach((row) => {
      blockedCount += 1;
      collect(_profilesFrom(row?.profiles));
    });
    if (waiting === 0) {
      // No server aggregate: prefer per-row aggregates, else the
      // per-profile entries_waiting sum (never both — no double count).
      waiting = blockedRows.reduce((acc: number, row) => {
        const rowAgg = _num(row?.waiting_patients);
        if (rowAgg > 0) return acc + rowAgg;
        return (
          acc +
          _profilesFrom(row?.profiles).reduce((a: number, p) => a + _num(p?.entries_waiting), 0)
        );
      }, 0);
    }
  } else if (waiting === 0) {
    waiting = topProfiles.reduce((acc: number, p) => acc + _num(p?.entries_waiting), 0);
  }

  return {
    waiting,
    blockedCount,
    profileKeys,
    serverMessage: typeof d.message === 'string' && d.message.trim() ? d.message : null,
  };
}

/**
 * Single delete: the server already blocks it; the panel explains the
 * impact and recommends the D-02-aligned alternative (archive/deactivate).
 */
export function formatDepartmentDeleteBlockMessage(
  t: TranslateFn,
  info: DepartmentDeleteBlockInfo,
  bulk: boolean,
): string {
  if (bulk && info.blockedCount > 0) {
    return t('admin2.dept_bulk_delete_blocked_toast', {
      count: info.blockedCount,
      waiting: info.waiting,
    });
  }
  return t('admin2.dept_delete_blocked_toast', { waiting: info.waiting });
}

/**
 * D-06 deactivation consequences — the three distinguishable actions
 * (S-11 различение «скрыть вкладку / закрыть новую запись / ожидающие
 * не исчезают»). Order is presentation-stable.
 */
export function describeDepartmentDeactivationConsequences(t: TranslateFn): string[] {
  return [
    t('admin2.dept_deactivate_conseq_new_entries'),
    t('admin2.dept_deactivate_conseq_hide_tab'),
    t('admin2.dept_deactivate_conseq_waiting_keep'),
  ];
}

/**
 * D-06/D-02 reactivation semantics: only the department's own 1:1 profile
 * comes back; independently archived profiles stay archived.
 */
export function describeDepartmentReactivationConsequences(t: TranslateFn): string[] {
  return [t('admin2.dept_reactivate_conseq_restore')];
}
