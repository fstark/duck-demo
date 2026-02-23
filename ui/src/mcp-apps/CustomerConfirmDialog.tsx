import { useState, useCallback } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';

interface CustomerData {
    name: string;
    company?: string;
    email?: string;
    phone?: string;
    address_line1?: string;
    address_line2?: string;
    city?: string;
    postal_code?: string;
    country?: string;
    tax_id?: string;
    payment_terms?: number;
    currency?: string;
    notes?: string;
}

export default function CustomerConfirmDialog() {
    const [status, setStatus] = useState<'connecting' | 'ready' | 'confirmed' | 'cancelled'>('connecting');
    const [customerData, setCustomerData] = useState<CustomerData | null>(null);

    const { app, isConnected, error } = useApp({
        appInfo: { name: 'CustomerConfirmDialog', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (appInstance) => {
            // Listen for tool input (the arguments passed to crm_create_customer)
            appInstance.ontoolinput = (params: any) => {
                console.log('Received tool input:', params);
                if (params.arguments) {
                    setCustomerData(params.arguments as CustomerData);
                    setStatus('ready');
                }
            };

            // Also listen for tool result as fallback
            appInstance.ontoolresult = (params: any) => {
                console.log('Received tool result:', params);
                if (params.content) {
                    // Try to extract customer data from structured content
                    try {
                        for (const item of params.content) {
                            if (item.type === 'text') {
                                const parsed = JSON.parse(item.text);
                                if (parsed.data) {
                                    setCustomerData(parsed.data as CustomerData);
                                    setStatus('ready');
                                }
                            }
                        }
                    } catch {
                        // ignore parse errors
                    }
                }
            };
        },
    });

    // Once connected, mark as ready if we don't have data yet
    // (data may arrive via ontoolinput notification)
    if (isConnected && status === 'connecting') {
        setStatus('ready');
    }

    const handleConfirm = useCallback(async () => {
        if (!customerData || !app) return;

        try {
            setStatus('confirmed');

            // Call the server tool to actually create the customer
            const response = await app.callServerTool({
                name: 'crm_confirm_create_customer',
                arguments: customerData as unknown as Record<string, unknown>,
            });

            console.log('Customer created:', response);
        } catch (err) {
            console.error('Failed to create customer:', err);
            setStatus('ready');
        }
    }, [app, customerData]);

    const handleCancel = useCallback(async () => {
        if (!app) return;
        setStatus('cancelled');
    }, [app]);

    if (error) {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <h2 style={{ color: '#dc2626', marginTop: 0 }}>Error</h2>
                <p>{error.message}</p>
            </div>
        );
    }

    if (!isConnected || status === 'connecting') {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <p>Connecting...</p>
            </div>
        );
    }

    if (status === 'confirmed') {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <h2 style={{ color: '#16a34a', marginTop: 0 }}>✓ Confirmed</h2>
                <p>Customer has been created successfully.</p>
            </div>
        );
    }

    if (status === 'cancelled') {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <h2 style={{ color: '#6b7280', marginTop: 0 }}>Cancelled</h2>
                <p>Customer creation was cancelled.</p>
            </div>
        );
    }

    if (!customerData) {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <p>Waiting for customer data...</p>
            </div>
        );
    }

    return (
        <div style={{
            padding: '24px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            maxWidth: '500px',
            margin: '0 auto'
        }}>
            <h2 style={{ marginTop: 0, marginBottom: '16px', fontSize: '20px', fontWeight: '600' }}>
                Confirm New Customer
            </h2>

            <div style={{
                backgroundColor: '#f9fafb',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '24px'
            }}>
                <DataField label="Name" value={customerData.name} />
                <DataField label="Company" value={customerData.company} />
                <DataField label="Email" value={customerData.email} />
                <DataField label="Phone" value={customerData.phone} />
                <DataField label="Address" value={[customerData.address_line1, customerData.address_line2].filter(Boolean).join(', ')} />
                <DataField label="City" value={customerData.city} />
                <DataField label="Postal Code" value={customerData.postal_code} />
                <DataField label="Country" value={customerData.country} />
                <DataField label="Tax ID" value={customerData.tax_id} />
                <DataField label="Payment Terms" value={customerData.payment_terms ? `${customerData.payment_terms} days` : undefined} />
                <DataField label="Currency" value={customerData.currency} />
                <DataField label="Notes" value={customerData.notes} />
            </div>

            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button
                    onClick={handleCancel}
                    style={{
                        padding: '8px 16px',
                        fontSize: '14px',
                        fontWeight: '500',
                        border: '1px solid #d1d5db',
                        borderRadius: '6px',
                        backgroundColor: 'white',
                        color: '#374151',
                        cursor: 'pointer',
                        transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f9fafb'}
                    onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'white'}
                >
                    Cancel
                </button>
                <button
                    onClick={handleConfirm}
                    style={{
                        padding: '8px 16px',
                        fontSize: '14px',
                        fontWeight: '500',
                        border: 'none',
                        borderRadius: '6px',
                        backgroundColor: '#2563eb',
                        color: 'white',
                        cursor: 'pointer',
                        transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#1d4ed8'}
                    onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#2563eb'}
                >
                    Confirm & Create Customer
                </button>
            </div>
        </div>
    );
}

function DataField({ label, value }: { label: string; value?: string | number }) {
    if (!value) return null;
    return (
        <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>{label}</div>
            <div style={{ fontSize: '14px', fontWeight: label === 'Name' ? '500' : '400' }}>{value}</div>
        </div>
    );
}