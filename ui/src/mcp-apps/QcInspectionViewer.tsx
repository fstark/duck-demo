import { useEffect, useState } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import { AppShell, AppCard, SectionTitle, uiColors } from './shared/ui';

// ── Types ────────────────────────────────────────────────────────────────────

interface Finding {
    id?: string;
    finding_type: string;
    severity: 'critical' | 'major' | 'minor';
    confidence?: number;
    description?: string;
    location_hint?: string | null;
    image_ref?: string | null;
}

interface InspectionResult {
    id?: string;
    qc_hold_batch_id?: string;
    production_order_id?: string;
    model_name?: string;
    status?: string;
    decision: 'pass' | 'partial_scrap' | 'full_scrap';
    confidence_overall?: number;
    decision_reason?: string;
    findings: Finding[];
}

// ── Decision badge ────────────────────────────────────────────────────────────

const DECISION_STYLES: Record<string, { bg: string; border: string; color: string; label: string }> = {
    pass:          { bg: '#f0fdf4', border: '#86efac', color: '#15803d', label: '✓ Pass'         },
    partial_scrap: { bg: '#fffbeb', border: '#fcd34d', color: '#b45309', label: '⚠ Partial Scrap' },
    full_scrap:    { bg: '#fef2f2', border: '#fca5a5', color: '#dc2626', label: '✗ Full Scrap'    },
};

const SEVERITY_COLORS: Record<string, string> = {
    critical: '#dc2626',
    major:    '#d97706',
    minor:    '#6b7280',
};

function DecisionBadge({ decision }: { decision: string }) {
    const s = DECISION_STYLES[decision] ?? { bg: '#f9fafb', border: '#e5e7eb', color: '#374151', label: decision };
    return (
        <div style={{
            display: 'inline-block',
            padding: '6px 14px',
            borderRadius: 8,
            border: `1px solid ${s.border}`,
            backgroundColor: s.bg,
            color: s.color,
            fontWeight: 700,
            fontSize: 16,
        }}>
            {s.label}
        </div>
    );
}

function Pct({ v }: { v?: number }) {
    if (v == null) return null;
    return <span>{Math.round(v * 100)}%</span>;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function QcInspectionViewer() {
    const [result, setResult] = useState<InspectionResult | null>(null);

    const { isConnected, error } = useApp({
        appInfo: { name: 'QcInspectionViewer', version: '1.0.0' },
        capabilities: {},
        onAppCreated: (app) => {
            app.ontoolresult = (params: any) => {
                // Prefer structuredContent; fall back to content[0].text JSON
                let data: InspectionResult | null = null;
                if (params?.structuredContent?.decision) {
                    data = params.structuredContent as InspectionResult;
                } else if (Array.isArray(params?.content)) {
                    for (const item of params.content) {
                        if (item?.type === 'text') {
                            try {
                                const parsed = JSON.parse(item.text);
                                if (parsed?.decision) { data = parsed; break; }
                            } catch { /* ignore */ }
                        }
                    }
                }
                if (data) setResult(data);
            };
        },
    });

    // Keep TypeScript happy — isConnected drives no layout change here
    void isConnected;

    if (error) {
        return (
            <AppShell maxWidth={560}>
                <p style={{ color: '#dc2626' }}>{error.message}</p>
            </AppShell>
        );
    }

    if (!result) {
        return (
            <AppShell maxWidth={560}>
                <p style={{ color: uiColors.muted, margin: 0 }}>Running AI inspection…</p>
            </AppShell>
        );
    }

    const findings = result.findings ?? [];

    return (
        <AppShell maxWidth={560}>

            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <DecisionBadge decision={result.decision} />
                {result.confidence_overall != null && (
                    <span style={{ fontSize: 14, color: uiColors.muted }}>
                        Confidence: <Pct v={result.confidence_overall} />
                    </span>
                )}
            </div>

            {/* Context */}
            {(result.production_order_id || result.qc_hold_batch_id) && (
                <div style={{ fontSize: 13, color: uiColors.muted, marginBottom: 14 }}>
                    {result.production_order_id && <span>MO: <strong>{result.production_order_id}</strong></span>}
                    {result.production_order_id && result.qc_hold_batch_id && <span> · </span>}
                    {result.qc_hold_batch_id && <span>Batch: <strong>{result.qc_hold_batch_id}</strong></span>}
                    {result.model_name && <span style={{ marginLeft: 8 }}>· {result.model_name}</span>}
                </div>
            )}

            {/* Decision reason */}
            {result.decision_reason && (
                <AppCard marginBottom={14}>
                    <SectionTitle>Decision Reason</SectionTitle>
                    <p style={{ margin: 0, fontSize: 14, color: uiColors.text, lineHeight: 1.5 }}>
                        {result.decision_reason}
                    </p>
                </AppCard>
            )}

            {/* Findings */}
            {findings.length > 0 && (
                <AppCard marginBottom={0}>
                    <SectionTitle>Findings ({findings.length})</SectionTitle>
                    {findings.map((f, i) => (
                        <div key={f.id ?? i} style={{
                            backgroundColor: uiColors.inputBg,
                            border: `1px solid ${uiColors.cardBorder}`,
                            borderRadius: 6,
                            padding: '10px 12px',
                            marginBottom: i < findings.length - 1 ? 8 : 0,
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                <span style={{
                                    fontSize: 11,
                                    fontWeight: 700,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    color: SEVERITY_COLORS[f.severity] ?? uiColors.muted,
                                }}>
                                    {f.severity}
                                </span>
                                <span style={{ fontSize: 12, color: uiColors.muted }}>
                                    {f.finding_type.replace(/_/g, ' ')}
                                </span>
                                {f.confidence != null && (
                                    <span style={{ fontSize: 11, color: uiColors.muted, marginLeft: 'auto' }}>
                                        <Pct v={f.confidence} />
                                    </span>
                                )}
                            </div>
                            {f.description && (
                                <p style={{ margin: 0, fontSize: 13, color: uiColors.text, lineHeight: 1.45 }}>
                                    {f.description}
                                </p>
                            )}
                            {f.location_hint && (
                                <p style={{ margin: '4px 0 0', fontSize: 12, color: uiColors.muted }}>
                                    Location: {f.location_hint}
                                </p>
                            )}
                        </div>
                    ))}
                </AppCard>
            )}

            {findings.length === 0 && result.decision === 'pass' && (
                <div style={{
                    border: '1px solid #bbf7d0',
                    backgroundColor: '#f0fdf4',
                    borderRadius: 8,
                    padding: '10px 14px',
                    color: '#166534',
                    fontSize: 14,
                }}>
                    No defects found. All units meet quality standards.
                </div>
            )}

        </AppShell>
    );
}
