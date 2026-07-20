// src/types/axios-silent.d.ts
//
// Local module augmentation that adds the `silent` flag to AxiosRequestConfig.
// Used by apiClient wrapper to suppress error notifications for expected
// non-2xx responses (e.g., 404 when checking optional resources).

import 'axios';

declare module 'axios' {
  export interface AxiosRequestConfig {
    silent?: boolean;
  }
}
