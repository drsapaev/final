/**
 * Axios-like API wrapper
 * Provides get, post, put, delete methods with automatic auth
 */
import logger from '../utils/logger';

const BASE_URL = 'http://localhost:8000/api/v1';

function getAuthToken() {
    return (
        localStorage.getItem('auth_token') ||
        localStorage.getItem('access_token') ||
        localStorage.getItem('token') ||
        ''
    );
}

async function request(method, path, options = {}) {
    const token = getAuthToken();

    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
    };

    // Build URL with params
    let url = `${BASE_URL}${path}`;
    if (options.params) {
        const searchParams = new URLSearchParams();
        Object.entries(options.params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                searchParams.append(key, value);
            }
        });
        const queryString = searchParams.toString();
        if (queryString) {
            url += `?${queryString}`;
        }
    }

    logger.log(`[api] ${method} ${path}`, { hasToken: !!token });

    const fetchOptions = {
        method,
        headers,
    };

    if (options.body || (options.data && method !== 'GET')) {
        fetchOptions.body = JSON.stringify(options.body || options.data);
    }

    const res = await fetch(url, fetchOptions);

    if (!res.ok) {
        let detail = 'Request failed';
        try {
            const errorData = await res.json();
            detail = errorData.detail || errorData.message || detail;
        } catch (_) {
            detail = `HTTP ${res.status}: ${res.statusText}`;
        }

        logger.error(`[api] Request failed: ${path}`, { status: res.status, detail });
        throw new Error(detail);
    }

    try {
        const data = await res.json();
        return { data, status: res.status };
    } catch (_) {
        return { data: null, status: res.status };
    }
}

const api = {
    get: (path, options) => request('GET', path, options),
    post: (path, data, options) => request('POST', path, { ...options, body: data }),
    put: (path, data, options) => request('PUT', path, { ...options, body: data }),
    delete: (path, options) => request('DELETE', path, options),
    patch: (path, data, options) => request('PATCH', path, { ...options, body: data }),
};

export default api;
