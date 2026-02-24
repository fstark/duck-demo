import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import ItemInspectViewer from './ItemInspectViewer';

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <ItemInspectViewer />
    </StrictMode>,
);
