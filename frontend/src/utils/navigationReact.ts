/**
 * React-часть единой navigation policy.
 *
 * Использование в React-компонентах:
 *   import { useNavigateSafely } from '../utils/navigationReact';
 *   const navigateSafely = useNavigateSafely();
 *   navigateSafely('/patients/123');
 *
 * Преимущества над raw useNavigate():
 *   - логирует навигацию (debug-уровень)
 *   - не делает ничего, если уже на целевом маршруте
 *   - supports `replace` и `state`
 *
 * Этот модуль отделён от `utils/navigation.js`, потому что последний
 * используется в не-React контексте (api/client.js) и не должен тащить
 * зависимость от react-router-dom.
 */

import { useNavigate } from 'react-router-dom';
import { isOnPath } from './navigation';

/**
 * @returns {(path: string, options?: { replace?: boolean, state?: unknown }) => void}
 */
export function useNavigateSafely(): (path: string, options?: { replace?: boolean; state?: unknown }) => void {
  const navigate = useNavigate();

  return (path: string, options: { replace?: boolean; state?: unknown } = {}) => {
    const { replace = false, state = null } = options;
    if (isOnPath(path)) {
      return;
    }
    navigate(path, { replace, state });
  };
}

export default useNavigateSafely;
