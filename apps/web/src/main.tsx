import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import './theme.css';
import './index.css';

const root = document.getElementById('root');
if (!root) throw new Error('Application root is missing');
ReactDOM.createRoot(root).render(<React.StrictMode><App /></React.StrictMode>);
