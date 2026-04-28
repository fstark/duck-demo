import { useCallback, useEffect, useMemo, useState } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import {
    type ConfirmationMetadata,
    runGenericConfirmAction,
} from './shared/confirmation';
import {
    ActionRow,
    AppCard,
    AppShell,
    PrimaryButton,
    SecondaryButton,
    SectionTitle,
    StatusScreen,
    uiColors,
} from './shared/ui';

type TariffSuggestion = {
    code: string;
    description: string;
    confidence?: string;
};

type TariffItem = {
    sku: string;
    qty: number;
    item_name: string;
    suggestions: TariffSuggestion[];
};

type TariffPickerPayload = {
    title: string;
    destination_country: string;
    original_tool: string;
    arguments: {
        ship_from: Record<string, unknown>;
        ship_to: Record<string, unknown>;
        planned_departure: string;
        planned_arrival: string;
        packages: Array<{ contents: Array<Record<string, unknown>> }>;
        reference?: Record<string, unknown> | null;
    };
    items: TariffItem[];
};

type SubmissionLine = {
    item_name: string;
    sku: string;
    qty: number;
    tariff_code: string;
    tariff_description: string | null;
};

export default function TariffPickerDialog() {
    const [status, setStatus] = useState<'connecting' | 'ready' | 'submitting' | 'awaiting_final_confirmation' | 'submitted' | 'cancelled' | 'error'>('connecting');
    const [payload, setPayload] = useState<TariffPickerPayload | null>(null);
    const [errorText, setErrorText] = useState<string | null>(null);
    const [selectedCodes, setSelectedCodes] = useState<Record<number, string>>({});
    const [customCodes, setCustomCodes] = useState<Record<number, string>>({});
    const [submittedLines, setSubmittedLines] = useState<SubmissionLine[]>([]);
    const [confirmationData, setConfirmationData] = useState<ConfirmationMetadata | null>(null);
    const [submittedNote, setSubmittedNote] = useState<string>('');

    const { app, isConnected, error } = useApp({
        appInfo: { name: 'TariffPickerDialog', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (appInstance) => {
            appInstance.ontoolresult = (params: any) => {
                if (!params?.structuredContent) return;
                const data = params.structuredContent as TariffPickerPayload;
                setPayload(data);

                const defaults: Record<number, string> = {};
                (data.items || []).forEach((item, idx) => {
                    const first = item.suggestions?.[0];
                    if (first?.code) defaults[idx] = first.code;
                });

                setSelectedCodes(defaults);
                setCustomCodes({});
                setConfirmationData(null);
                setSubmittedLines([]);
                setSubmittedNote('');
                setStatus('ready');
            };
        },
    });

    useEffect(() => {
        if (isConnected && status === 'connecting') {
            setStatus('ready');
        }
    }, [isConnected, status]);

    const canSubmit = useMemo(() => {
        if (!payload) return false;
        return payload.items.every((_, idx) => {
            const custom = (customCodes[idx] || '').trim();
            const selected = (selectedCodes[idx] || '').trim();
            return Boolean(custom || selected);
        });
    }, [payload, selectedCodes, customCodes]);

    const handleSubmit = useCallback(async () => {
        if (!app || !payload) return;

        try {
            setStatus('submitting');
            setErrorText(null);

            let itemCursor = 0;
            const nextSubmittedLines: SubmissionLine[] = [];
            const updatedPackages = payload.arguments.packages.map((pkg) => {
                const updatedContents = pkg.contents.map((content) => {
                    const item = payload.items[itemCursor];
                    const custom = (customCodes[itemCursor] || '').trim();
                    const selectedCode = custom || (selectedCodes[itemCursor] || '').trim();
                    const suggestion = (item?.suggestions || []).find((s) => s.code === selectedCode);
                    const selectedDescription = suggestion?.description || (content.tariff_description as string) || null;

                    if (item) {
                        nextSubmittedLines.push({
                            item_name: item.item_name,
                            sku: item.sku,
                            qty: item.qty,
                            tariff_code: selectedCode,
                            tariff_description: selectedDescription,
                        });
                    }

                    itemCursor += 1;
                    return {
                        ...content,
                        tariff_code: selectedCode,
                        tariff_description: selectedDescription,
                    };
                });

                return {
                    ...pkg,
                    contents: updatedContents,
                };
            });

            const response = await app.callServerTool({
                name: payload.original_tool,
                arguments: {
                    ...payload.arguments,
                    packages: updatedPackages,
                } as Record<string, unknown>,
            });

            setSubmittedLines(nextSubmittedLines);

            const responseContent = (response as any)?.structuredContent as ConfirmationMetadata | undefined;
            if (responseContent?.original_tool && responseContent?.arguments) {
                setConfirmationData(responseContent);
                setStatus('awaiting_final_confirmation');
            } else {
                setSubmittedNote('Shipment request submitted.');
                setStatus('submitted');
            }
        } catch (submitError: any) {
            setStatus('error');
            setErrorText(submitError?.message || 'Failed to submit tariff selections.');
        }
    }, [app, payload, selectedCodes, customCodes]);

    const handleFinalConfirm = useCallback(async () => {
        if (!app || !confirmationData) return;

        try {
            setStatus('submitting');
            const result = await runGenericConfirmAction(app, {
                original_tool: confirmationData.original_tool,
                arguments: confirmationData.arguments,
            });

            const shipmentId = result?.shipment_id;
            if (shipmentId) {
                setSubmittedNote(`Shipment ${shipmentId} was created successfully.`);
            } else {
                setSubmittedNote('Shipment was created successfully.');
            }
            setStatus('submitted');
        } catch (confirmError: any) {
            setErrorText(confirmError?.message || 'Failed to create shipment after tariff selection.');
            setStatus('error');
        }
    }, [app, confirmationData]);

    const handleCancel = useCallback(() => {
        setStatus('cancelled');
    }, []);

    if (error) {
        return (
            <AppShell maxWidth={640}>
                <StatusScreen title="Error" titleColor="#dc2626" message={error.message} />
            </AppShell>
        );
    }

    if (!isConnected || status === 'connecting' || !payload) {
        return (
            <AppShell maxWidth={640}>
                <StatusScreen title="Loading..." message="Loading tariff suggestions..." />
            </AppShell>
        );
    }

    if (status === 'submitted') {
        return (
            <AppShell maxWidth={640}>
                <StatusScreen
                    title="Tariff Codes Submitted"
                    titleColor="#16a34a"
                    message="Shipment request was re-submitted with the selected tariff codes."
                />

                <AppCard>
                    <SectionTitle>Shipment Summary</SectionTitle>
                    <div style={{ fontSize: '14px', color: '#111827', marginBottom: '6px' }}>
                        <strong>Destination:</strong> {payload.destination_country}
                    </div>
                    <div style={{ fontSize: '14px', color: '#111827', marginBottom: '6px' }}>
                        <strong>Departure:</strong> {payload.arguments.planned_departure}
                    </div>
                    <div style={{ fontSize: '14px', color: '#111827', marginBottom: submittedLines.length > 0 ? '12px' : 0 }}>
                        <strong>Arrival:</strong> {payload.arguments.planned_arrival}
                    </div>

                    {submittedLines.length > 0 && (
                        <div>
                            <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '6px' }}>Selected tariff codes</div>
                            {submittedLines.map((line) => (
                                <div
                                    key={`${line.sku}-${line.tariff_code}`}
                                    style={{
                                        backgroundColor: uiColors.inputBg,
                                        border: `1px solid ${uiColors.cardBorder}`,
                                        borderRadius: '6px',
                                        padding: '8px 10px',
                                        marginBottom: '8px',
                                    }}
                                >
                                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>{line.item_name}</div>
                                    <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '2px' }}>SKU: {line.sku} | Qty: {line.qty}</div>
                                    <div style={{ fontSize: '14px', color: '#111827', marginTop: '4px' }}>
                                        <strong>{line.tariff_code}</strong>
                                        {line.tariff_description ? ` - ${line.tariff_description}` : ''}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </AppCard>

                <div style={{ border: '1px solid #bbf7d0', backgroundColor: '#f0fdf4', borderRadius: '8px', padding: '12px', color: '#166534', fontSize: '14px' }}>
                    {submittedNote || 'Shipment was created successfully.'}
                </div>
            </AppShell>
        );
    }

    if (status === 'awaiting_final_confirmation' && confirmationData) {
        const summaryFields = (confirmationData.fields || []).filter((field) => {
            return field.value !== null && field.value !== undefined && field.value !== '';
        });

        return (
            <AppShell maxWidth={640}>
                <h2 style={{ marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>
                    Confirm Shipment Creation
                </h2>
                <p style={{ marginTop: 0, marginBottom: '16px', color: '#6b7280' }}>
                    Tariff codes are saved. Review and confirm shipment creation.
                </p>

                <AppCard>
                    <SectionTitle>Selected Tariffs</SectionTitle>
                    {submittedLines.map((line) => (
                        <div
                            key={`${line.sku}-${line.tariff_code}`}
                            style={{ backgroundColor: uiColors.inputBg, border: `1px solid ${uiColors.cardBorder}`, borderRadius: '6px', padding: '8px 10px', marginBottom: '8px' }}
                        >
                            <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827' }}>{line.item_name}</div>
                            <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '2px' }}>SKU: {line.sku} | Qty: {line.qty}</div>
                            <div style={{ fontSize: '14px', color: '#111827', marginTop: '4px' }}>
                                <strong>{line.tariff_code}</strong>
                                {line.tariff_description ? ` - ${line.tariff_description}` : ''}
                            </div>
                        </div>
                    ))}
                </AppCard>

                <AppCard>
                    <SectionTitle>Shipment Details</SectionTitle>
                    {summaryFields.map((field) => (
                        <div key={field.name} style={{ marginBottom: '8px' }}>
                            <div style={{ fontSize: '12px', color: '#6b7280' }}>{field.label}</div>
                            <div style={{ fontSize: '14px', color: '#111827', fontWeight: 500 }}>{String(field.value)}</div>
                        </div>
                    ))}
                </AppCard>

                <ActionRow marginTop={0}>
                    <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
                    <PrimaryButton onClick={handleFinalConfirm}>Create Shipment</PrimaryButton>
                </ActionRow>
            </AppShell>
        );
    }

    if (status === 'cancelled') {
        return (
            <AppShell maxWidth={640}>
                <StatusScreen title="Cancelled" titleColor="#6b7280" message="Tariff code selection was cancelled." />
            </AppShell>
        );
    }

    return (
        <AppShell maxWidth={640}>
            <h2 style={{ marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>
                {payload.title || 'Select tariff codes'}
            </h2>
            <p style={{ marginTop: 0, marginBottom: '20px', fontSize: '14px', color: '#6b7280' }}>
                Destination: {payload.destination_country}
            </p>

            {payload.items.map((item, idx) => {
                const selected = selectedCodes[idx] || '';
                const custom = customCodes[idx] || '';

                return (
                    <AppCard key={`${item.sku}-${idx}`}>
                        <div style={{ fontWeight: 600, fontSize: '18px', marginBottom: '4px' }}>{item.item_name}</div>
                        <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '12px' }}>
                            SKU: {item.sku} | Qty: {item.qty}
                        </div>

                        {(item.suggestions || []).map((suggestion) => (
                            <label
                                key={`${idx}-${suggestion.code}`}
                                style={{
                                    display: 'block',
                                    marginBottom: '8px',
                                    border: `1px solid ${uiColors.cardBorder}`,
                                    borderRadius: '6px',
                                    padding: '8px 10px',
                                    backgroundColor: uiColors.inputBg,
                                    cursor: 'pointer',
                                }}
                            >
                                <input
                                    type="radio"
                                    name={`tariff-${idx}`}
                                    checked={selected === suggestion.code}
                                    onChange={() => setSelectedCodes((prev) => ({ ...prev, [idx]: suggestion.code }))}
                                    style={{ marginRight: '8px' }}
                                />{' '}
                                <strong>{suggestion.code}</strong> - {suggestion.description}
                                {suggestion.confidence ? ` (${suggestion.confidence})` : ''}
                            </label>
                        ))}

                        <div style={{ marginTop: '10px' }}>
                            <label style={{ fontSize: '13px', color: '#374151', fontWeight: 600 }}>Custom code (optional)</label>
                            <input
                                type="text"
                                value={custom}
                                onChange={(e) => setCustomCodes((prev) => ({ ...prev, [idx]: e.target.value }))}
                                placeholder="e.g. 9503.00"
                                style={{
                                    width: '100%',
                                    marginTop: '6px',
                                    padding: '8px 10px',
                                    border: `1px solid ${uiColors.inputBorder}`,
                                    borderRadius: '6px',
                                    fontSize: '14px',
                                    color: '#111827',
                                    backgroundColor: uiColors.inputBg,
                                    boxSizing: 'border-box',
                                }}
                            />
                        </div>
                    </AppCard>
                );
            })}

            {status === 'error' && <p style={{ color: '#b91c1c', marginTop: '4px' }}>{errorText}</p>}

            <ActionRow>
                <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
                <PrimaryButton
                    onClick={handleSubmit}
                    disabled={!canSubmit || status === 'submitting'}
                >
                    {status === 'submitting' ? 'Submitting...' : 'Confirm Tariff Codes'}
                </PrimaryButton>
            </ActionRow>
        </AppShell>
    );
}
