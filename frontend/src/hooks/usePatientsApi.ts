/**
 * usePatientsApi — hook wrapper for the patients API module.
 *
 * Per ADR-0015, components must NOT import from `api/patients` directly.
 * This hook is the sanctioned entry point for:
 *   - getPatient / createPatient / updatePatient
 *   - searchPatients / searchPatientsByPhone
 *   - checkAuthProbe / createRegistrarCart / findPatientByPhoneVariants
 */

import {
  getPatient,
  createPatient,
  updatePatient,
  searchPatients,
  searchPatientsByPhone,
  checkAuthProbe,
  createRegistrarCart,
  findPatientByPhoneVariants,
} from '../api/patients';

export interface UsePatientsApiReturn {
  getPatient: typeof getPatient;
  createPatient: typeof createPatient;
  updatePatient: typeof updatePatient;
  searchPatients: typeof searchPatients;
  searchPatientsByPhone: typeof searchPatientsByPhone;
  checkAuthProbe: typeof checkAuthProbe;
  createRegistrarCart: typeof createRegistrarCart;
  findPatientByPhoneVariants: typeof findPatientByPhoneVariants;
}

export function usePatientsApi(): UsePatientsApiReturn {
  return {
    getPatient,
    createPatient,
    updatePatient,
    searchPatients,
    searchPatientsByPhone,
    checkAuthProbe,
    createRegistrarCart,
    findPatientByPhoneVariants,
  };
}

export default usePatientsApi;
