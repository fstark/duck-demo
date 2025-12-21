import { createContext, useContext, useState, ReactNode } from 'react'

export interface NavigationListContext<T = any> {
    listType: string // e.g., 'customers', 'customer-orders', 'items'
    items: T[] // The list of items
    currentIndex: number // Current position in the list
    filters?: Record<string, any> // Optional filters applied to this list
}

export interface NavigationReferrer {
    page: string // e.g., 'orders', 'shipments'
    id?: string // The ID of the referring item
    label?: string // Display label for the back link
}

interface NavigationContextType {
    listContext: NavigationListContext | null
    setListContext: (context: NavigationListContext | null) => void
    clearListContext: () => void
    referrer: NavigationReferrer | null
    setReferrer: (referrer: NavigationReferrer | null) => void
}

const NavigationContext = createContext<NavigationContextType | undefined>(undefined)

export function NavigationProvider({ children }: { children: ReactNode }) {
    const [listContext, setListContext] = useState<NavigationListContext | null>(null)
    const [referrer, setReferrer] = useState<NavigationReferrer | null>(null)

    const clearListContext = () => {
        setListContext(null)
        setReferrer(null)
    }

    return (
        <NavigationContext.Provider value={{ listContext, setListContext, clearListContext, referrer, setReferrer }}>
            {children}
        </NavigationContext.Provider>
    )
}

export function useNavigation() {
    const context = useContext(NavigationContext)
    if (context === undefined) {
        throw new Error('useNavigation must be used within a NavigationProvider')
    }
    return context
}
