```javascript
import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

api.interceptors.request.use(
  config => {
    console.log('Request:', config.method.toUpperCase(), config.url, config.params || config.data || '');
    return config;
  },
  error => {
    console.error('Request Error:', error.message, error.config);
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  response => {
    console.log('Response:', response.status, response.config.method.toUpperCase(), response.config.url, response.data);
    return response;
  },
  error => {
    console.error('Response Error:', error.response?.status, error.response?.data || error.message, error.config);
    if (error.response && error.response.status === 401) {
      console.warn('Unauthorized access. Redirecting to login...');
      localStorage.removeItem('user_info');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```