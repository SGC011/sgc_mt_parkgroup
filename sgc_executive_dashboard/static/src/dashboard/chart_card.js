import { Component, onWillStart, onMounted, onWillUnmount, useRef, onWillUpdateProps } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { formatValue, accentColor, paletteFor, withAlpha } from "./utils";

export class SgcChartCard extends Component {
    static template = "sgc_executive_dashboard.ChartCard";
    static props = {
        chart: { type: Object },
        currency: { type: Object, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onWillStart(() => loadJS("/web/static/lib/Chart/Chart.js"));
        onMounted(() => this.render_());
        onWillUpdateProps(() => this.destroy_());
        onWillUnmount(() => this.destroy_());
    }

    destroy_() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    get config() {
        const c = this.props.chart;
        const accent = accentColor(c.accent);
        const isCategorical = ["doughnut", "pie", "polarArea"].includes(c.type);
        const currency = this.props.currency;

        const multiSeries = c.datasets.length > 1;
        const seriesColors = multiSeries ? paletteFor(c.accent, c.datasets.length) : [];

        const datasets = c.datasets.map((ds, idx) => {
            if (isCategorical) {
                return {
                    ...ds,
                    backgroundColor: paletteFor(c.accent, ds.data.length),
                    borderColor: "transparent",
                    borderWidth: 0,
                    hoverOffset: 6,
                };
            }
            if (c.type === "line") {
                return {
                    ...ds,
                    borderColor: accent,
                    backgroundColor: withAlpha(accent, 0.14),
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.38,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointBackgroundColor: accent,
                };
            }
            // Multi-series bars (e.g. the stacked milestone breakdown) need a
            // distinct colour per series or the segments are indistinguishable.
            const barColor = multiSeries ? seriesColors[idx] : accent;
            return {
                ...ds,
                backgroundColor: withAlpha(barColor, 0.85),
                hoverBackgroundColor: barColor,
                borderRadius: 6,
                borderSkipped: false,
                maxBarThickness: 28,
            };
        });

        return {
            type: c.type,
            data: { labels: c.labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: c.horizontal ? "y" : "x",
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        display: isCategorical || multiSeries,
                        position: "bottom",
                        labels: { usePointStyle: true, boxWidth: 8, padding: 16 },
                    },
                    tooltip: {
                        backgroundColor: "rgba(10,27,48,.92)",
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            label: (item) => {
                                // indexAxis:"y" (horizontal bars) swaps which
                                // parsed field holds the value vs. the category.
                                const raw = c.horizontal
                                    ? (item.parsed.x ?? item.parsed)
                                    : (item.parsed.y ?? item.parsed);
                                return ` ${formatValue(raw, c.value_format, currency)}`;
                            },
                        },
                    },
                },
                // For a horizontal bar (indexAxis:"y"), Chart.js maps the VALUE
                // axis to x and the CATEGORY axis to y — the opposite of a
                // normal vertical chart. The currency/number formatter must
                // follow the value axis, not always "y".
                scales: isCategorical ? {} : {
                    x: {
                        stacked: !!c.stacked,
                        // Sparse/flat datasets (common on a freshly seeded demo
                        // DB) make Chart.js auto-scale to a tiny or negative
                        // range with repeated/degenerate tick labels. These
                        // dashboard metrics (counts, currency, percent) are
                        // never negative, so anchoring at zero keeps the axis
                        // meaningful regardless of how little data exists.
                        beginAtZero: c.horizontal,
                        grid: { display: c.horizontal },
                        ticks: c.horizontal
                            ? { padding: 8, callback: (v) => formatValue(v, c.value_format, currency) }
                            : { maxRotation: 0, autoSkipPadding: 16 },
                    },
                    y: {
                        stacked: !!c.stacked,
                        beginAtZero: !c.horizontal,
                        border: { display: false },
                        grid: { color: "rgba(100,116,139,.14)", drawTicks: false, display: !c.horizontal },
                        ticks: c.horizontal
                            ? { padding: 8 }
                            : { padding: 8, callback: (v) => formatValue(v, c.value_format, currency) },
                    },
                },
            },
        };
    }

    render_() {
        const canvas = this.canvasRef.el;
        if (!canvas || !window.Chart) {
            return;
        }
        this.chart = new window.Chart(canvas, this.config);
    }
}
