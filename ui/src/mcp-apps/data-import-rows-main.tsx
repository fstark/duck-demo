import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import DataImportRowsApp from './DataImportRowsApp';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <DataImportRowsApp />
    </StrictMode>,
);
