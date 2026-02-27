import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import GenericConfirmDialog from './GenericConfirmDialog';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <GenericConfirmDialog />
    </StrictMode>,
);
