import { createContext, useContext, useState, ReactNode } from 'react'

export interface NavigationListContext<T = any> {
    listType: string // e.g., 'customers', 'customer-orders', 'items'
    items: T[] // The list of items
    currentIndex: number // Current position in the list
    filters?: Record<string, any> // Optional filters applied to this list
}

interface NavigationContextType {
    listContext: NavigationListContext | null
    setListContext: (context: NavigationListContext | null) => void
    clearListContext: () => void
}

const NavigationContext = createContext<NavigationContextType | undefined>(undefined)

export function NavigationProvider({ children }: { children: ReactNode }) {
    const [listContext, setListContext] = useState<NavigationListContext | null>(null)

    const clearListContext = () => setListContext(null)

    return (
        <NavigationContext.Provider value={{ listContext, setListContext, clearListContext }}>
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
