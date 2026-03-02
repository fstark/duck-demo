"""Service for generating chart images."""

import os
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import config

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def generate_chart(
    chart_type: str,
    labels: List[str],
    values: Optional[List[float]] = None,
    series: Optional[List[Dict[str, Any]]] = None,
    title: Optional[str] = None
) -> Dict[str, str]:
        """
        Generate a chart image and return the filename.

        Args:
            chart_type: Type of chart - pie, bar, bar_horizontal, line, scatter, area, stacked_area, stacked_bar, waterfall, treemap
            labels: List of labels for x-axis or pie slices
            values: List of numeric values (for backward compatibility, single series)
            series: List of series dicts: [{"name": "Q1", "values": [10, 20, 30]}, ...]
            title: Optional chart title

        Returns:
            Dictionary with filename and full_path
        """
        valid_types = ["pie", "bar", "bar_horizontal", "line", "scatter", "area", "stacked_area", "stacked_bar", "waterfall", "treemap"]
        if chart_type not in valid_types:
            raise ValueError(f"Unsupported chart type: {chart_type}. Valid: {', '.join(valid_types)}")

        if values is not None:
            series = [{"name": "", "values": values}]
        elif series is None:
            raise ValueError("Must provide either 'values' or 'series'")

        for s in series:
            if len(s["values"]) != len(labels):
                raise ValueError(f"Series '{s.get('name', '')}' values length must match labels length")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_uuid = str(uuid.uuid4())
        filename = f"{timestamp}_{file_uuid}.png"

        charts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "charts")
        os.makedirs(charts_dir, exist_ok=True)

        full_path = os.path.join(charts_dir, filename)

        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == "pie":
            values_list = series[0]["values"]

            def make_autopct(values):
                def autopct(pct):
                    total = sum(values)
                    val = int(round(pct * total / 100.0))
                    return f'{val}\n({pct:.1f}%)'
                return autopct

            ax.pie(values_list, labels=labels, autopct=make_autopct(values_list), startangle=90)
            ax.axis('equal')

        elif chart_type == "bar":
            x = range(len(labels))
            width = 0.8 / len(series) if len(series) > 1 else 0.6

            for idx, s in enumerate(series):
                offset = (idx - len(series) / 2 + 0.5) * width
                bars = ax.bar([i + offset for i in x], s["values"], width, label=s["name"])
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{int(height)}', ha='center', va='bottom', fontsize=8)

            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            if len(series) > 1 or series[0]["name"]:
                ax.legend()

        elif chart_type == "bar_horizontal":
            y = range(len(labels))
            height = 0.8 / len(series) if len(series) > 1 else 0.6

            for idx, s in enumerate(series):
                offset = (idx - len(series) / 2 + 0.5) * height
                bars = ax.barh([i + offset for i in y], s["values"], height, label=s["name"])
                for bar in bars:
                    width = bar.get_width()
                    ax.text(width, bar.get_y() + bar.get_height()/2.,
                           f'{int(width)}', ha='left', va='center', fontsize=8)

            ax.set_yticks(y)
            ax.set_yticklabels(labels)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()

        elif chart_type == "line":
            x = range(len(labels))

            for s in series:
                ax.plot(x, s["values"], marker='o', label=s["name"], linewidth=2)
                for i, val in enumerate(s["values"]):
                    ax.text(i, val, f'{int(val)}', ha='center', va='bottom', fontsize=8)

            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()

        elif chart_type == "scatter":
            for s in series:
                ax.scatter(range(len(labels)), s["values"], label=s["name"], s=100, alpha=0.6)

            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()

        elif chart_type == "area":
            x = range(len(labels))

            for s in series:
                ax.fill_between(x, s["values"], alpha=0.4, label=s["name"])
                ax.plot(x, s["values"], linewidth=2)

            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            if len(series) > 1 or series[0]["name"]:
                ax.legend()

        elif chart_type == "stacked_area":
            x = range(len(labels))

            cumulative = [0] * len(labels)
            for s in series:
                new_cumulative = [cumulative[i] + s["values"][i] for i in range(len(labels))]
                ax.fill_between(x, cumulative, new_cumulative, alpha=0.6, label=s["name"])
                cumulative = new_cumulative

            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
            ax.legend()

        elif chart_type == "stacked_bar":
            x = range(len(labels))
            width = 0.6

            cumulative = [0] * len(labels)
            for s in series:
                ax.bar(x, s["values"], width, bottom=cumulative, label=s["name"])
                cumulative = [cumulative[i] + s["values"][i] for i in range(len(labels))]

            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.legend()

        elif chart_type == "waterfall":
            values_list = series[0]["values"]
            cumulative = 0
            cumulative_values = []
            colors_list = []

            for val in values_list:
                cumulative_values.append(cumulative)
                cumulative += val
                colors_list.append('green' if val >= 0 else 'red')

            bars = ax.bar(range(len(labels)), values_list, bottom=cumulative_values, color=colors_list, alpha=0.7)

            for i, (bar, val) in enumerate(zip(bars, values_list)):
                height = cumulative_values[i] + val
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(val):+d}', ha='center', va='bottom' if val >= 0 else 'top', fontsize=8)

            for i in range(len(labels) - 1):
                ax.plot([i + 0.4, i + 0.6],
                       [cumulative_values[i] + values_list[i], cumulative_values[i] + values_list[i]],
                       'k--', linewidth=0.5, alpha=0.5)

            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.axhline(y=0, color='black', linewidth=0.8)

        elif chart_type == "treemap":
            import squarify

            values_list = series[0]["values"]

            filtered_data = [(label, val) for label, val in zip(labels, values_list) if val > 0]

            if not filtered_data:
                raise ValueError("Treemap requires at least one positive value")

            filtered_labels, filtered_values = zip(*filtered_data)

            chart_colors = plt.cm.Set3(range(len(filtered_labels)))

            labels_with_values = [f"{label}\n{int(val)}" for label, val in zip(filtered_labels, filtered_values)]

            squarify.plot(sizes=filtered_values, label=labels_with_values, alpha=0.8, color=chart_colors, text_kwargs={'fontsize': 9})
            ax.axis('off')

        if title:
            ax.set_title(title)

        plt.tight_layout()
        plt.savefig(full_path, dpi=100, bbox_inches='tight')
        plt.close(fig)

        return {
            "filename": filename,
            "full_path": full_path,
            "url": f"{config.API_BASE}/api/charts/{filename}"
        }


# Namespace for backward compatibility
chart_service = SimpleNamespace(
    generate_chart=generate_chart,
)
ChartService = chart_service
