import { useRef, useState, useCallback } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import { AppShell, AppCard, SectionTitle, PrimaryButton, SecondaryButton, ActionRow, uiColors } from './shared/ui';

// ── Types ────────────────────────────────────────────────────────────────────

interface MappingEntry {
    source: string;
    target: string;
    transform: string;
    confidence: number;
}

interface RowIssue {
    field?: string;
    issue_type?: string;
    message?: string;
}

interface ImportRow {
    id: string;
    source_row: number;
    status: string;
    raw_data: Record<string, string>;
    mapped_data: Record<string, string | number | null>;
    resolved_refs: Record<string, string>;
    issues: RowIssue[];
    created_entity_id?: string | null;
}

interface BatchQuestion {
    issue_type: string;
    description: string;
    affected_rows: number[];
    suggestion?: string;
}

interface StagingState {
    job_id: string;
    entity_type: string | null;
    source_filename: string | null;
    source_format: string | null;
    status: string;
    row_count: number;
    columns_detected: string[];
    mapping: MappingEntry[] | null;
    issues_summary: Record<string, number>;
    batch_questions: BatchQuestion[];
    rows: ImportRow[];
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

// ── Row status badge ──────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { bg: string; border: string; color: string; label: string }> = {
    ready: { bg: '#f0fdf4', border: '#86efac', color: '#15803d', label: 'Ready' },
    needs_review: { bg: '#fffbeb', border: '#fcd34d', color: '#b45309', label: 'Review' },
    auto_fixed: { bg: '#eff6ff', border: '#93c5fd', color: '#1d4ed8', label: 'Auto-fixed' },
    rejected: { bg: '#fef2f2', border: '#fca5a5', color: '#dc2626', label: 'Rejected' },
    created: { bg: '#f0fdf4', border: '#86efac', color: '#15803d', label: 'Created' },
    merged: { bg: '#f5f3ff', border: '#c4b5fd', color: '#7c3aed', label: 'Merged' },
    skipped: { bg: '#f9fafb', border: '#e5e7eb', color: '#6b7280', label: 'Skipped' },
};

function RowStatusBadge({ status }: { status: string }) {
    const s = STATUS_STYLES[status] ?? { bg: '#f9fafb', border: '#e5e7eb', color: '#374151', label: status };
    return (
        <span style={{
            display: 'inline-block', padding: '2px 8px', borderRadius: 4,
            border: `1px solid ${s.border}`, backgroundColor: s.bg, color: s.color,
            fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
        }}>
            {s.label}
        </span>
    );
}

// ── Job status badge ──────────────────────────────────────────────────────────

function JobStatusBadge({ status }: { status: string }) {
    let bg: string, border: string, color: string, label: string;
    switch (status) {
        case 'validated':
            bg = '#fffbeb'; border = '#fcd34d'; color = '#b45309'; label = 'Reviewing';
            break;
        case 'ready_to_execute':
            bg = '#f0fdf4'; border = '#86efac'; color = '#15803d'; label = 'Ready to import';
            break;
        case 'executed':
            bg = '#f0fdf4'; border = '#86efac'; color = '#15803d'; label = 'Imported';
            break;
        case 'rolled_back':
            bg = '#fef2f2'; border = '#fca5a5'; color = '#dc2626'; label = 'Rolled back';
            break;
        default:
            bg = '#f9fafb'; border = '#e5e7eb'; color = '#374151'; label = status;
    }
    return (
        <span style={{
            display: 'inline-block', padding: '4px 12px', borderRadius: 6,
            border: `1px solid ${border}`, backgroundColor: bg, color,
            fontSize: 13, fontWeight: 600,
        }}>
            {label}
        </span>
    );
}

// ── Column mapping table ──────────────────────────────────────────────────────

function MappingTable({ mapping, excludedTargets, onToggle }: {
    mapping: MappingEntry[];
    excludedTargets: Set<string>;
    onToggle: (target: string) => void;
}) {
    return (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
                <tr style={{ borderBottom: `2px solid ${uiColors.cardBorder}` }}>
                    <th style={{ ...thStyle, width: 28, textAlign: 'center' }}></th>
                    <th style={thStyle}>Source</th>
                    <th style={thStyle}>Target</th>
                    <th style={thStyle}>Transform</th>
                    <th style={{ ...thStyle, textAlign: 'center' }}>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {mapping.map((m, i) => {
                    const excluded = excludedTargets.has(m.target);
                    return (
                        <tr key={i} style={{
                            borderBottom: `1px solid ${uiColors.cardBorder}`,
                            opacity: excluded ? 0.4 : 1,
                        }}>
                            <td style={{ ...tdStyle, textAlign: 'center' }}>
                                <input
                                    type="checkbox"
                                    checked={!excluded}
                                    onChange={() => onToggle(m.target)}
                                    style={{ cursor: 'pointer' }}
                                />
                            </td>
                            <td style={tdStyle}><code style={codeStyle}>{m.source}</code></td>
                            <td style={tdStyle}><code style={codeStyle}>{m.target}</code></td>
                            <td style={tdStyle}>{m.transform === 'none' ? '—' : m.transform}</td>
                            <td style={{ ...tdStyle, textAlign: 'center' }}><ConfidenceBadge value={m.confidence} /></td>
                        </tr>
                    );
                })}
            </tbody>
        </table>
    );
}

// ── Data grid ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 10;

function DataGrid({ rows, mapping, status, excludedTargets }: { rows: ImportRow[]; mapping: MappingEntry[] | null; status: string; excludedTargets: Set<string> }) {
    const [page, setPage] = useState(0);
    const targetCols = mapping ? mapping.map(m => m.target).filter(t => !excludedTargets.has(t)) : [];
    const showEntityId = status === 'executed';

    const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    const currentPage = Math.min(page, totalPages - 1);
    const pageRows = rows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

    return (
        <div>
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, tableLayout: 'fixed' }}>
                    <colgroup>
                        <col style={{ width: 36 }} />
                        <col style={{ width: 70 }} />
                        {targetCols.map(col => <col key={col} />)}
                        {showEntityId && <col style={{ width: 90 }} />}
                    </colgroup>
                    <thead>
                        <tr style={{ borderBottom: `2px solid ${uiColors.cardBorder}` }}>
                            <th style={{ ...thStyle, fontSize: 11 }}>#</th>
                            <th style={{ ...thStyle, fontSize: 11 }}>Status</th>
                            {targetCols.map(col => (
                                <th key={col} style={{ ...thStyle, fontSize: 11 }}>{col}</th>
                            ))}
                            {showEntityId && <th style={{ ...thStyle, fontSize: 11 }}>Entity ID</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {pageRows.map((row) => {
                            const dimmed = row.status === 'rejected' || row.status === 'skipped' || row.status === 'merged';
                            return (
                                <tr key={row.id} style={{
                                    borderBottom: `1px solid ${uiColors.cardBorder}`,
                                    opacity: dimmed ? 0.4 : 1,
                                    height: 32,
                                }}>
                                    <td style={{ ...tdStyle, fontSize: 11, color: uiColors.muted }}>{row.source_row}</td>
                                    <td style={tdStyle}><RowStatusBadge status={row.status} /></td>
                                    {targetCols.map(col => {
                                        const val = row.mapped_data[col];
                                        const hasIssue = !dimmed && row.issues.some(iss => iss.field === col);
                                        return (
                                            <td key={col} style={{
                                                ...tdStyle,
                                                backgroundColor: hasIssue ? '#fef2f2' : undefined,
                                            }}>
                                                {val != null ? String(val) : <span style={{ color: uiColors.muted }}>—</span>}
                                                {hasIssue && <span title="Has issue" style={{ marginLeft: 4, color: '#dc2626' }}>⚠</span>}
                                            </td>
                                        );
                                    })}
                                    {showEntityId && (
                                        <td style={{ ...tdStyle, fontWeight: 600, color: '#7c3aed' }}>
                                            {row.created_entity_id ?? '—'}
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            {/* Pagination */}
            {totalPages > 1 && (
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    gap: 8, marginTop: 10, fontSize: 12, color: uiColors.muted,
                }}>
                    <button
                        type="button"
                        onClick={() => setPage(Math.max(0, currentPage - 1))}
                        disabled={currentPage === 0}
                        style={paginationBtnStyle(currentPage === 0)}
                    >
                        ‹
                    </button>
                    <span style={{ fontWeight: 600, minWidth: 60, textAlign: 'center' }}>
                        {currentPage + 1} / {totalPages}
                    </span>
                    <button
                        type="button"
                        onClick={() => setPage(Math.min(totalPages - 1, currentPage + 1))}
                        disabled={currentPage === totalPages - 1}
                        style={paginationBtnStyle(currentPage === totalPages - 1)}
                    >
                        ›
                    </button>
                </div>
            )}
        </div>
    );
}

// ── Auto-fix log ──────────────────────────────────────────────────────────────

function AutoFixLog({ rows }: { rows: ImportRow[] }) {
    const fixes: string[] = [];
    for (const row of rows) {
        for (const iss of row.issues) {
            if (iss.issue_type === 'auto_fixed' && iss.message) {
                fixes.push(`Row ${row.source_row}: ${iss.message}`);
            }
        }
    }
    if (fixes.length === 0) return null;

    return (
        <details style={{ marginTop: 10, fontSize: 12 }}>
            <summary style={{ cursor: 'pointer', color: uiColors.muted, fontWeight: 500 }}>
                Auto-fixes applied ({fixes.length})
            </summary>
            <ul style={{ marginTop: 6, paddingLeft: 18, color: uiColors.text, lineHeight: 1.6 }}>
                {fixes.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
        </details>
    );
}

// ── Suggestion actions per issue type ─────────────────────────────────────────

function actionsForQuestion(q: BatchQuestion): { label: string; instruction: string; primary?: boolean }[] {
    switch (q.issue_type) {
        case 'existing_duplicate':
            return [
                { label: 'Skip', instruction: `reject rows ${q.affected_rows.join(', ')}`, primary: true },
                { label: 'Import anyway', instruction: `keep rows ${q.affected_rows.join(', ')}` },
            ];
        case 'possible_duplicate':
            return [
                { label: 'Merge', instruction: `merge rows ${q.affected_rows.join(', ')}`, primary: true },
                { label: 'Keep both', instruction: `keep rows ${q.affected_rows.join(', ')}` },
            ];
        default:
            return [];
    }
}

// ── Batch question carousel ──────────────────────────────────────────────────

function SuggestionCarousel({ questions, onAction, loading }: {
    questions: BatchQuestion[];
    onAction: (instruction: string) => void;
    loading: boolean;
}) {
    const [index, setIndex] = useState(0);
    // Clamp index if questions shrink
    const current = Math.min(index, questions.length - 1);
    const q = questions[current];
    if (!q) return null;

    const actions = actionsForQuestion(q);
    const total = questions.length;

    return (
        <AppCard>
            <div style={{ position: 'relative' }}>
                {/* Loading overlay */}
                {loading && (
                    <div style={{
                        position: 'absolute', inset: 0, backgroundColor: 'rgba(255,255,255,0.7)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        borderRadius: 6, zIndex: 1,
                    }}>
                        <span style={{ fontSize: 13, color: uiColors.muted, fontWeight: 500 }}>
                            Applying…
                        </span>
                    </div>
                )}
                {/* Navigation header */}
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginBottom: 10,
                }}>
                    <SectionTitle>Suggestions</SectionTitle>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: uiColors.muted }}>
                        <button
                            type="button"
                            onClick={() => setIndex(Math.max(0, current - 1))}
                            disabled={current === 0 || loading}
                            style={navBtnStyle(current === 0 || loading)}
                            aria-label="Previous suggestion"
                        >
                            ‹
                        </button>
                        <span style={{ fontWeight: 600, minWidth: 48, textAlign: 'center' }}>
                            {current + 1} / {total}
                        </span>
                        <button
                            type="button"
                            onClick={() => setIndex(Math.min(total - 1, current + 1))}
                            disabled={current === total - 1 || loading}
                            style={navBtnStyle(current === total - 1 || loading)}
                            aria-label="Next suggestion"
                        >
                            ›
                        </button>
                    </div>
                </div>

                {/* Current question */}
                <div style={{
                    padding: '10px 14px', borderRadius: 6,
                    backgroundColor: '#fffbeb', border: '1px solid #fcd34d', fontSize: 13,
                }}>
                    <div style={{ fontWeight: 600, color: '#b45309', marginBottom: 4 }}>{q.description}</div>
                    <div style={{ color: uiColors.muted, fontSize: 11 }}>
                        Affects row{q.affected_rows.length !== 1 ? 's' : ''} {q.affected_rows.join(', ')}
                    </div>
                </div>

                {/* Action buttons */}
                {actions.length > 0 && (
                    <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                        {actions.map((a) => (
                            a.primary
                                ? <PrimaryButton
                                    key={a.label}
                                    onClick={() => onAction(a.instruction)}
                                    disabled={loading}
                                    backgroundColor="#b45309"
                                >
                                    {a.label}
                                </PrimaryButton>
                                : <SecondaryButton key={a.label} onClick={() => onAction(a.instruction)}>
                                    {a.label}
                                </SecondaryButton>
                        ))}
                    </div>
                )}
            </div>
        </AppCard>
    );
}

function navBtnStyle(disabled: boolean): React.CSSProperties {
    return {
        width: 26, height: 26, borderRadius: 4, border: `1px solid ${uiColors.cardBorder}`,
        backgroundColor: disabled ? '#f9fafb' : '#ffffff',
        color: disabled ? '#d1d5db' : '#374151',
        cursor: disabled ? 'default' : 'pointer', fontSize: 16, fontWeight: 700,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        lineHeight: 1, padding: 0,
    };
}

const paginationBtnStyle = navBtnStyle;

// ── Issues summary ────────────────────────────────────────────────────────────

function IssuesSummary({ summary }: { summary: Record<string, number> }) {
    const entries = Object.entries(summary);
    if (entries.length === 0) return null;
    return (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
            {entries.map(([key, count]) => (
                <span key={key} style={{
                    fontSize: 12, padding: '2px 8px', borderRadius: 4,
                    backgroundColor: '#f9fafb', border: `1px solid ${uiColors.cardBorder}`,
                    color: uiColors.text,
                }}>
                    {key}: <strong>{count}</strong>
                </span>
            ))}
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

// ── Main component ────────────────────────────────────────────────────────────

export default function DataImportViewer() {
    const [state, setState] = useState<StagingState | null>(null);
    const [fixInput, setFixInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [excludedTargets, setExcludedTargets] = useState<Set<string>>(new Set());
    const appRef = useRef<any>(null);

    const toggleColumn = useCallback((target: string) => {
        setExcludedTargets(prev => {
            const next = new Set(prev);
            if (next.has(target)) next.delete(target);
            else next.add(target);
            return next;
        });
    }, []);

    const { isConnected, error: connError } = useApp({
        appInfo: { name: 'DataImportViewer', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (app) => {
            appRef.current = app;
            app.ontoolresult = (params: any) => {
                const data = extractState(params);
                if (data) setState(data);
            };
        },
    });

    void isConnected;

    const handleQuickAction = useCallback(async (instruction: string) => {
        if (!appRef.current || !state) return;
        setLoading(true);
        setError(null);
        try {
            const result = await appRef.current.callServerTool({
                name: 'data_import_fix',
                arguments: { job_id: state.job_id, instruction },
            });
            const updated = extractState(result);
            if (updated) setState(updated);
        } catch (err: any) {
            setError(err?.message ?? 'Action failed');
        } finally {
            setLoading(false);
        }
    }, [state]);

    if (connError) {
        return (
            <AppShell maxWidth={960}>
                <p style={{ color: '#dc2626' }}>{connError.message}</p>
            </AppShell>
        );
    }

    if (!state) {
        return (
            <AppShell maxWidth={960}>
                <p style={{ color: uiColors.muted, margin: 0 }}>Processing import…</p>
            </AppShell>
        );
    }

    const canImport = state.status === 'validated' || state.status === 'ready_to_execute';
    const hasErrors = state.rows.some(r =>
        r.status === 'needs_review' && r.issues.some(iss => iss.issue_type === 'error')
    );
    const isExecuted = state.status === 'executed';
    const isRolledBack = state.status === 'rolled_back';

    async function handleFix() {
        const instruction = fixInput.trim();
        if (!instruction || !appRef.current) return;
        setLoading(true);
        setError(null);
        try {
            const result = await appRef.current.callServerTool({
                name: 'data_import_fix',
                arguments: { job_id: state!.job_id, instruction },
            });
            const updated = extractState(result);
            if (updated) setState(updated);
            setFixInput('');
        } catch (err: any) {
            setError(err?.message ?? 'Fix failed');
        } finally {
            setLoading(false);
        }
    }

    async function handleExecute() {
        if (!appRef.current) return;
        setLoading(true);
        setError(null);
        try {
            const result = await appRef.current.callServerTool({
                name: 'data_import_execute',
                arguments: {
                    job_id: state!.job_id,
                    exclude_columns: excludedTargets.size > 0 ? [...excludedTargets] : undefined,
                },
            });
            const updated = extractState(result);
            if (updated) setState(updated);
        } catch (err: any) {
            setError(err?.message ?? 'Import failed');
        } finally {
            setLoading(false);
        }
    }

    return (
        <AppShell maxWidth={960}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
                <JobStatusBadge status={state.status} />
                <span style={{ fontSize: 13, color: uiColors.muted }}>
                    {state.source_filename && (
                        <span><strong style={{ color: uiColors.text }}>{state.source_filename}</strong></span>
                    )}
                    {state.entity_type && (
                        <span> · {state.entity_type}</span>
                    )}
                    <span> · {state.row_count} row{state.row_count !== 1 ? 's' : ''}</span>
                    <span> · {state.job_id}</span>
                </span>
            </div>

            {/* Issues summary */}
            <IssuesSummary summary={state.issues_summary} />

            {/* Column mapping */}
            {state.mapping && state.mapping.length > 0 && (
                <AppCard>
                    <SectionTitle>Column Mapping</SectionTitle>
                    <MappingTable mapping={state.mapping} excludedTargets={excludedTargets} onToggle={toggleColumn} />
                </AppCard>
            )}

            {/* Data grid */}
            <AppCard>
                <SectionTitle>Data ({state.rows.length} rows)</SectionTitle>
                <DataGrid rows={state.rows} mapping={state.mapping} status={state.status} excludedTargets={excludedTargets} />
                <AutoFixLog rows={state.rows} />
            </AppCard>

            {/* Suggestions carousel */}
            {!isExecuted && !isRolledBack && (
                state.batch_questions.length > 0
                    ? <SuggestionCarousel
                        questions={state.batch_questions}
                        onAction={handleQuickAction}
                        loading={loading}
                    />
                    : canImport && !hasErrors && (
                        <div style={{
                            padding: '8px 12px', marginBottom: 12, borderRadius: 6,
                            backgroundColor: '#f0fdf4', border: '1px solid #86efac',
                            color: '#15803d', fontSize: 13, fontWeight: 500,
                        }}>
                            All rows are ready. You can import now.
                        </div>
                    )
            )}

            {/* Error display */}
            {error && (
                <div style={{
                    padding: '8px 12px', marginBottom: 12, borderRadius: 6,
                    backgroundColor: '#fef2f2', border: '1px solid #fca5a5',
                    color: '#dc2626', fontSize: 13,
                }}>
                    {error}
                </div>
            )}

            {/* Fix + Import controls */}
            {canImport && !isExecuted && (
                <>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                        <input
                            type="text"
                            value={fixInput}
                            onChange={(e) => setFixInput(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') handleFix(); }}
                            placeholder="Type a fix instruction (e.g. 'merge the duplicates, use the longer name')"
                            disabled={loading}
                            style={{
                                flex: 1, padding: '8px 12px', fontSize: 13,
                                border: `1px solid ${uiColors.inputBorder}`,
                                borderRadius: 6, backgroundColor: uiColors.inputBg,
                                color: uiColors.text, outline: 'none',
                            }}
                        />
                        <SecondaryButton onClick={handleFix}>
                            {loading ? 'Applying…' : 'Fix'}
                        </SecondaryButton>
                    </div>
                    <ActionRow>
                        <PrimaryButton
                            onClick={handleExecute}
                            disabled={loading || hasErrors}
                            backgroundColor="#16a34a"
                        >
                            {loading ? 'Importing…' : `Import ${state.rows.filter(r => r.status === 'ready' || r.status === 'auto_fixed' || r.status === 'needs_review').length} records`}
                        </PrimaryButton>
                    </ActionRow>
                </>
            )}

            {/* Post-execution summary */}
            {isExecuted && (
                <AppCard marginBottom={0}>
                    <SectionTitle>Import Complete</SectionTitle>
                    <p style={{ margin: 0, fontSize: 13, color: uiColors.text }}>
                        {state.rows.filter(r => r.created_entity_id).length} {state.entity_type} record(s) created successfully.
                    </p>
                </AppCard>
            )}

            {isRolledBack && (
                <AppCard marginBottom={0}>
                    <SectionTitle>Import Rolled Back</SectionTitle>
                    <p style={{ margin: 0, fontSize: 13, color: '#dc2626' }}>
                        All created records have been removed.
                    </p>
                </AppCard>
            )}

        </AppShell>
    );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractState(params: any): StagingState | null {
    if (!params) return null;

    // structuredContent path
    const sc = params.structuredContent;
    if (sc && typeof sc === 'object' && sc.job_id) return sc as StagingState;

    // content array path (text items with JSON)
    const content = params.content;
    if (Array.isArray(content)) {
        for (const item of content) {
            if (item?.type === 'text' && typeof item.text === 'string') {
                try {
                    const parsed = JSON.parse(item.text);
                    if (parsed?.job_id) return parsed as StagingState;
                } catch { /* ignore */ }
            }
        }
    }

    // Direct object
    if (params.job_id) return params as StagingState;

    return null;
}
