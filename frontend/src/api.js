import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Add API key to requests
api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('jobnavigator_api_key') || '';
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

export default api;
