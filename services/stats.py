"""Service for statistics operations."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Union

from db import dict_rows
from services._base import db_conn


def get_statistics(
        entity: str,
        metric: str,
        group_by: Optional[Union[str, List[str]]],
        field: Optional[str],
        status: Optional[str],
        item_type: Optional[str],
        warehouse: Optional[str],
        city: Optional[str],
        item_ids: Optional[List[str]],
        limit: int,
        return_chart: Optional[str] = None,
        chart_title: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get flexible statistics for any entity, optionally returning a chart."""
        import config as cfg

        entity_config = {
            "customers": {"table": "customers", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["city", "company"], "date_fields": ["created_at"]},
            "sales_orders": {"table": "sales_orders", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["status", "customer_id"], "date_fields": ["created_at", "requested_delivery_date"]},
            "sales_order_lines": {"table": "sales_order_lines", "join": "LEFT JOIN sales_orders ON sales_order_lines.sales_order_id = sales_orders.id", "field_mapping": {}, "date_field_table": "sales_orders", "valid_fields": ["qty", "line_total"], "valid_groups": ["sales_order_id", "item_id"], "date_fields": ["created_at"]},
            "items": {"table": "items", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["unit_price"], "valid_groups": ["type"], "date_fields": []},
            "stock": {"table": "stock", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["on_hand"], "valid_groups": ["warehouse", "location", "item_id"], "date_fields": []},
            "production_orders": {"table": "production_orders", "join": "LEFT JOIN recipes ON production_orders.recipe_id = recipes.id", "field_mapping": {"qty": "recipes.output_qty"}, "date_field_table": None, "valid_fields": ["id", "qty"], "valid_groups": ["status", "item_id"], "date_fields": ["started_at", "completed_at", "eta_finish", "eta_ship"]},
            "shipments": {"table": "shipments", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["id"], "valid_groups": ["status"], "date_fields": ["planned_departure", "planned_arrival"]},
            "shipment_lines": {"table": "shipment_lines", "join": "LEFT JOIN shipments ON shipment_lines.shipment_id = shipments.id", "field_mapping": {}, "date_field_table": "shipments", "valid_fields": ["qty"], "valid_groups": ["shipment_id", "item_id"], "date_fields": ["planned_departure", "planned_arrival"]},
            "purchase_orders": {"table": "purchase_orders", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["qty"], "valid_groups": ["status", "item_id", "supplier_id"], "date_fields": ["ordered_at", "expected_delivery", "received_at"]},
            "invoices": {"table": "invoices", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["total", "subtotal"], "valid_groups": ["status", "customer_id"], "date_fields": ["invoice_date", "due_date", "issued_at", "paid_at", "created_at"]},
            "payments": {"table": "payments", "join": None, "field_mapping": {}, "date_field_table": None, "valid_fields": ["amount"], "valid_groups": ["invoice_id", "payment_method"], "date_fields": ["payment_date", "created_at"]},
        }
        if entity not in entity_config:
            return {"error": f"Invalid entity: {entity}. Valid options: {', '.join(entity_config.keys())}"}

        ecfg = entity_config[entity]
        table = ecfg["table"]
        join_clause = ecfg["join"] or ""
        field_mapping = ecfg["field_mapping"]

        if metric == "count":
            select_clause = "COUNT(*) as value"
        elif metric in ["sum", "avg", "min", "max"]:
            if not field:
                return {"error": f"Field is required for {metric} operation"}
            if field not in ecfg["valid_fields"]:
                if field == "qty" and entity == "sales_orders":
                    return {
                        "error": f"sales_orders has no qty field (quantities are in sales_order_lines). "
                                f"For quantity analysis:\n"
                                f"  - Total quantity: entity='sales_order_lines', metric='sum', field='qty'\n"
                                f"  - By item: add group_by='item_id'\n"
                                f"  - By order: add group_by='sales_order_id'"
                    }
                elif field == "qty" and entity == "shipments":
                    return {
                        "error": f"shipments has no qty field (quantities are in shipment_lines). "
                                f"For quantity analysis:\n"
                                f"  - Total quantity: entity='shipment_lines', metric='sum', field='qty'\n"
                                f"  - By item: add group_by='item_id'\n"
                                f"  - By shipment: add group_by='shipment_id'"
                    }
                else:
                    return {"error": f"Invalid field '{field}' for entity '{entity}'. Valid: {ecfg['valid_fields']}"}
            actual_field = field_mapping.get(field, field)
            select_clause = f"{metric.upper()}({actual_field}) as value"
        else:
            return {"error": f"Invalid metric: {metric}. Valid options: count, sum, avg, min, max"}

        filters = []
        params: List[Any] = []
        if status:
            filters.append(f"{table}.status = ?")
            params.append(status)
        if item_type:
            filters.append(f"{table}.type = ?")
            params.append(item_type)
        if warehouse:
            filters.append(f"{table}.warehouse = ?")
            params.append(warehouse)
        if city:
            filters.append(f"{table}.city = ?")
            params.append(city)
        if item_ids:
            placeholders = ",".join(["?" for _ in item_ids])
            filters.append(f"{table}.item_id IN ({placeholders})")
            params.extend(item_ids)

        # Date range filtering
        if date_from or date_to:
            if not ecfg["date_fields"]:
                return {"error": f"Entity '{entity}' has no date fields for date range filtering."}
            primary_date_field = ecfg["date_fields"][0]
            date_table = ecfg.get("date_field_table") or table
            if date_from:
                filters.append(f"DATE({date_table}.{primary_date_field}) >= ?")
                params.append(date_from)
            if date_to:
                filters.append(f"DATE({date_table}.{primary_date_field}) <= ?")
                params.append(date_to)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        with db_conn() as conn:
            if group_by:
                if isinstance(group_by, list):
                    for gb_field in group_by:
                        if gb_field not in ecfg["valid_groups"]:
                            return {"error": f"Invalid group_by field '{gb_field}' for entity '{entity}'. Valid: {ecfg['valid_groups']}"}

                    select_fields = ", ".join([f"{table}.{gb_field}" for gb_field in group_by])
                    group_fields = ", ".join([f"{table}.{gb_field}" for gb_field in group_by])
                    sql = f"SELECT {select_fields}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {group_fields} ORDER BY value DESC LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))

                    result: Dict[str, Any] = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}

                    if return_chart:
                        chart_result = _generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]

                    return result

                if ":" in group_by:
                    period, field_name = group_by.split(":", 1)
                    if field_name not in ecfg["date_fields"]:
                        if entity == "stock":
                            return {
                                "error": f"stock table has no date fields (it's a current snapshot, not historical data). "
                                        f"For inventory changes over time, use transaction tables:\n"
                                        f"  - Production: entity='production_orders', metric='sum', field='qty', group_by='date:completed_at'\n"
                                        f"  - Shipments: entity='shipment_lines', metric='sum', field='qty', group_by='date:planned_departure'\n"
                                        f"  - Purchases: entity='purchase_orders', metric='sum', field='qty', group_by='date:received_at'"
                            }
                        return {"error": f"Invalid date field '{field_name}' for entity '{entity}'. Valid: {ecfg['date_fields']}"}

                    date_table = ecfg.get("date_field_table") or table

                    if period == "date":
                        group_expr = f"DATE({date_table}.{field_name})"
                        group_label = "date"
                    elif period == "month":
                        group_expr = f"strftime('%Y-%m', {date_table}.{field_name})"
                        group_label = "month"
                    elif period == "year":
                        group_expr = f"strftime('%Y', {date_table}.{field_name})"
                        group_label = "year"
                    else:
                        return {"error": f"Invalid time period '{period}'. Valid: date, month, year"}

                    sql = f"SELECT {group_expr} as {group_label}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {group_expr} ORDER BY {group_label} LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))

                    result = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}

                    if return_chart:
                        chart_result = _generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]

                    return result
                else:
                    if group_by not in ecfg["valid_groups"]:
                        return {"error": f"Invalid group_by '{group_by}' for entity '{entity}'. Valid: {ecfg['valid_groups']}"}
                    sql = f"SELECT {table}.{group_by}, {select_clause} FROM {table} {join_clause} {where_clause} GROUP BY {table}.{group_by} ORDER BY value DESC LIMIT ?"
                    params.append(limit)
                    rows = dict_rows(conn.execute(sql, params))

                    result = {"entity": entity, "metric": metric, "group_by": group_by, "results": rows}

                    if return_chart:
                        chart_result = _generate_chart_from_results(
                            return_chart, rows, group_by, chart_title, entity, metric
                        )
                        if "error" in chart_result:
                            return chart_result
                        result["chart_url"] = chart_result["chart_url"]
                        result["chart_filename"] = chart_result["chart_filename"]

                    return result
            else:
                sql = f"SELECT {select_clause} FROM {table} {join_clause} {where_clause}"
                result_row = conn.execute(sql, params).fetchone()
                return {"entity": entity, "metric": metric, "value": result_row["value"] if result_row["value"] is not None else 0}

def _generate_chart_from_results(
        chart_type: str,
        rows: List[Dict[str, Any]],
        group_by: Union[str, List[str]],
        chart_title: Optional[str],
        entity: str,
        metric: str
    ) -> Dict[str, Any]:
        """Generate chart from query results."""
        from services.chart import chart_service

        if not rows:
            return {"error": "No data to chart"}

        if isinstance(group_by, list):
            if len(group_by) != 2:
                return {"error": "Multi-dimensional charting requires exactly 2 group_by fields"}

            label_field = group_by[0]
            series_field = group_by[1]

            labels_set = set()
            series_set = set()
            for row in rows:
                labels_set.add(str(row[label_field]))
                series_set.add(str(row[series_field]))

            labels = sorted(list(labels_set))
            series_names = sorted(list(series_set))

            series_data = []
            for series_name in series_names:
                values = []
                for label in labels:
                    value = 0
                    for row in rows:
                        if str(row[label_field]) == label and str(row[series_field]) == series_name:
                            value = row.get("value", 0)
                            break
                    values.append(value)
                series_data.append({"name": series_name, "values": values})

            title = chart_title or f"{entity.replace('_', ' ').title()} by {label_field} and {series_field}"
            chart_result = chart_service.generate_chart(
                chart_type=chart_type,
                labels=labels,
                series=series_data,
                title=title
            )
            return {
                "chart_url": chart_result["url"],
                "chart_filename": chart_result["filename"]
            }

        else:
            if ":" in group_by:
                period = group_by.split(":", 1)[0]
                label_field = period
            else:
                label_field = group_by

            labels = [str(row[label_field]) for row in rows]
            values = [row.get("value", 0) for row in rows]

            title = chart_title or f"{entity.replace('_', ' ').title()} by {label_field}"
            chart_result = chart_service.generate_chart(
                chart_type=chart_type,
                labels=labels,
                values=values,
                title=title
            )
            return {
                "chart_url": chart_result["url"],
                "chart_filename": chart_result["filename"]
            }


# Namespace for backward compatibility
stats_service = SimpleNamespace(
    get_statistics=get_statistics,
    _generate_chart_from_results=_generate_chart_from_results,
)
StatsService = stats_service
