import { useState, useCallback } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';

interface FieldMetadata {
    name: string;
    label: string;
    type: string;
    value: any;
    required?: boolean;
    help_text?: string;
    group?: string;
    display_order?: number;
    options?: string[];
}

interface ConfirmationMetadata {
    original_tool: string;
    title: string;
    description: string;
    category: string;
    fields: FieldMetadata[];
    arguments: Record<string, any>;
}

export default function GenericConfirmDialog() {
    const [status, setStatus] = useState<'connecting' | 'ready' | 'confirmed' | 'cancelled'>('connecting');
    const [confirmationData, setConfirmationData] = useState<ConfirmationMetadata | null>(null);

    const { app, isConnected, error } = useApp({
        appInfo: { name: 'GenericConfirmDialog', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (appInstance) => {
            // Listen for tool result (the metadata returned by gateway tools)
            appInstance.ontoolresult = (params: any) => {
                console.log('Received tool result:', params);
                // Check for structuredContent first (new format)
                if (params.structuredContent) {
                    setConfirmationData(params.structuredContent as ConfirmationMetadata);
                    setStatus('ready');
                } else if (params.content) {
                    // Try to extract from content array
                    try {
                        for (const item of params.content) {
                            if (item.type === 'text') {
                                const parsed = JSON.parse(item.text);
                                if (parsed.data) {
                                    setConfirmationData(parsed.data as ConfirmationMetadata);
                                    setStatus('ready');
                                    break;
                                }
                            }
                        }
                    } catch (err) {
                        console.error('Failed to parse tool result:', err);
                    }
                }
            };
        },
    });

    // Once connected, mark as ready if we don't have data yet
    if (isConnected && status === 'connecting') {
        setStatus('ready');
    }

    const handleConfirm = useCallback(async () => {
        if (!confirmationData || !app) return;

        try {
            setStatus('confirmed');

            // Call the generic dispatcher with the original tool name and arguments
            const response = await app.callServerTool({
                name: 'generic_confirm_action',
                arguments: {
                    original_tool: confirmationData.original_tool,
                    arguments: confirmationData.arguments,
                } as unknown as Record<string, unknown>,
            });

            console.log('Action confirmed and completed:', response);
        } catch (err) {
            console.error('Failed to execute action:', err);
            setStatus('ready');
        }
    }, [app, confirmationData]);

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
                <p>Action has been completed successfully.</p>
            </div>
        );
    }

    if (status === 'cancelled') {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <h2 style={{ color: '#6b7280', marginTop: 0 }}>Cancelled</h2>
                <p>Action was cancelled.</p>
            </div>
        );
    }

    if (!confirmationData) {
        return (
            <div style={{ padding: '20px', fontFamily: 'system-ui, sans-serif' }}>
                <p>Waiting for confirmation data...</p>
            </div>
        );
    }

    // Group fields by their group property
    const groupedFields: Record<string, FieldMetadata[]> = {};
    const ungroupedFields: FieldMetadata[] = [];

    for (const field of confirmationData.fields) {
        if (field.group) {
            if (!groupedFields[field.group]) {
                groupedFields[field.group] = [];
            }
            groupedFields[field.group].push(field);
        } else {
            ungroupedFields.push(field);
        }
    }

    // Sort fields by display_order within each group
    Object.keys(groupedFields).forEach(group => {
        groupedFields[group].sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
    });
    ungroupedFields.sort((a, b) => (a.display_order || 0) - (b.display_order || 0));

    return (
        <div style={{
            padding: '24px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            maxWidth: '600px',
            margin: '0 auto'
        }}>
            <h2 style={{ marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: '600' }}>
                {confirmationData.title}
            </h2>

            {confirmationData.description && (
                <p style={{
                    marginTop: 0,
                    marginBottom: '20px',
                    fontSize: '14px',
                    color: '#6b7280'
                }}>
                    {confirmationData.description}
                </p>
            )}

            <div style={{
                backgroundColor: '#f9fafb',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '24px'
            }}>
                {/* Render ungrouped fields first */}
                {ungroupedFields.length > 0 && ungroupedFields.map(field => (
                    <FieldDisplay key={field.name} field={field} />
                ))}

                {/* Render grouped fields */}
                {Object.entries(groupedFields).map(([groupName, fields]) => (
                    <div key={groupName} style={{ marginTop: ungroupedFields.length > 0 ? '16px' : 0 }}>
                        <h3 style={{
                            fontSize: '13px',
                            fontWeight: '600',
                            color: '#374151',
                            marginTop: 0,
                            marginBottom: '12px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em'
                        }}>
                            {groupName}
                        </h3>
                        {fields.map(field => (
                            <FieldDisplay key={field.name} field={field} />
                        ))}
                    </div>
                ))}
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
                        backgroundColor: getCategoryColor(confirmationData.category),
                        color: 'white',
                        cursor: 'pointer',
                        transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => {
                        const color = getCategoryColor(confirmationData.category);
                        e.currentTarget.style.backgroundColor = darkenColor(color);
                    }}
                    onMouseOut={(e) => {
                        e.currentTarget.style.backgroundColor = getCategoryColor(confirmationData.category);
                    }}
                >
                    Confirm
                </button>
            </div>
        </div>
    );
}

function FieldDisplay({ field }: { field: FieldMetadata }) {
    // Don't display fields with null/undefined values
    if (field.value === null || field.value === undefined || field.value === '') {
        return null;
    }

    // Format the value based on type
    let displayValue: string;

    if (field.type === 'object' && typeof field.value === 'object') {
        displayValue = JSON.stringify(field.value, null, 2);
    } else if (field.type === 'boolean') {
        displayValue = field.value ? 'Yes' : 'No';
    } else if (Array.isArray(field.value)) {
        displayValue = field.value.join(', ');
    } else {
        displayValue = String(field.value);
    }

    return (
        <div style={{ marginBottom: '12px' }}>
            <div style={{
                fontSize: '12px',
                color: '#6b7280',
                marginBottom: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
            }}>
                {field.label}
                {field.required && (
                    <span style={{ color: '#dc2626', fontSize: '14px' }}>*</span>
                )}
            </div>
            <div style={{
                fontSize: '14px',
                fontWeight: field.required ? '500' : '400',
                whiteSpace: field.type === 'textarea' || field.type === 'object' ? 'pre-wrap' : 'normal',
                fontFamily: field.type === 'object' ? 'monospace' : 'inherit'
            }}>
                {displayValue}
            </div>
            {field.help_text && (
                <div style={{
                    fontSize: '11px',
                    color: '#9ca3af',
                    marginTop: '2px'
                }}>
                    {field.help_text}
                </div>
            )}
        </div>
    );
}

function getCategoryColor(category: string): string {
    const colors: Record<string, string> = {
        customer: '#2563eb',
        order: '#7c3aed',
        financial: '#dc2626',
        production: '#ea580c',
        messaging: '#0891b2',
        general: '#059669'
    };
    return colors[category] || colors.general;
}

function darkenColor(color: string): string {
    const colorMap: Record<string, string> = {
        '#2563eb': '#1d4ed8',
        '#7c3aed': '#6d28d9',
        '#dc2626': '#b91c1c',
        '#ea580c': '#c2410c',
        '#0891b2': '#0e7490',
        '#059669': '#047857'
    };
    return colorMap[color] || color;
}
