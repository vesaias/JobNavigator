import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // send jn_session cookie on every request
});

// Attach API key from localStorage as a fallback header (extension + API client parity)
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('jobnavigator_api_key') || '';
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// Broadcast a global event on 401 so the app can show the login modal
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('jn:unauthorized'));
    }
    return Promise.reject(error);
  }
);

export default api;
