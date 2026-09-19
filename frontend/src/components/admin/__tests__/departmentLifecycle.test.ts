/**
 * RQ-13 UI-slice (S-11): pure parser for the department-delete 409 guard
 * payload. The single-delete endpoint (RQ-13.a) returns
 * `{error, message, waiting_patients, profiles[]}`; the bulk-delete guard
 * parity returns `{error, message, waiting_patients, blocked[]}` where
 * each row carries per-department profiles. Both shapes must normalize,
 * anything else must return null (then the UI falls back to the generic
 * error message — no crash on foreign payloads).
 */
import { describe, expect, it } from 'vitest';

import {
  describeDepartmentDeactivationConsequences,
  describeDepartmentReactivationConsequences,
  formatDepartmentDeleteBlockMessage,
  parseDepartmentDeleteBlock,
} from '../departmentLifecycle';

const t = (key: string, opts?: Record<string, unknown>) => {
  const table: Record<string, string> = {
    'admin2.dept_delete_blocked_toast':
      'Удаление заблокировано: ожидающих — {waiting}. Отключите отделение вместо удаления.',
    'admin2.dept_bulk_delete_blocked_toast':
      'Массовое удаление отменено: отделений с историей — {count}, ожидающих — {waiting}.',
    'admin2.dept_deactivate_conseq_new_entries': 'закрыть новую запись',
    'admin2.dept_deactivate_conseq_hide_tab': 'скрыть вкладку',
    'admin2.dept_deactivate_conseq_waiting_keep': 'ожидающие не исчезают',
    'admin2.dept_reactivate_conseq_restore': 'заархивированные вкладки не включаются',
  };
  let out = table[key] ?? key;
  if (opts) {
    for (const [k, v] of Object.entries(opts)) {
      out = out.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    }
  }
  return out;
};

describe('parseDepartmentDeleteBlock (RQ-13 UI)', () => {
  it('normalizes the single-delete 409 shape (profiles at top level)', () => {
    const parsed = parseDepartmentDeleteBlock({
      error: 'department_has_queue_history',
      message: 'Нельзя удалить отделение',
      waiting_patients: 3,
      profiles: [{ profile_key: 'cardiology', daily_queues: 1, entries_waiting: 3, entries_total: 5 }],
    });
    expect(parsed).not.toBeNull();
    expect(parsed?.waiting).toBe(3);
    expect(parsed?.profileKeys).toEqual(['cardiology']);
    expect(parsed?.blockedCount).toBe(0);
  });

  it('normalizes the bulk-delete 409 shape (blocked rows)', () => {
    const parsed = parseDepartmentDeleteBlock({
      error: 'department_has_queue_history',
      waiting_patients: 7,
      blocked: [
        {
          department_id: 1,
          name: 'Кардиология',
          waiting_patients: 7,
          profiles: [
            { profile_key: 'cardiology', entries_waiting: 4 },
            { profile_key: 'ekg', entries_waiting: 3 },
          ],
        },
      ],
    });
    expect(parsed).not.toBeNull();
    expect(parsed?.waiting).toBe(7);
    expect(parsed?.blockedCount).toBe(1);
    expect(parsed?.profileKeys).toEqual(['cardiology', 'ekg']);
  });

  it('returns null for non-guard payloads and garbage', () => {
    expect(parseDepartmentDeleteBlock(null)).toBeNull();
    expect(parseDepartmentDeleteBlock(undefined)).toBeNull();
    expect(parseDepartmentDeleteBlock('oops')).toBeNull();
    expect(parseDepartmentDeleteBlock({ error: 'something_else' })).toBeNull();
    expect(parseDepartmentDeleteBlock({ error: 'department_has_queue_history', profiles: 'nope' })).toBeNull();
  });

  it('formats user-facing messages with waiting counts and the deactivate advice', () => {
    const parsed = parseDepartmentDeleteBlock({
      error: 'department_has_queue_history',
      waiting_patients: 3,
      profiles: [{ profile_key: 'cardiology', entries_waiting: 3 }],
    });
    expect(parsed).not.toBeNull();
    const msg = formatDepartmentDeleteBlockMessage(t, parsed!, false);
    expect(msg).toContain('3');
    expect(msg).toMatch(/Отключите отделение вместо удаления/i);

    const bulk = parseDepartmentDeleteBlock({
      error: 'department_has_queue_history',
      waiting_patients: 7,
      blocked: [{ department_id: 1, waiting_patients: 7, profiles: [{ profile_key: 'ekg', entries_waiting: 7 }] }],
    });
    expect(bulk).not.toBeNull();
    const bulkMsg = formatDepartmentDeleteBlockMessage(t, bulk!, true);
    expect(bulkMsg).toContain('1');
    expect(bulkMsg).toContain('7');
  });

  it('returns the three distinguishable deactivation consequences and the 1:1 restore note', () => {
    const bullets = describeDepartmentDeactivationConsequences(t);
    expect(bullets).toHaveLength(3);
    expect(bullets[0]).toMatch(/закрыть новую запись/i);
    expect(bullets[1]).toMatch(/скрыть вкладку/i);
    expect(bullets[2]).toMatch(/ожидающие не исчезают/i);
    const restore = describeDepartmentReactivationConsequences(t);
    expect(restore[0]).toMatch(/заархивированные вкладки не включаются/i);
  });
});
