import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import DataImportViewer from './DataImportViewer';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <DataImportViewer />
    </StrictMode>,
);
