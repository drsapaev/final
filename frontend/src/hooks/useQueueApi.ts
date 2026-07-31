/**
 * useQueueApi — hook wrapper for the queue API module.
 *
 * Per ADR-0015, components must NOT import from `api/queue` directly.
 * This hook is the sanctioned entry point for:
 *   - fetchAvailableSpecialists
 *   - applyRegistrarEditDelta / createQueueEntriesBatch / updateOnlineQueueEntry
 *   - other queue mutations
 *
 * Components should call:
 *   const queueApi = useQueueApi();
 *   const specialists = await queueApi.fetchAvailableSpecialists();
 */

import {
  fetchAvailableSpecialists,
  fetchPublicQueueProfiles,
  fetchQrTokenInfo,
  startQueueJoinSession,
  completeQueueJoinSession,
  applyRegistrarEditDelta,
  createQueueEntriesBatch,
  updateOnlineQueueEntry,
} from '../api/queue';

export interface UseQueueApiReturn {
  fetchAvailableSpecialists: typeof fetchAvailableSpecialists;
  fetchPublicQueueProfiles: typeof fetchPublicQueueProfiles;
  fetchQrTokenInfo: typeof fetchQrTokenInfo;
  startQueueJoinSession: typeof startQueueJoinSession;
  completeQueueJoinSession: typeof completeQueueJoinSession;
  applyRegistrarEditDelta: typeof applyRegistrarEditDelta;
  createQueueEntriesBatch: typeof createQueueEntriesBatch;
  updateOnlineQueueEntry: typeof updateOnlineQueueEntry;
}

export function useQueueApi(): UseQueueApiReturn {
  return {
    fetchAvailableSpecialists,
    fetchPublicQueueProfiles,
    fetchQrTokenInfo,
    startQueueJoinSession,
    completeQueueJoinSession,
    applyRegistrarEditDelta,
    createQueueEntriesBatch,
    updateOnlineQueueEntry,
  };
}

export default useQueueApi;
