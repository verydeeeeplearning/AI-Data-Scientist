import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '../renderer/components/providers/ThemeProvider';
import { DensityProvider } from '../renderer/components/providers/DensityProvider';
import './i18n';
import './styles/mobile.css';
import App from './App';
import { registerMobileServiceWorker } from './sw/register';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <DensityProvider>
        <App />
      </DensityProvider>
    </ThemeProvider>
  </React.StrictMode>,
);

registerMobileServiceWorker();
