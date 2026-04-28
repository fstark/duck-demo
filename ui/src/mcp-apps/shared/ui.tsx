import type { CSSProperties, ReactNode } from 'react';

export const uiColors = {
  text: '#111827',
  muted: '#6b7280',
  cardBg: '#f9fafb',
  cardBorder: '#e5e7eb',
  inputBg: '#ffffff',
  inputBorder: '#d1d5db',
};

export function AppShell({ children, maxWidth = 620 }: { children: ReactNode; maxWidth?: number }) {
  return <div style={shellStyle(maxWidth)}>{children}</div>;
}

export function AppCard({ children, marginBottom = 14 }: { children: ReactNode; marginBottom?: number }) {
  return <div style={cardStyle(marginBottom)}>{children}</div>;
}

export function StatusScreen({
  title,
  message,
  titleColor,
}: {
  title: string;
  message: string;
  titleColor?: string;
}) {
  return (
    <>
      <h2 style={{ color: titleColor ?? uiColors.text, marginTop: 0, marginBottom: 8, fontSize: 20, fontWeight: 600 }}>{title}</h2>
      <p style={{ marginTop: 0, color: uiColors.muted }}>{message}</p>
    </>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3
      style={{
        marginTop: 0,
        marginBottom: 10,
        fontSize: 14,
        color: '#374151',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
      }}
    >
      {children}
    </h3>
  );
}

export function ActionRow({ children, marginTop = 20 }: { children: ReactNode; marginTop?: number }) {
  return <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop }}>{children}</div>;
}

export function SecondaryButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '8px 16px',
        fontSize: 14,
        fontWeight: 500,
        border: `1px solid ${uiColors.inputBorder}`,
        borderRadius: 6,
        backgroundColor: uiColors.inputBg,
        color: '#374151',
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  );
}

export function PrimaryButton({
  children,
  onClick,
  disabled = false,
  backgroundColor = '#7c3aed',
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  backgroundColor?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '8px 16px',
        fontSize: 14,
        fontWeight: 500,
        border: 'none',
        borderRadius: 6,
        backgroundColor: disabled ? '#9ca3af' : backgroundColor,
        color: '#ffffff',
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      {children}
    </button>
  );
}

function shellStyle(maxWidth: number): CSSProperties {
  return {
    padding: 24,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    maxWidth,
    margin: '16px auto',
    color: uiColors.text,
    backgroundColor: '#ffffff',
    border: '1px solid #dbe3ee',
    borderRadius: 12,
    boxShadow: '0 10px 28px rgba(15, 23, 42, 0.14)',
  };
}

function cardStyle(marginBottom: number): CSSProperties {
  return {
    backgroundColor: uiColors.cardBg,
    border: `1px solid ${uiColors.cardBorder}`,
    borderRadius: 8,
    padding: 16,
    marginBottom,
  };
}
