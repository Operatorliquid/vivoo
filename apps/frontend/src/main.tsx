import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { initializeTheme } from '@courtvision/design-system';
import '@courtvision/design-system/theme.css';
import '@courtvision/design-system/typography.css';
import '@courtvision/design-system/components.css';
import './styles/base.css';
import './styles/shell.css';
import './styles/board.css';
import './styles/detail.css';
import './styles/public.css';
import './styles/admin.css';
import { App } from './app/App';

initializeTheme();

createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
);
