# UI Design Principles

## Overview

This document defines the UI patterns and conventions used throughout the application to ensure consistency and maintainability.

## Layout Structure

### Dashboard (Home Page)
- Grid of cards displaying key metrics
- Each card shows:
  - Title (entity type)
  - Large count number
  - Descriptive text
  - "View [entity]" button to navigate to list

### Navigation Tabs
- Horizontal navigation bar at the top
- Active tab: dark background (`bg-slate-900`) with white text
- Inactive tabs: light gray background (`bg-slate-100`) with hover effect
- Clicking a tab clears navigation context

### List Pages
- Page title (e.g., "Sales Orders", "Items")
- Single card containing a sortable table
- Entire rows are clickable to navigate to detail view
- When row is clicked, stores list context for navigation

### Detail Pages
- Page title
- Back button: contextual based on referrer
  - "← Back to [referring page]" if navigated from another detail page
  - "← Back to [entity type]" if navigated from list
- Navigation controls (when coming from list):
  - Previous/Next buttons
  - Position indicator (e.g., "3 of 15")
- Content cards with related information

## Tables

### Standard Features
- Sortable columns (indicated by header styling)
- Clickable rows (hover effect: `hover:bg-slate-50`)
- Consistent column rendering

### Sorting Behavior
- First click: sort ascending (or default direction)
- Second click: sort descending
- Third click: remove sort
- Some columns have default descending sort (dates, ETA)

### Data Rendering Rules

#### Empty/Null Values
Display as long dash: `—`
- Applies to: missing text, null prices, empty dates

#### Numeric Zero
Display as long dash for stock quantities: `—`
- Non-zero numbers display normally

#### Currency
Format: `{amount} €`
- Use `formatPrice()` utility from `utils/currency.ts`
- Handles null values (returns `—`)
- Example: `19 €`, `13.5 €`

#### Status Fields
Display as badges using `<Badge>` component
- Applies to:
  - Order fulfillment state
  - Item type
  - Shipment status
- Styling: colored background with rounded corners

#### Related Entities
Display as clickable links in brand color
- Customer names in orders
- Item SKUs
- Styling: `text-brand-600 hover:underline`
- Click behavior: sets referrer context before navigation

#### Multi-line Cells
Stack vertically when showing primary + secondary info
- Primary: regular text
- Secondary: smaller gray text (`text-xs text-slate-500`)
- Example: Item SKU + name, Customer name + company

## Navigation Context

### List Context
Tracks position when navigating from list to detail:
```typescript
{
  listType: 'customers' | 'items' | 'orders' | 'shipments' | 'production',
  items: Array,
  currentIndex: number
}
```

Enables:
- Previous/Next navigation in detail pages
- Position indicator
- Maintaining sort order

### Referrer Context
Tracks origin when navigating between entities:
```typescript
{
  page: string,     // e.g., 'orders'
  id?: string,      // e.g., 'SO-1037'
  label?: string    // e.g., 'Order SO-1037'
}
```

Enables:
- Contextual back button text
- Return to specific detail page vs. list

### Context Clearing
- Navigation tabs: clear both contexts
- Detail page back button: clear referrer
- List page: clear referrer

## Component Guidelines

### Cards
- White background with shadow
- Padding for content
- Optional title prop
- Used for: dashboard metrics, detail page sections

### Buttons
- Primary action: brand color link with underline on hover
- Navigation: Previous/Next with rounded borders
- Disabled state: opacity reduced, cursor not-allowed

### Loading States
- Display in card: "Loading [entity]..."
- Gray text (`text-slate-500`)

### Error States
- Display in card: error message
- Red text (`text-red-600`)
- Include back/retry button

## Code Organization

### Page Structure
- List pages: `{Entity}ListPage.tsx`
- Detail pages: `{Entity}DetailPage.tsx`
- Location: `ui/src/pages/`

### Shared Utilities
- Currency: `ui/src/utils/currency.ts`
- Navigation: `ui/src/contexts/NavigationContext.tsx`

### Component Library
- `Card.tsx`: Container component
- `Table.tsx`: Sortable table with click handlers
- `Badge.tsx`: Status indicator
- `Layout.tsx`: Page wrapper with navigation

## Consistency Checklist

When adding a new entity page:
- [ ] Create list page with sortable table
- [ ] Create detail page with back button
- [ ] Add to navigation tabs
- [ ] Add to dashboard (if applicable)
- [ ] Use badges for status fields
- [ ] Format currency with `formatPrice()`
- [ ] Display null values as `—`
- [ ] Make related entities clickable with referrer tracking
- [ ] Support prev/next navigation from list
- [ ] Handle loading and error states
