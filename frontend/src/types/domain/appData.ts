/**
 * Domain types for the AppData context.
 *
 * These are intentionally permissive — each entity uses an index signature
 * for backend-driven dynamic fields, with canonical fields typed explicitly.
 * As the strict-mode migration progresses, these can be tightened.
 */

export interface AppUser {
  id: string | number;
  name?: string;
  full_name?: string;
  email?: string;
  role?: string;
  [key: string]: unknown;
}

export interface AppPatient {
  id: string | number;
  name?: string;
  full_name?: string;
  phone?: string;
  [key: string]: unknown;
}

export interface AppAppointment {
  id: string | number;
  patient_id?: string | number;
  doctor_id?: string | number;
  status?: string;
  [key: string]: unknown;
}

export interface AppQueueEntry {
  id: string | number;
  status?: string;
  [key: string]: unknown;
}

export interface AppQueueData {
  entries: AppQueueEntry[];
  is_open?: boolean;
  [key: string]: unknown;
}

export interface AppEMRData {
  [key: string]: unknown;
}

export interface AppLabResult {
  id?: string | number;
  [key: string]: unknown;
}

export interface AppLoadingState {
  users: boolean;
  patients: boolean;
  appointments: boolean;
  emr: boolean;
  [key: string]: boolean;
}

export interface AppErrorsState {
  users: string | null;
  patients: string | null;
  appointments: string | null;
  emr: string | null;
  [key: string]: string | null;
}

export interface AppDataState {
  users: AppUser[];
  currentUser: AppUser | null;
  patients: AppPatient[];
  selectedPatient: AppPatient | null;
  appointments: AppAppointment[];
  queueData: AppQueueData | null;
  emrData: AppEMRData | null;
  labResults: AppLabResult[];
  loading: AppLoadingState;
  errors: AppErrorsState;
}

export type AppDataAction =
  | { type: 'SET_USERS'; payload: AppUser[] }
  | { type: 'SET_CURRENT_USER'; payload: AppUser | null }
  | { type: 'ADD_USER'; payload: AppUser }
  | { type: 'UPDATE_USER'; payload: AppUser }
  | { type: 'DELETE_USER'; payload: string | number }
  | { type: 'SET_PATIENTS'; payload: AppPatient[] }
  | { type: 'SET_SELECTED_PATIENT'; payload: AppPatient | null }
  | { type: 'ADD_PATIENT'; payload: AppPatient }
  | { type: 'UPDATE_PATIENT'; payload: AppPatient }
  | { type: 'SET_APPOINTMENTS'; payload: AppAppointment[] }
  | { type: 'ADD_APPOINTMENT'; payload: AppAppointment }
  | { type: 'UPDATE_APPOINTMENT'; payload: AppAppointment }
  | { type: 'SET_QUEUE_DATA'; payload: AppQueueData | null }
  | { type: 'UPDATE_QUEUE_ENTRY'; payload: AppQueueEntry }
  | { type: 'SET_EMR_DATA'; payload: AppEMRData | null }
  | { type: 'UPDATE_EMR_FIELD'; payload: { field: string; value: unknown } }
  | { type: 'SET_LAB_RESULTS'; payload: AppLabResult[] }
  | { type: 'ADD_LAB_RESULT'; payload: AppLabResult }
  | { type: 'SET_LOADING'; payload: { key: string; value: boolean } }
  | { type: 'SET_ERROR'; payload: { key: string; error: string | null } }
  | { type: 'CLEAR_ERROR'; payload: string };

export interface AppDataContextValue extends AppDataState {
  actions: {
    setUsers: (users: AppUser[]) => void;
    setCurrentUser: (user: AppUser | null) => void;
    addUser: (user: AppUser) => void;
    updateUser: (user: AppUser) => void;
    deleteUser: (userId: string | number) => void;
    setPatients: (patients: AppPatient[]) => void;
    setSelectedPatient: (patient: AppPatient | null) => void;
    addPatient: (patient: AppPatient) => void;
    updatePatient: (patient: AppPatient) => void;
    setAppointments: (appointments: AppAppointment[]) => void;
    addAppointment: (appointment: AppAppointment) => void;
    updateAppointment: (appointment: AppAppointment) => void;
    setQueueData: (queueData: AppQueueData | null) => void;
    updateQueueEntry: (entry: AppQueueEntry) => void;
    setEMRData: (emrData: AppEMRData | null) => void;
    updateEMRField: (field: string, value: unknown) => void;
    setLabResults: (results: AppLabResult[]) => void;
    addLabResult: (result: AppLabResult) => void;
    setLoading: (key: string, value: boolean) => void;
    setError: (key: string, error: string | null) => void;
    clearError: (key: string) => void;
  };
}
