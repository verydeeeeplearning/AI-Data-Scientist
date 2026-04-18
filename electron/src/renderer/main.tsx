import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { bootstrapRendererObservabilityFromQuery } from './observability';
import './styles/globals.css';

bootstrapRendererObservabilityFromQuery();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
