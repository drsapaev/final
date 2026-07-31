/**
 * useServicesApi — hook wrapper for the services API module.
 *
 * Per ADR-0015, components must NOT import from `api/services` directly.
 * This hook is the sanctioned entry point for:
 *   - servicesService (service catalog CRUD)
 *   - notificationsService (notification preferences CRUD)
 *   - clearNotificationQueryCache (cache invalidation utility)
 */

import {
  servicesService,
  notificationsService,
  clearNotificationQueryCache,
} from '../api/services';

export type ServicesService = typeof servicesService;
export type NotificationsService = typeof notificationsService;

export interface UseServicesApiReturn {
  servicesService: ServicesService;
  notificationsService: NotificationsService;
  clearNotificationQueryCache: typeof clearNotificationQueryCache;
}

export function useServicesApi(): UseServicesApiReturn {
  return {
    servicesService,
    notificationsService,
    clearNotificationQueryCache,
  };
}

export default useServicesApi;
