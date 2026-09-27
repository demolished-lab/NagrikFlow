import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import './public-landing.css';
import './a11y.css';
import './reference-ui.css';
import { lang } from './i18n';

document.documentElement.lang = lang() === 'hi' ? 'hi' : 'en';
createRoot(document.getElementById('root')!).render(<App />);
