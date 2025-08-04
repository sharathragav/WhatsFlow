import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './components/App';

// Optional: Import any global error reporting or analytics
// import reportWebVitals from './reportWebVitals';

// Create the root element for React 18
const root = ReactDOM.createRoot(document.getElementById('root'));

// Render the main App component
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Optional: Measure performance in your app
// Learn more: https://bit.ly/CRA-vitals
// reportWebVitals(console.log);