/**
 * Shared infrastructure for state machine transition validators.
 *
 * Per ADR-0017 + Track 3, each domain state machine defines:
 * 1. A status union type
 * 2. An ALLOWED_TRANSITIONS table (from → to[])
 * 3. isValid*Transition() — pure check
 * 4. apply*Transition() — runtime enforcer (dev-only warn on forbidden, prod no-op)
 *
 * This file provides the generic helpers that each domain module uses.
 */

/**
 * Check if a transition is allowed (including self-loops / idempotent transitions).
 */
export function isTransitionAllowed<S extends string>(
  table: Record<S, readonly S[]>,
  from: S,
  to: S,
): boolean {
  if (from === to) return true; // idempotent
  return table[from]?.includes(to) ?? false;
}

/**
 * Apply a transition. Returns the target status if allowed, or the original
 * status if forbidden (with dev-only console.warn).
 *
 * The `state` parameter is the full state object; the function returns a
 * new object with the updated status (immutable).
 */
export function applyTransition<S extends string, T extends { status: S }>(
  table: Record<S, readonly S[]>,
  state: T,
  next: S,
  machineName: string,
): T {
  if (!isTransitionAllowed(table, state.status, next)) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(
        `[${machineName}] forbidden transition: ${state.status} → ${next}`,
      );
    }
    return state; // no-op
  }
  return { ...state, status: next };
}

/**
 * Check if a status is terminal (no outgoing edges except self-loop).
 */
export function isTerminalStatus<S extends string>(
  table: Record<S, readonly S[]>,
  status: S,
): boolean {
  const outgoing = table[status]?.filter((s) => s !== status) ?? [];
  return outgoing.length === 0;
}

/**
 * Get all reachable statuses from a starting status (BFS).
 */
export function getReachableStatuses<S extends string>(
  table: Record<S, readonly S[]>,
  start: S,
): Set<S> {
  const visited = new Set<S>([start]);
  const queue: S[] = [start];
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const next of table[current] ?? []) {
      if (!visited.has(next)) {
        visited.add(next);
        queue.push(next);
      }
    }
  }
  return visited;
}

/**
 * Get all statuses defined in the table.
 */
export function getAllStatuses<S extends string>(table: Record<S, readonly S[]>): S[] {
  return Object.keys(table) as S[];
}
