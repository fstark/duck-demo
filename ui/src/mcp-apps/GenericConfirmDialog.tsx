import { useState, useCallback, type ReactNode } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import {
    type ConfirmationField,
    type ConfirmationMetadata,
    getResultLines,
    runGenericConfirmAction,
} from './shared/confirmation';
import {
    ActionRow,
    AppCard,
    AppShell,
    PrimaryButton,
    SecondaryButton,
    StatusScreen,
    uiColors,
} from './shared/ui';

export default function GenericConfirmDialog() {
    const [status, setStatus] = useState<'connecting' | 'ready' | 'confirming' | 'confirmed' | 'cancelled'>('connecting');
    const [confirmationData, setConfirmationData] = useState<ConfirmationMetadata | null>(null);
    const [executionResult, setExecutionResult] = useState<Record<string, unknown> | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    const { app, isConnected, error } = useApp({
        appInfo: { name: 'GenericConfirmDialog', version: '1.0.1' },
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
            setActionError(null);
            setStatus('confirming');

            // Call the generic dispatcher with the original tool name and arguments
            const result = await runGenericConfirmAction(app, {
                original_tool: confirmationData.original_tool,
                arguments: confirmationData.arguments,
            });

            setExecutionResult(result);

            console.log('Action confirmed and completed:', result);
            setStatus('confirmed');
        } catch (err) {
            console.error('Failed to execute action:', err);
            setActionError((err as Error)?.message || 'Failed to execute action.');
            setStatus('ready');
        }
    }, [app, confirmationData]);

    const handleCancel = useCallback(async () => {
        if (!app) return;
        setStatus('cancelled');
    }, [app]);

    if (error) {
        return (
            <AppShell>
                <StatusScreen title="Error" titleColor="#dc2626" message={error.message} />
            </AppShell>
        );
    }

    if (!isConnected || status === 'connecting') {
        return (
            <AppShell>
                <StatusScreen title="Connecting..." message="Waiting for MCP app connection." />
            </AppShell>
        );
    }

    if (status === 'confirming') {
        return (
            <AppShell>
                <StatusScreen title="Submitting..." message="Executing confirmed action." />
            </AppShell>
        );
    }

    if (status === 'confirmed') {
        const resultLines = getResultLines(executionResult);

        return (
            <AppShell>
                <StatusScreen title="Confirmed" titleColor="#16a34a" message="Action has been completed successfully." />

                <AppCard marginBottom={0}>
                    <h3 style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: uiColors.muted,
                        marginTop: 0,
                        marginBottom: resultLines.length > 0 ? '12px' : 0,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                    }}>
                        Result
                    </h3>
                    {resultLines.length > 0 ? resultLines.map(([label, value]) => (
                        <div key={label} style={{ marginBottom: '10px' }}>
                            <div style={{ fontSize: 12, color: uiColors.muted, marginBottom: 2 }}>{label}</div>
                            <div style={{ fontSize: 14, color: uiColors.text, fontWeight: 500 }}>{value}</div>
                        </div>
                    )) : (
                        <p style={{ margin: 0, color: uiColors.muted, fontSize: 14 }}>No result details were returned by the tool.</p>
                    )}
                </AppCard>
            </AppShell>
        );
    }

    if (status === 'cancelled') {
        return (
            <AppShell>
                <StatusScreen title="Cancelled" titleColor="#6b7280" message="Action was cancelled." />
            </AppShell>
        );
    }

    if (!confirmationData) {
        return (
            <AppShell>
                <StatusScreen title="Waiting..." message="Waiting for confirmation data." />
            </AppShell>
        );
    }

    // Group fields by their group property
    const groupedFields: Record<string, ConfirmationField[]> = {};
    const ungroupedFields: ConfirmationField[] = [];

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
        <AppShell>
            <h2 style={{ marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: '600' }}>
                {confirmationData.title}
            </h2>

            {confirmationData.description && (
                <p style={{
                    marginTop: 0,
                    marginBottom: '20px',
                    fontSize: '14px',
                    color: uiColors.muted,
                }}>
                    {confirmationData.description}
                </p>
            )}

            <AppCard marginBottom={24}>
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
                            color: uiColors.muted,
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
            </AppCard>

            <ActionRow marginTop={0}>
                <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
                <PrimaryConfirmButton category={confirmationData.category} onClick={handleConfirm}>
                    Confirm
                </PrimaryConfirmButton>
            </ActionRow>

            {actionError && (
                <p style={{ marginTop: '12px', color: '#b91c1c', fontSize: '14px' }}>
                    {actionError}
                </p>
            )}
        </AppShell>
    );
}

function FieldDisplay({ field }: { field: ConfirmationField }) {
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
                color: 'var(--vscode-descriptionForeground, #6b7280)',
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
                fontFamily: field.type === 'object' ? 'monospace' : 'inherit',
                color: 'var(--vscode-foreground, #111827)',
            }}>
                {displayValue}
            </div>
            {field.help_text && (
                <div style={{
                    fontSize: '11px',
                    color: 'var(--vscode-descriptionForeground, #9ca3af)',
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

function PrimaryConfirmButton({
    category,
    onClick,
    children,
}: {
    category: string;
    onClick: () => void;
    children: ReactNode;
}) {
    const [isHover, setIsHover] = useState(false);
    const baseColor = getCategoryColor(category);
    const backgroundColor = isHover ? darkenColor(baseColor) : baseColor;

    return (
        <PrimaryButton
            onClick={onClick}
            backgroundColor={backgroundColor}
        >
            <span
                onMouseEnter={() => setIsHover(true)}
                onMouseLeave={() => setIsHover(false)}
                style={{ display: 'inline-block', width: '100%' }}
            >
                {children}
            </span>
        </PrimaryButton>
    );
}
