/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SgcChartCard } from "../dashboard/chart_card";
import { formatValue } from "../dashboard/utils";

export class SgcAiResult extends Component {
    static template = "sgc_executive_dashboard.AiResult";
    static components = { SgcChartCard };
    static props = {
        result: { type: Object },
        currency: { type: Object, optional: true },
        onDismiss: { type: Function },
    };

    setup() {
        this.action = useService("action");
    }

    get displayValue() {
        const r = this.props.result;
        if (r.value === undefined || r.value === null) {
            return null;
        }
        return formatValue(r.value, r.value_format, this.props.currency);
    }

    // Synthesize a chart dict in the exact shape SgcChartCard already
    // consumes (see chart_card.js / provider_finance.py-style chart
    // entries), so a breakdown reuses the same rendering as every other
    // dashboard chart instead of a bespoke component.
    get breakdownChart() {
        const r = this.props.result;
        const breakdown = r.breakdown;
        if (!breakdown || !breakdown.labels || !breakdown.labels.length) {
            return null;
        }
        return {
            key: "ai_breakdown",
            title: (r.spec && r.spec.name) || "Breakdown",
            subtitle: "",
            type: "bar",
            horizontal: true,
            span: 2,
            accent: "brand",
            labels: breakdown.labels,
            datasets: [{ label: (r.spec && r.spec.name) || "Value", data: breakdown.values }],
            value_format: r.value_format || "number",
        };
    }

    get findings() {
        return this.props.result.findings || [];
    }

    get drivers() {
        return this.props.result.drivers || [];
    }

    get comparisonGrid() {
        return this.props.result.comparison_grid || [];
    }

    get facts() {
        return this.props.result.facts || [];
    }

    factValue(f) {
        if (f.value === undefined || f.value === null) {
            return "";
        }
        return formatValue(f.value, f.format || f.value_format, this.props.currency);
    }

    onOpenAction() {
        if (this.props.result.action) {
            this.action.doAction(this.props.result.action);
        }
    }
}
