"""MCP tools – chart generation."""

from typing import Any, Dict, List, Optional

from mcp_tools._common import log_tool
from services import chart_service


def register(mcp):
    """Register chart tools."""

    @mcp.tool(name="chart_generate", meta={"tags": ["shared"]})
    @log_tool("chart_generate")
    def chart_generate(
        chart_type: str,
        labels: List[str],
        values: Optional[List[float]] = None,
        series: Optional[List[Dict[str, Any]]] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a chart image and return a URL to access it.

        Parameters:
            chart_type: Type of chart - pie, bar, bar_horizontal, line, scatter, area, stacked_area, stacked_bar, waterfall, treemap
            labels: List of labels for x-axis or pie slices
            values: List of numeric values (single series, for backward compatibility)
            series: List of series dicts for multi-series charts: [{"name": "Q1", "values": [10, 20, 30]}, {"name": "Q2", "values": [15, 25, 35]}]
            title: Optional title for the chart

        Chart Types:
            - pie: Single series only, shows distribution with values and percentages
            - bar: Vertical bar chart, supports multiple series side-by-side
            - bar_horizontal: Horizontal bar chart, supports multiple series
            - line: Line chart with markers, great for trends over time
            - scatter: Scatter plot for correlations
            - area: Filled area under line, shows volume over time
            - stacked_area: Multiple series stacked, shows composition changes
            - stacked_bar: Multiple series stacked vertically
            - waterfall: Sequential changes (single series), shows cumulative effect

        Examples:
            Single series (backward compatible):
                chart_generate("pie", labels=["A", "B", "C"], values=[30, 50, 20])

            Multi-series comparison:
                chart_generate("bar", labels=["Jan", "Feb", "Mar"],
                    series=[{"name": "2025", "values": [100, 120, 140]},
                            {"name": "2026", "values": [110, 130, 150]}])

            Waterfall (sequential changes):
                chart_generate("waterfall", labels=["Start", "Sales", "Costs", "End"],
                    values=[1000, 500, -300, 1200])

        Returns:
            Dictionary with 'url' field containing the full URL to the generated chart image.
            Chart files are stored with timestamp-first filenames for easy date-based sorting and cleanup.
        """
        result = chart_service.generate_chart(chart_type, labels, values, series, title)
        return {"url": result["url"], "filename": result["filename"]}
