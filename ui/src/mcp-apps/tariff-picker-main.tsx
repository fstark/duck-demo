import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import TariffPickerDialog from './TariffPickerDialog';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <TariffPickerDialog />
    </StrictMode>,
);
