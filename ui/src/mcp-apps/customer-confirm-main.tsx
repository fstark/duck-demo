import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import CustomerConfirmDialog from './CustomerConfirmDialog';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <CustomerConfirmDialog />
    </StrictMode>,
);
