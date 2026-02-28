"""Services package — re-exports all singleton instances for backward compatibility."""

from services._base import db_conn
from services.simulation import simulation_service, SimulationService
from services.customer import customer_service, CustomerService
from services.inventory import inventory_service, InventoryService
from services.catalog import catalog_service, CatalogService
from services.pricing import pricing_service, PricingService
from services.sales import sales_service, SalesService
from services.logistics import logistics_service, LogisticsService
from services.production import production_service, ProductionService
from services.recipe import recipe_service, RecipeService
from services.purchase import purchase_service, PurchaseService
from services.messaging import messaging_service, MessagingService
from services.quote import quote_service, QuoteService
from services.invoice import invoice_service, InvoiceService
from services.document import document_service, DocumentService
from services.stats import stats_service, StatsService
from services.admin import admin_service, AdminService
from services.chart import chart_service, ChartService

__all__ = [
    "db_conn",
    "simulation_service", "SimulationService",
    "customer_service", "CustomerService",
    "inventory_service", "InventoryService",
    "catalog_service", "CatalogService",
    "pricing_service", "PricingService",
    "sales_service", "SalesService",
    "logistics_service", "LogisticsService",
    "production_service", "ProductionService",
    "recipe_service", "RecipeService",
    "purchase_service", "PurchaseService",
    "messaging_service", "MessagingService",
    "quote_service", "QuoteService",
    "invoice_service", "InvoiceService",
    "document_service", "DocumentService",
    "stats_service", "StatsService",
    "admin_service", "AdminService",
    "chart_service", "ChartService",
]
