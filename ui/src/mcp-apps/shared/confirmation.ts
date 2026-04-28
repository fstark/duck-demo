export interface ConfirmationField {
    name: string;
    label: string;
    type: string;
    value: unknown;
    required?: boolean;
    help_text?: string;
    group?: string;
    display_order?: number;
    options?: string[];
}

export interface ConfirmationMetadata {
    original_tool: string;
    title: string;
    description: string;
    category: string;
    fields: ConfirmationField[];
    arguments: Record<string, unknown>;
}

type ToolCaller = {
    callServerTool(input: { name: string; arguments: Record<string, unknown> }): Promise<unknown>;
};

export async function runGenericConfirmAction(
    app: ToolCaller,
    confirmation: Pick<ConfirmationMetadata, 'original_tool' | 'arguments'>,
): Promise<Record<string, unknown> | null> {
    const response = await app.callServerTool({
        name: 'generic_confirm_action',
        arguments: {
            original_tool: confirmation.original_tool,
            arguments: confirmation.arguments,
        },
    });

    return extractExecutionResult(response);
}

export function extractExecutionResult(response: unknown): Record<string, unknown> | null {
    const maybeObj = response as Record<string, unknown> | null | undefined;
    const structured = maybeObj?.structuredContent;
    if (structured && typeof structured === 'object') {
        return structured as Record<string, unknown>;
    }

    const content = maybeObj?.content;
    if (Array.isArray(content)) {
        for (const item of content) {
            if (!item || typeof item !== 'object') continue;
            const maybeText = item as { type?: unknown; text?: unknown };
            if (maybeText.type !== 'text' || typeof maybeText.text !== 'string') continue;
            try {
                const parsed = JSON.parse(maybeText.text);
                if (parsed && typeof parsed === 'object') {
                    return parsed as Record<string, unknown>;
                }
            } catch {
                return { message: maybeText.text };
            }
        }
    }

    if (maybeObj && typeof maybeObj === 'object') {
        return maybeObj;
    }

    return null;
}

export function getResultLines(result: Record<string, unknown> | null): Array<[string, string]> {
    if (!result) return [];

    const preferredKeys = [
        'shipment_id', 'sales_order_id', 'invoice_id', 'quote_id', 'production_order_id',
        'purchase_order_id', 'customer_id', 'email_id', 'status', 'message',
    ];

    const lines: Array<[string, string]> = [];
    for (const key of preferredKeys) {
        const value = result[key];
        if (value !== null && value !== undefined && value !== '') {
            lines.push([toLabel(key), String(value)]);
        }
    }

    if (lines.length > 0) return lines;

    return Object.entries(result)
        .filter(([, value]) => value !== null && value !== undefined && value !== '' && typeof value !== 'object')
        .slice(0, 6)
        .map(([key, value]) => [toLabel(key), String(value)]);
}

function toLabel(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
