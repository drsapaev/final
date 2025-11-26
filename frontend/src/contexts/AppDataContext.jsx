import React, { createContext, useContext, useReducer, useCallback } from 'react';

/**
 * Контекст для управления глобальным состоянием приложения
 * Оптимизирует передачу данных между компонентами
 */

// Начальное состояние
const initialState = {
  // Пользователи и роли
  users: [],
  currentUser: null,
  
  // Пациенты
  patients: [],
  selectedPatient: null,
  
  // Записи и очереди
  appointments: [],
  queueData: null,
  
  // Медицинские данные
  emrData: null,
  labResults: [],
  
  // UI состояния
  loading: {
    users: false,
    patients: false,
    appointments: false,
    emr: false
  },
  
  errors: {
    users: null,
    patients: null,
    appointments: null,
    emr: null
  }
};

// Типы действий
const ActionTypes = {
  // Пользователи
  SET_USERS: 'SET_USERS',
  SET_CURRENT_USER: 'SET_CURRENT_USER',
  ADD_USER: 'ADD_USER',
  UPDATE_USER: 'UPDATE_USER',
  DELETE_USER: 'DELETE_USER',
  
  // Пациенты
  SET_PATIENTS: 'SET_PATIENTS',
  SET_SELECTED_PATIENT: 'SET_SELECTED_PATIENT',
  ADD_PATIENT: 'ADD_PATIENT',
  UPDATE_PATIENT: 'UPDATE_PATIENT',
  
  // Записи
  SET_APPOINTMENTS: 'SET_APPOINTMENTS',
  ADD_APPOINTMENT: 'ADD_APPOINTMENT',
  UPDATE_APPOINTMENT: 'UPDATE_APPOINTMENT',
  
  // Очередь
  SET_QUEUE_DATA: 'SET_QUEUE_DATA',
  UPDATE_QUEUE_ENTRY: 'UPDATE_QUEUE_ENTRY',
  
  // EMR
  SET_EMR_DATA: 'SET_EMR_DATA',
  UPDATE_EMR_FIELD: 'UPDATE_EMR_FIELD',
  
  // Лабораторные результаты
  SET_LAB_RESULTS: 'SET_LAB_RESULTS',
  ADD_LAB_RESULT: 'ADD_LAB_RESULT',
  
  // Состояния загрузки
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR'
};

// Reducer для управления состоянием
function appDataReducer(state, action) {
  switch (action.type) {
    // Пользователи
    case ActionTypes.SET_USERS:
      return {
        ...state,
        users: action.payload,
        loading: { ...state.loading, users: false },
        errors: { ...state.errors, users: null }
      };
      
    case ActionTypes.SET_CURRENT_USER:
      return {
        ...state,
        currentUser: action.payload
      };
      
    case ActionTypes.ADD_USER:
      return {
        ...state,
        users: [...state.users, action.payload]
      };
      
    case ActionTypes.UPDATE_USER:
      return {
        ...state,
        users: state.users.map(user => 
          user.id === action.payload.id ? { ...user, ...action.payload } : user
        )
      };
      
    case ActionTypes.DELETE_USER:
      return {
        ...state,
        users: state.users.filter(user => user.id !== action.payload)
      };
    
    // Пациенты
    case ActionTypes.SET_PATIENTS:
      return {
        ...state,
        patients: action.payload,
        loading: { ...state.loading, patients: false },
        errors: { ...state.errors, patients: null }
      };
      
    case ActionTypes.SET_SELECTED_PATIENT:
      return {
        ...state,
        selectedPatient: action.payload
      };
      
    case ActionTypes.ADD_PATIENT:
      return {
        ...state,
        patients: [...state.patients, action.payload]
      };
      
    case ActionTypes.UPDATE_PATIENT:
      return {
        ...state,
        patients: state.patients.map(patient => 
          patient.id === action.payload.id ? { ...patient, ...action.payload } : patient
        ),
        selectedPatient: state.selectedPatient?.id === action.payload.id 
          ? { ...state.selectedPatient, ...action.payload } 
          : state.selectedPatient
      };
    
    // Записи
    case ActionTypes.SET_APPOINTMENTS:
      return {
        ...state,
        appointments: action.payload,
        loading: { ...state.loading, appointments: false },
        errors: { ...state.errors, appointments: null }
      };
      
    case ActionTypes.ADD_APPOINTMENT:
      return {
        ...state,
        appointments: [...state.appointments, action.payload]
      };
      
    case ActionTypes.UPDATE_APPOINTMENT:
      return {
        ...state,
        appointments: state.appointments.map(appointment => 
          appointment.id === action.payload.id ? { ...appointment, ...action.payload } : appointment
        )
      };
    
    // Очередь
    case ActionTypes.SET_QUEUE_DATA:
      return {
        ...state,
        queueData: action.payload
      };
      
    case ActionTypes.UPDATE_QUEUE_ENTRY:
      return {
        ...state,
        queueData: state.queueData ? {
          ...state.queueData,
          entries: state.queueData.entries.map(entry =>
            entry.id === action.payload.id ? { ...entry, ...action.payload } : entry
          )
        } : null
      };
    
    // EMR
    case ActionTypes.SET_EMR_DATA:
      return {
        ...state,
        emrData: action.payload,
        loading: { ...state.loading, emr: false },
        errors: { ...state.errors, emr: null }
      };
      
    case ActionTypes.UPDATE_EMR_FIELD:
      return {
        ...state,
        emrData: state.emrData ? {
          ...state.emrData,
          [action.payload.field]: action.payload.value
        } : null
      };
    
    // Лабораторные результаты
    case ActionTypes.SET_LAB_RESULTS:
      return {
        ...state,
        labResults: action.payload
      };
      
    case ActionTypes.ADD_LAB_RESULT:
      return {
        ...state,
        labResults: [...state.labResults, action.payload]
      };
    
    // Состояния загрузки и ошибок
    case ActionTypes.SET_LOADING:
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.payload.key]: action.payload.value
        }
      };
      
    case ActionTypes.SET_ERROR:
      return {
        ...state,
        errors: {
          ...state.errors,
          [action.payload.key]: action.payload.error
        },
        loading: {
          ...state.loading,
          [action.payload.key]: false
        }
      };
      
    case ActionTypes.CLEAR_ERROR:
      return {
        ...state,
        errors: {
          ...state.errors,
          [action.payload]: null
        }
      };
    
    default:
      return state;
  }
}

// Создаем контекст
const AppDataContext = createContext();

// Провайдер контекста
export const AppDataProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appDataReducer, initialState);

  // Action creators
  const actions = {
    // Пользователи
    setUsers: useCallback((users) => {
      dispatch({ type: ActionTypes.SET_USERS, payload: users });
    }, []),
    
    setCurrentUser: useCallback((user) => {
      dispatch({ type: ActionTypes.SET_CURRENT_USER, payload: user });
    }, []),
    
    addUser: useCallback((user) => {
      dispatch({ type: ActionTypes.ADD_USER, payload: user });
    }, []),
    
    updateUser: useCallback((user) => {
      dispatch({ type: ActionTypes.UPDATE_USER, payload: user });
    }, []),
    
    deleteUser: useCallback((userId) => {
      dispatch({ type: ActionTypes.DELETE_USER, payload: userId });
    }, []),

    // Пациенты
    setPatients: useCallback((patients) => {
      dispatch({ type: ActionTypes.SET_PATIENTS, payload: patients });
    }, []),
    
    setSelectedPatient: useCallback((patient) => {
      dispatch({ type: ActionTypes.SET_SELECTED_PATIENT, payload: patient });
    }, []),
    
    addPatient: useCallback((patient) => {
      dispatch({ type: ActionTypes.ADD_PATIENT, payload: patient });
    }, []),
    
    updatePatient: useCallback((patient) => {
      dispatch({ type: ActionTypes.UPDATE_PATIENT, payload: patient });
    }, []),

    // Записи
    setAppointments: useCallback((appointments) => {
      dispatch({ type: ActionTypes.SET_APPOINTMENTS, payload: appointments });
    }, []),
    
    addAppointment: useCallback((appointment) => {
      dispatch({ type: ActionTypes.ADD_APPOINTMENT, payload: appointment });
    }, []),
    
    updateAppointment: useCallback((appointment) => {
      dispatch({ type: ActionTypes.UPDATE_APPOINTMENT, payload: appointment });
    }, []),

    // Очередь
    setQueueData: useCallback((queueData) => {
      dispatch({ type: ActionTypes.SET_QUEUE_DATA, payload: queueData });
    }, []),
    
    updateQueueEntry: useCallback((entry) => {
      dispatch({ type: ActionTypes.UPDATE_QUEUE_ENTRY, payload: entry });
    }, []),

    // EMR
    setEMRData: useCallback((emrData) => {
      dispatch({ type: ActionTypes.SET_EMR_DATA, payload: emrData });
    }, []),
    
    updateEMRField: useCallback((field, value) => {
      dispatch({ type: ActionTypes.UPDATE_EMR_FIELD, payload: { field, value } });
    }, []),

    // Лабораторные результаты
    setLabResults: useCallback((results) => {
      dispatch({ type: ActionTypes.SET_LAB_RESULTS, payload: results });
    }, []),
    
    addLabResult: useCallback((result) => {
      dispatch({ type: ActionTypes.ADD_LAB_RESULT, payload: result });
    }, []),

    // Утилиты
    setLoading: useCallback((key, value) => {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { key, value } });
    }, []),
    
    setError: useCallback((key, error) => {
      dispatch({ type: ActionTypes.SET_ERROR, payload: { key, error } });
    }, []),
    
    clearError: useCallback((key) => {
      dispatch({ type: ActionTypes.CLEAR_ERROR, payload: key });
    }, [])
  };

  const value = {
    ...state,
    actions
  };

  return (
    <AppDataContext.Provider value={value}>
      {children}
    </AppDataContext.Provider>
  );
};

// Хук для использования контекста
export const useAppData = () => {
  const context = useContext(AppDataContext);
  if (!context) {
    throw new Error('useAppData must be used within an AppDataProvider');
  }
  return context;
};

// Селекторы для оптимизации производительности
export const useAppDataSelector = (selector) => {
  const context = useAppData();
  return selector(context);
};

export default AppDataContext;
