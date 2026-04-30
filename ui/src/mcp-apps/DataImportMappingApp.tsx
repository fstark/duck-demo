import { useRef, useState, useCallback } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import { AppCard, SectionTitle, PrimaryButton, uiColors } from './shared/ui';

const fullPage: React.CSSProperties = {
    width: '100vw', minHeight: '100vh', padding: 24,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    color: uiColors.text, backgroundColor: '#ffffff', boxSizing: 'border-box',
};

// ── Types ────────────────────────────────────────────────────────────────────

interface MappingEntry {
    source: string;
    target: string | null;
    transform: string;
    confidence: number;
}

interface TargetField {
    name: string;
    required: boolean;
    type: string;
}

interface SampleRow {
    raw_data: Record<string, string>;
    mapped_data: Record<string, string | number | null>;
}

interface MappingState {
    job_id: string;
    entity_type: string;
    entity_confidence: number;
    source_filename: string | null;
    row_count: number;
    columns_detected: string[];
    mapping: MappingEntry[];
    sample_rows: SampleRow[];
    target_fields: TargetField[];
    global_instructions: string;
    status: string;
}

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ value }: { value: number }) {
    const pct = Math.round(value * 100);
    let bg: string, border: string, color: string;
    if (value >= 0.85) {
        bg = '#f0fdf4'; border = '#86efac'; color = '#15803d';
    } else if (value >= 0.70) {
        bg = '#fffbeb'; border = '#fcd34d'; color = '#b45309';
    } else {
        bg = '#fef2f2'; border = '#fca5a5'; color = '#dc2626';
    }
    return (
        <span style={{
            display: 'inline-block', padding: '2px 8px', borderRadius: 4,
            border: `1px solid ${border}`, backgroundColor: bg, color,
            fontSize: 11, fontWeight: 600,
        }}>
            {pct}%
        </span>
    );
}

// ── Mapping table (editable) ──────────────────────────────────────────────────

function MappingTable({ mapping, targetFields, onChangeTarget, onChangeTransform, onToggleExclude }: {
    mapping: MappingEntry[];
    targetFields: TargetField[];
    onChangeTarget: (index: number, target: string | null) => void;
    onChangeTransform: (index: number, transform: string) => void;
    onToggleExclude: (index: number) => void;
}) {
    return (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
                <tr style={{ borderBottom: `2px solid ${uiColors.cardBorder}` }}>
                    <th style={{ ...thStyle, width: 28, textAlign: 'center' }}>✓</th>
                    <th style={thStyle}>Source Column</th>
                    <th style={thStyle}>Target Field</th>
                    <th style={thStyle}>Transform</th>
                    <th style={{ ...thStyle, textAlign: 'center' }}>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {mapping.map((m, i) => {
                    const excluded = m.target === null;
                    return (
                        <tr key={i} style={{
                            borderBottom: `1px solid ${uiColors.cardBorder}`,
                            opacity: excluded ? 0.4 : 1,
                        }}>
                            <td style={{ ...tdStyle, textAlign: 'center' }}>
                                <input
                                    type="checkbox"
                                    checked={!excluded}
                                    onChange={() => onToggleExclude(i)}
                                    style={{ cursor: 'pointer' }}
                                />
                            </td>
                            <td style={tdStyle}><code style={codeStyle}>{m.source}</code></td>
                            <td style={tdStyle}>
                                <select
                                    value={m.target ?? ''}
                                    onChange={(e) => onChangeTarget(i, e.target.value || null)}
                                    style={selectStyle}
                                    disabled={excluded}
                                >
                                    <option value="">— unmapped —</option>
                                    {targetFields.map(f => (
                                        <option key={f.name} value={f.name}>
                                            {f.name}{f.required ? ' *' : ''}
                                        </option>
                                    ))}
                                </select>
                            </td>
                            <td style={tdStyle}>
                                <input
                                    type="text"
                                    value={m.transform}
                                    onChange={(e) => onChangeTransform(i, e.target.value)}
                                    style={inputStyle}
                                    disabled={excluded}
                                />
                            </td>
                            <td style={{ ...tdStyle, textAlign: 'center' }}>
                                <ConfidenceBadge value={m.confidence} />
                            </td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    );
}

// ── Sample preview table ──────────────────────────────────────────────────────

function SamplePreview({ sampleRows, mapping, loading }: {
    sampleRows: SampleRow[];
    mapping: MappingEntry[];
    loading: boolean;
}) {
    const activeCols = mapping.filter(m => m.target !== null);

    return (
        <div style={{ position: 'relative' }}>
            {loading && (
                <div style={{
                    position: 'absolute', inset: 0, backgroundColor: 'rgba(255,255,255,0.7)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    borderRadius: 6, zIndex: 1,
                }}>
                    <span style={{ fontSize: 13, color: uiColors.muted, fontWeight: 500 }}>
                        Refreshing preview…
                    </span>
                </div>
            )}
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                        <tr style={{ borderBottom: `2px solid ${uiColors.cardBorder}` }}>
                            <th style={{ ...thStyle, fontSize: 11 }}>#</th>
                            {activeCols.map(m => (
                                <th key={m.source} style={{ ...thStyle, fontSize: 11 }}>
                                    <div style={{ color: uiColors.muted }}>{m.source}</div>
                                    <div style={{ fontWeight: 700 }}>→ {m.target}</div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sampleRows.map((row, idx) => (
                            <tr key={idx} style={{ borderBottom: `1px solid ${uiColors.cardBorder}` }}>
                                <td style={{ ...tdStyle, fontSize: 11, color: uiColors.muted }}>{idx + 1}</td>
                                {activeCols.map(m => {
                                    const rawVal = row.raw_data[m.source];
                                    const mappedVal = m.target ? row.mapped_data[m.target] : null;
                                    const changed = rawVal !== undefined && String(rawVal) !== String(mappedVal ?? '');
                                    return (
                                        <td key={m.source} style={tdStyle}>
                                            {changed ? (
                                                <span>
                                                    <span style={{ color: uiColors.muted, textDecoration: 'line-through', fontSize: 11 }}>
                                                        {rawVal}
                                                    </span>
                                                    {' → '}
                                                    <span style={{ fontWeight: 600 }}>
                                                        {mappedVal != null ? String(mappedVal) : '—'}
                                                    </span>
                                                </span>
                                            ) : (
                                                <span>{mappedVal != null ? String(mappedVal) : '—'}</span>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// ── Shared styles ─────────────────────────────────────────────────────────────

const thStyle: React.CSSProperties = {
    textAlign: 'left', padding: '6px 8px', fontWeight: 600,
    color: '#374151', whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
    padding: '5px 8px', verticalAlign: 'middle',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
};

const codeStyle: React.CSSProperties = {
    fontSize: 12, backgroundColor: '#f3f4f6', padding: '1px 4px',
    borderRadius: 3, fontFamily: 'monospace',
};

const selectStyle: React.CSSProperties = {
    fontSize: 12, padding: '3px 6px', borderRadius: 4,
    border: `1px solid ${uiColors.inputBorder}`, backgroundColor: uiColors.inputBg,
    width: '100%',
};

const inputStyle: React.CSSProperties = {
    fontSize: 12, padding: '3px 6px', borderRadius: 4,
    border: `1px solid ${uiColors.inputBorder}`, backgroundColor: uiColors.inputBg,
    width: '100%',
};

// ── Main component ────────────────────────────────────────────────────────────

export default function DataImportMappingApp() {
    const [state, setState] = useState<MappingState | null>(null);
    const [mapping, setMapping] = useState<MappingEntry[]>([]);
    const [sampleRows, setSampleRows] = useState<SampleRow[]>([]);
    const [globalInstructions, setGlobalInstructions] = useState('');
    const [previewLoading, setPreviewLoading] = useState(false);
    const [confirming, setConfirming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'mapping' | 'instructions'>('mapping');
    const appRef = useRef<any>(null);
    const previewTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const { isConnected, error: connError } = useApp({
        appInfo: { name: 'DataImportMappingApp', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (app) => {
            appRef.current = app;
            app.ontoolresult = (params: any) => {
                const data = extractMappingState(params);
                if (data) {
                    setState(data);
                    setMapping(data.mapping);
                    setSampleRows(data.sample_rows);
                    setGlobalInstructions(data.global_instructions || '');
                }
            };
        },
    });

    void isConnected;

    const refreshPreview = useCallback((updatedMapping: MappingEntry[], instructions?: string) => {
        if (!appRef.current || !state) return;
        // Debounce
        if (previewTimerRef.current) clearTimeout(previewTimerRef.current);
        previewTimerRef.current = setTimeout(async () => {
            setPreviewLoading(true);
            try {
                const result = await appRef.current.callServerTool({
                    name: 'data_import_preview_sample',
                    arguments: { job_id: state.job_id, mapping: updatedMapping, global_instructions: instructions ?? '' },
                });
                const parsed = extractPreviewResult(result);
                if (parsed) setSampleRows(parsed);
            } catch (err: any) {
                // Non-critical — just leave current preview
            } finally {
                setPreviewLoading(false);
            }
        }, 500);
    }, [state]);

    const handleChangeTarget = useCallback((index: number, target: string | null) => {
        setMapping(prev => {
            const next = [...prev];
            next[index] = { ...next[index], target };
            refreshPreview(next);
            return next;
        });
    }, [refreshPreview]);

    const handleChangeTransform = useCallback((index: number, transform: string) => {
        setMapping(prev => {
            const next = [...prev];
            next[index] = { ...next[index], transform };
            refreshPreview(next);
            return next;
        });
    }, [refreshPreview]);

    const handleToggleExclude = useCallback((index: number) => {
        setMapping(prev => {
            const next = [...prev];
            const current = next[index];
            next[index] = { ...current, target: current.target === null ? '' : null };
            refreshPreview(next);
            return next;
        });
    }, [refreshPreview]);

    const handleConfirm = useCallback(async () => {
        if (!appRef.current || !state) return;
        setConfirming(true);
        setError(null);
        try {
            // Persist the mapping
            await appRef.current.callServerTool({
                name: 'data_import_confirm_mapping',
                arguments: {
                    job_id: state.job_id,
                    mapping,
                    global_instructions: globalInstructions,
                },
            });
            // Ask the agent to open Phase 2 via sendMessage
            await appRef.current.sendMessage({
                role: 'user',
                content: [{
                    type: 'text', text:
                        `Mapping completed for import job ${state.job_id} (${state.row_count} rows). Move to the row review.`
                }],
            });
        } catch (err: any) {
            setError(err?.message ?? 'Confirmation failed');
            setConfirming(false);
        }
    }, [state, mapping, globalInstructions]);

    if (connError) {
        return (
            <div style={fullPage}>
                <p style={{ color: '#dc2626' }}>{connError.message}</p>
            </div>
        );
    }

    if (!state) {
        return (
            <div style={fullPage}>
                <p style={{ color: uiColors.muted, margin: 0 }}>Processing import…</p>
            </div>
        );
    }

    return (
        <div style={fullPage}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
                <span style={{
                    display: 'inline-block', padding: '4px 12px', borderRadius: 6,
                    border: '1px solid #93c5fd', backgroundColor: '#eff6ff', color: '#1d4ed8',
                    fontSize: 13, fontWeight: 600,
                }}>
                    Mapping Review
                </span>
                <span style={{ fontSize: 13, color: uiColors.muted }}>
                    {state.source_filename && (
                        <span><strong style={{ color: uiColors.text }}>{state.source_filename}</strong></span>
                    )}
                    {state.entity_type && (
                        <span> · {state.entity_type} <ConfidenceBadge value={state.entity_confidence} /></span>
                    )}
                    <span> · {state.row_count} row{state.row_count !== 1 ? 's' : ''}</span>
                </span>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 0, marginBottom: 14, borderBottom: `2px solid ${uiColors.cardBorder}` }}>
                {(['mapping', 'instructions'] as const).map(tab => (
                    <button
                        key={tab}
                        type="button"
                        onClick={() => setActiveTab(tab)}
                        style={{
                            padding: '8px 16px', fontSize: 13, fontWeight: 600,
                            border: 'none', borderBottom: activeTab === tab ? '2px solid #2563eb' : '2px solid transparent',
                            marginBottom: -2, cursor: 'pointer',
                            backgroundColor: 'transparent',
                            color: activeTab === tab ? '#2563eb' : uiColors.muted,
                        }}
                    >
                        {tab === 'mapping' ? 'Column Mapping' : 'Global Instructions'}
                    </button>
                ))}
            </div>

            {activeTab === 'mapping' && (
                <AppCard>
                    <MappingTable
                        mapping={mapping}
                        targetFields={state.target_fields}
                        onChangeTarget={handleChangeTarget}
                        onChangeTransform={handleChangeTransform}
                        onToggleExclude={handleToggleExclude}
                    />
                </AppCard>
            )}

            {activeTab === 'instructions' && (
                <AppCard>
                    <textarea
                        value={globalInstructions}
                        onChange={(e) => setGlobalInstructions(e.target.value)}
                        placeholder="Optional: describe data conventions (e.g. 'All dates are DD/MM/YYYY', 'Country names are in German')"
                        rows={6}
                        style={{
                            width: '100%', fontSize: 13, padding: '8px 12px',
                            border: `1px solid ${uiColors.inputBorder}`, borderRadius: 6,
                            backgroundColor: uiColors.inputBg, color: uiColors.text,
                            resize: 'vertical', fontFamily: 'inherit',
                        }}
                    />
                    <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                        <PrimaryButton
                            onClick={() => refreshPreview(mapping, globalInstructions)}
                            disabled={previewLoading}
                            backgroundColor="#2563eb"
                        >
                            {previewLoading ? 'Applying…' : 'Apply to Preview'}
                        </PrimaryButton>
                    </div>
                </AppCard>
            )}

            {/* Sample preview */}
            <AppCard>
                <SectionTitle>Sample Preview ({sampleRows.length} rows)</SectionTitle>
                <SamplePreview sampleRows={sampleRows} mapping={mapping} loading={previewLoading} />
            </AppCard>

            {/* Error */}
            {error && (
                <div style={{
                    padding: '8px 12px', marginBottom: 12, borderRadius: 6,
                    backgroundColor: '#fef2f2', border: '1px solid #fca5a5',
                    color: '#dc2626', fontSize: 13,
                }}>
                    {error}
                </div>
            )}

            {/* Confirm button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                <PrimaryButton
                    onClick={handleConfirm}
                    disabled={confirming}
                    backgroundColor="#16a34a"
                >
                    {confirming ? 'Processing…' : 'Confirm Mapping & Proceed'}
                </PrimaryButton>
            </div>
        </div>
    );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractMappingState(params: any): MappingState | null {
    if (!params) return null;
    const sc = params.structuredContent;
    if (sc && typeof sc === 'object' && sc.job_id && sc.mapping) return sc as MappingState;
    const content = params.content;
    if (Array.isArray(content)) {
        for (const item of content) {
            if (item?.type === 'text' && typeof item.text === 'string') {
                try {
                    const parsed = JSON.parse(item.text);
                    if (parsed?.job_id && parsed?.mapping) return parsed as MappingState;
                } catch { /* ignore */ }
            }
        }
    }
    if (params.job_id && params.mapping) return params as MappingState;
    return null;
}

function extractPreviewResult(params: any): SampleRow[] | null {
    if (!params) return null;
    const sc = params.structuredContent;
    if (sc && typeof sc === 'object' && sc.sample_rows) return sc.sample_rows;
    const content = params.content;
    if (Array.isArray(content)) {
        for (const item of content) {
            if (item?.type === 'text' && typeof item.text === 'string') {
                try {
                    const parsed = JSON.parse(item.text);
                    if (parsed?.sample_rows) return parsed.sample_rows;
                } catch { /* ignore */ }
            }
        }
    }
    if (params.sample_rows) return params.sample_rows;
    return null;
}
