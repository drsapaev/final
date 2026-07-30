/**
 * AsyncState<T> — discriminated union for async resource state.
 *
 * Replaces pairs of useState<T[]>([]) + useState<string | null>(null)
 * with a single useState<AsyncState<T>>({ status: 'idle' }).
 *
 * Usage:
 *   const [state, setState] = useState<AsyncState<Patient[]>>({ status: 'idle' });
 *
 *   // Loading
 *   setState({ status: 'loading' });
 *
 *   // Success
 *   const patients = await fetchPatients();
 *   setState({ status: 'success', data: patients });
 *
 *   // Error
 *   setState({ status: 'error', error: 'Failed to load patients' });
 *
 *   // Render
 *   if (state.status === 'loading') return <Spinner />;
 *   if (state.status === 'error') return <ErrorView error={state.error} />;
 *   if (state.status === 'success') return <PatientList patients={state.data} />;
 *   return null; // idle
 */

export type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };

// === Helper constructors ===

export const idleState = <T>(): AsyncState<T> => ({ status: 'idle' });
export const loadingState = <T>(): AsyncState<T> => ({ status: 'loading' });
export const successState = <T>(data: T): AsyncState<T> => ({ status: 'success', data });
export const errorState = <T>(error: string): AsyncState<T> => ({ status: 'error', error });

// === Type guards ===

export function isLoading<T>(state: AsyncState<T>): state is { status: 'loading' } {
  return state.status === 'loading';
}

export function isSuccess<T>(state: AsyncState<T>): state is { status: 'success'; data: T } {
  return state.status === 'success';
}

export function isError<T>(state: AsyncState<T>): state is { status: 'error'; error: string } {
  return state.status === 'error';
}

// === Data extractor ===

export function getData<T>(state: AsyncState<T>, fallback: T): T {
  return state.status === 'success' ? state.data : fallback;
}

export function getError<T>(state: AsyncState<T>): string | null {
  return state.status === 'error' ? state.error : null;
}
