import { useCallback, useEffect, useMemo, useState } from 'react';
import { useApp } from '@modelcontextprotocol/ext-apps/react';

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

export default function TariffPickerDialog() {
  const [status, setStatus] = useState<'connecting' | 'ready' | 'submitting' | 'submitted' | 'cancelled' | 'error'>('connecting');
  const [payload, setPayload] = useState<TariffPickerPayload | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [selectedCodes, setSelectedCodes] = useState<Record<number, string>>({});
  const [customCodes, setCustomCodes] = useState<Record<number, string>>({});

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
      const updatedPackages = payload.arguments.packages.map((pkg) => {
        const updatedContents = pkg.contents.map((content) => {
          const item = payload.items[itemCursor];
          const custom = (customCodes[itemCursor] || '').trim();
          const selectedCode = custom || (selectedCodes[itemCursor] || '').trim();
          const suggestion = (item?.suggestions || []).find((s) => s.code === selectedCode);

          itemCursor += 1;
          return {
            ...content,
            tariff_code: selectedCode,
            tariff_description: suggestion?.description || (content.tariff_description as string) || null,
          };
        });

        return {
          ...pkg,
          contents: updatedContents,
        };
      });

      await app.callServerTool({
        name: payload.original_tool,
        arguments: {
          ...payload.arguments,
          packages: updatedPackages,
        } as Record<string, unknown>,
      });

      setStatus('submitted');
    } catch (submitError: any) {
      setStatus('error');
      setErrorText(submitError?.message || 'Failed to submit tariff selections.');
    }
  }, [app, payload, selectedCodes, customCodes]);

  const handleCancel = useCallback(() => {
    setStatus('cancelled');
  }, []);

  const appShellStyle: React.CSSProperties = {
    padding: '24px',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    maxWidth: '640px',
    margin: '0 auto',
    color: '#111827',
  };

  const cardStyle: React.CSSProperties = {
    backgroundColor: '#f9fafb',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '14px',
  };

  if (error) {
    return (
      <div style={appShellStyle}>
        <h2 style={{ color: '#dc2626', marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>Error</h2>
        <p style={{ marginTop: 0 }}>{error.message}</p>
      </div>
    );
  }

  if (!isConnected || status === 'connecting' || !payload) {
    return (
      <div style={appShellStyle}>
        <p style={{ margin: 0, color: '#6b7280' }}>Loading tariff suggestions...</p>
      </div>
    );
  }

  if (status === 'submitted') {
    return (
      <div style={appShellStyle}>
        <h2 style={{ color: '#16a34a', marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>
          Tariff Codes Submitted
        </h2>
        <p>Shipment request was re-submitted with the selected tariff codes.</p>
      </div>
    );
  }

  if (status === 'cancelled') {
    return (
      <div style={appShellStyle}>
        <h2 style={{ color: '#6b7280', marginTop: 0, marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>
          Cancelled
        </h2>
        <p>Tariff code selection was cancelled.</p>
      </div>
    );
  }

  return (
    <div style={appShellStyle}>
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
          <div key={`${item.sku}-${idx}`} style={cardStyle}>
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
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  padding: '8px 10px',
                  backgroundColor: '#ffffff',
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
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px',
                  color: '#111827',
                  backgroundColor: '#ffffff',
                  boxSizing: 'border-box',
                }}
              />
            </div>
          </div>
        );
      })}

      {status === 'error' && <p style={{ color: '#b91c1c', marginTop: '4px' }}>{errorText}</p>}

      <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '20px' }}>
        <button
          type="button"
          onClick={handleCancel}
          style={{
            padding: '8px 16px',
            fontSize: '14px',
            fontWeight: 500,
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: '#ffffff',
            color: '#374151',
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!canSubmit || status === 'submitting'}
          onClick={handleSubmit}
          style={{
            padding: '8px 16px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            borderRadius: '6px',
            backgroundColor: canSubmit ? '#7c3aed' : '#9ca3af',
            color: '#ffffff',
            cursor: canSubmit ? 'pointer' : 'not-allowed',
          }}
        >
          {status === 'submitting' ? 'Submitting...' : 'Confirm Tariff Codes'}
        </button>
      </div>
    </div>
  );
}
