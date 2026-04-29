import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import QcInspectionViewer from './QcInspectionViewer';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <QcInspectionViewer />
    </StrictMode>,
);
