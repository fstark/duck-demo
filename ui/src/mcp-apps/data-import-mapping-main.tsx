import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import DataImportMappingApp from './DataImportMappingApp';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <DataImportMappingApp />
    </StrictMode>,
);
