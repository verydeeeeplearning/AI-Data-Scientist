import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { DensityProvider } from './components/providers/DensityProvider';
import { ThemeProvider } from './components/providers/ThemeProvider';
import { bootstrapRendererObservabilityFromQuery } from './observability';
import './i18n';
import './styles/globals.css';

bootstrapRendererObservabilityFromQuery();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <DensityProvider>
        <App />
      </DensityProvider>
    </ThemeProvider>
  </React.StrictMode>
);
