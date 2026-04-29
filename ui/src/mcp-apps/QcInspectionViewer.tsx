import { useEffect, useRef, useState } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';
import { AppShell, AppCard, SectionTitle, PrimaryButton, uiColors } from './shared/ui';

// ── Types ────────────────────────────────────────────────────────────────────

interface Duck {
    bbox: [number, number, number, number]; // [x1, y1, x2, y2] normalised to [0, 1]
    severity: 'none' | 'minor' | 'major' | 'critical';
    defects: string[];
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
    duck_results?: Duck[];
    operator_image_uri?: string;
    reference_image_uri?: string;
}

// ── Severity helpers ──────────────────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = {
    none:     '#22c55e',
    minor:    '#f97316',
    major:    '#ef4444',
    critical: '#dc2626',
};
const SEV_ORDER = ['none', 'minor', 'major', 'critical'] as const;

function cycleSeverity(sev: string): string {
    const idx = SEV_ORDER.indexOf(sev as typeof SEV_ORDER[number]);
    return SEV_ORDER[(idx + 1) % SEV_ORDER.length];
}

// ── Decision badge ────────────────────────────────────────────────────────────

const DECISION_STYLES: Record<string, { bg: string; border: string; color: string; label: string }> = {
    pass:          { bg: '#f0fdf4', border: '#86efac', color: '#15803d', label: '✓ Pass'          },
    partial_scrap: { bg: '#fffbeb', border: '#fcd34d', color: '#b45309', label: '⚠ Partial Scrap'  },
    full_scrap:    { bg: '#fef2f2', border: '#fca5a5', color: '#dc2626', label: '✗ Full Scrap'     },
};

function DecisionBadge({ decision }: { decision: string }) {
    const s = DECISION_STYLES[decision] ?? { bg: '#f9fafb', border: '#e5e7eb', color: '#374151', label: decision };
    return (
        <div style={{
            display: 'inline-block', padding: '6px 14px', borderRadius: 8,
            border: `1px solid ${s.border}`, backgroundColor: s.bg, color: s.color,
            fontWeight: 700, fontSize: 16,
        }}>
            {s.label}
        </div>
    );
}

// ── Right panel: submitted image with bbox canvas overlay ─────────────────────

function DuckImage({
    imageUri, ducks, overrides, hoveredDuck, onHover, onLeave, onClickDuck,
}: {
    imageUri: string;
    ducks: Duck[];
    overrides: Record<number, string>;
    hoveredDuck: number | null;
    onHover: (idx: number) => void;
    onLeave: () => void;
    onClickDuck: (idx: number) => void;
}) {
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [displaySize, setDisplaySize] = useState<{ w: number; h: number } | null>(null);

    // Redraw boxes whenever relevant state changes
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !displaySize) return;
        // Set canvas internal resolution to match the displayed image pixel size
        // This avoids any stretch mismatch between canvas and CSS-scaled image
        const dpr = window.devicePixelRatio || 1;
        canvas.width = displaySize.w * dpr;
        canvas.height = displaySize.h * dpr;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, displaySize.w, displaySize.h);
        ducks.forEach((duck, idx) => {
            const sev = overrides[idx] ?? duck.severity;
            const color = SEV_COLOR[sev] ?? '#888';
            const [x1, y1, x2, y2] = duck.bbox;
            const px = x1 * displaySize.w;
            const py = y1 * displaySize.h;
            const pw = (x2 - x1) * displaySize.w;
            const ph = (y2 - y1) * displaySize.h;
            ctx.globalAlpha = hoveredDuck === idx ? 0.28 : 0.14;
            ctx.fillStyle = color;
            ctx.fillRect(px, py, pw, ph);
            ctx.globalAlpha = hoveredDuck === idx ? 1 : 0.8;
            ctx.strokeStyle = color;
            ctx.lineWidth = hoveredDuck === idx ? 3.5 : 2;
            ctx.strokeRect(px, py, pw, ph);
        });
        ctx.globalAlpha = 1;
    }, [ducks, overrides, hoveredDuck, displaySize]);

    function updateDisplaySize() {
        const img = imgRef.current;
        if (img && img.complete && img.naturalWidth) {
            setDisplaySize({ w: img.clientWidth, h: img.clientHeight });
        }
    }

    useEffect(() => {
        updateDisplaySize();
        window.addEventListener('resize', updateDisplaySize);
        return () => window.removeEventListener('resize', updateDisplaySize);
    }, [imageUri]);

    return (
        <div style={{ position: 'relative', lineHeight: 0 }}>
            <img
                ref={imgRef}
                src={imageUri}
                alt="Submitted batch"
                onLoad={updateDisplaySize}
                style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 6 }}
            />
            {displaySize && (
                <canvas
                    ref={canvasRef}
                    style={{
                        position: 'absolute', top: 0, left: 0,
                        width: displaySize.w, height: displaySize.h,
                        pointerEvents: 'none',
                    }}
                />
            )}
            {/* Transparent hit areas — percentage-positioned over each duck */}
            {ducks.map((duck, idx) => {
                const [x1, y1, x2, y2] = duck.bbox;
                return (
                    <div
                        key={idx}
                        style={{
                            position: 'absolute',
                            left: `${x1 * 100}%`, top: `${y1 * 100}%`,
                            width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%`,
                            cursor: 'pointer', boxSizing: 'border-box',
                        }}
                        onMouseEnter={() => onHover(idx)}
                        onMouseLeave={onLeave}
                        onClick={() => onClickDuck(idx)}
                    />
                );
            })}
        </div>
    );
}

// ── Left panel: reference image or duck defect detail ────────────────────────

function LeftPanel({
    referenceUri, hoveredDuck, ducks, overrides,
}: {
    referenceUri: string | undefined;
    hoveredDuck: number | null;
    ducks: Duck[];
    overrides: Record<number, string>;
}) {
    if (hoveredDuck !== null) {
        const duck = ducks[hoveredDuck];
        if (!duck) return null;
        const sev = overrides[hoveredDuck] ?? duck.severity;
        const color = SEV_COLOR[sev] ?? '#888';
        return (
            <div>
                <div style={{
                    backgroundColor: `${color}18`,
                    border: `2px solid ${color}`,
                    borderRadius: 8, padding: '12px 14px',
                }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color, marginBottom: 6 }}>
                        Duck {hoveredDuck + 1} — {sev.toUpperCase()}
                    </div>
                    {duck.defects.length > 0 ? (
                        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: uiColors.text, lineHeight: 1.55 }}>
                            {duck.defects.map((d, i) => <li key={i}>{d}</li>)}
                        </ul>
                    ) : (
                        <p style={{ margin: 0, fontSize: 13, color: uiColors.muted }}>No defects — quality OK.</p>
                    )}
                </div>
                <p style={{ marginTop: 8, marginBottom: 0, fontSize: 11, color: uiColors.muted }}>
                    Click the box on the right to cycle severity
                </p>
            </div>
        );
    }
    if (referenceUri) {
        return (
            <img
                src={referenceUri}
                alt="Reference product"
                style={{ width: '100%', height: 'auto', borderRadius: 6, display: 'block' }}
            />
        );
    }
    return <p style={{ color: uiColors.muted, fontSize: 13, margin: 0 }}>No reference image.</p>;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function QcInspectionViewer() {
    const [result, setResult] = useState<InspectionResult | null>(null);
    const [overrides, setOverrides] = useState<Record<number, string>>({});
    const [hoveredDuck, setHoveredDuck] = useState<number | null>(null);

    const { isConnected, error } = useApp({
        appInfo: { name: 'QcInspectionViewer', version: '2.0.0' },
        capabilities: {},
        onAppCreated: (app) => {
            app.ontoolresult = (params: any) => {
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
                if (data) {
                    console.log('[QC] duck_results:', JSON.stringify(data.duck_results, null, 2));
                    setResult(data); setOverrides({});
                }
            };
        },
    });

    void isConnected;

    if (error) {
        return (
            <AppShell maxWidth={920}>
                <p style={{ color: '#dc2626' }}>{error.message}</p>
            </AppShell>
        );
    }

    if (!result) {
        return (
            <AppShell maxWidth={920}>
                <p style={{ color: uiColors.muted, margin: 0 }}>Running AI inspection…</p>
            </AppShell>
        );
    }

    const ducks: Duck[] = Array.isArray(result.duck_results) ? result.duck_results : [];

    function getEffectiveSeverity(duck: Duck, idx: number): string {
        return overrides[idx] ?? duck.severity;
    }

    const passCount = ducks.filter((d, i) => getEffectiveSeverity(d, i) !== 'critical').length;
    const hasImages = !!(result.reference_image_uri || result.operator_image_uri);

    function handleClickDuck(idx: number) {
        const current = getEffectiveSeverity(ducks[idx], idx);
        setOverrides(prev => ({ ...prev, [idx]: cycleSeverity(current) }));
    }

    return (
        <AppShell maxWidth={920}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <DecisionBadge decision={result.decision} />
                <span style={{ fontSize: 13, color: uiColors.muted }}>
                    {result.production_order_id && (
                        <span>MO: <strong style={{ color: uiColors.text }}>{result.production_order_id}</strong></span>
                    )}
                    {result.production_order_id && result.qc_hold_batch_id && <span> · </span>}
                    {result.qc_hold_batch_id && (
                        <span>Batch: <strong style={{ color: uiColors.text }}>{result.qc_hold_batch_id}</strong></span>
                    )}
                </span>
            </div>

            {/* Decision reason */}
            {result.decision_reason && (
                <AppCard marginBottom={14}>
                    <p style={{ margin: 0, fontSize: 13, color: uiColors.text, lineHeight: 1.5 }}>
                        {result.decision_reason}
                    </p>
                </AppCard>
            )}

            {/* Two-panel image view */}
            {hasImages && (
                <div style={{ display: 'flex', gap: 14, marginBottom: 14, alignItems: 'flex-start' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <SectionTitle>Reference</SectionTitle>
                        <LeftPanel
                            referenceUri={result.reference_image_uri}
                            hoveredDuck={hoveredDuck}
                            ducks={ducks}
                            overrides={overrides}
                        />
                    </div>
                    {result.operator_image_uri && (
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <SectionTitle>
                                Submitted{ducks.length > 0 ? ` · ${ducks.length} duck${ducks.length !== 1 ? 's' : ''}` : ''}
                            </SectionTitle>
                            {ducks.length > 0 ? (
                                <DuckImage
                                    imageUri={result.operator_image_uri}
                                    ducks={ducks}
                                    overrides={overrides}
                                    hoveredDuck={hoveredDuck}
                                    onHover={setHoveredDuck}
                                    onLeave={() => setHoveredDuck(null)}
                                    onClickDuck={handleClickDuck}
                                />
                            ) : (
                                <img
                                    src={result.operator_image_uri}
                                    alt="Submitted batch"
                                    style={{ width: '100%', height: 'auto', borderRadius: 6, display: 'block' }}
                                />
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Severity legend + Pass button */}
            {ducks.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    {SEV_ORDER.map(sev => (
                        <span key={sev} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: uiColors.muted }}>
                            <span style={{ width: 11, height: 11, borderRadius: 2, backgroundColor: SEV_COLOR[sev], display: 'inline-block', flexShrink: 0 }} />
                            {sev}
                        </span>
                    ))}
                    <span style={{ fontSize: 12, color: uiColors.muted }}>· hover to inspect · click to cycle</span>
                    <div style={{ marginLeft: 'auto' }}>
                        <PrimaryButton backgroundColor="#16a34a" onClick={() => {}}>
                            Pass ({passCount})
                        </PrimaryButton>
                    </div>
                </div>
            )}

        </AppShell>
    );
}
