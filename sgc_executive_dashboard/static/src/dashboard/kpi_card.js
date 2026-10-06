import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SgcSparkline } from "./sparkline";
import { formatValue, accentColor } from "./utils";

export class SgcKpiCard extends Component {
    static template = "sgc_executive_dashboard.KpiCard";
    static components = { SgcSparkline };
    static props = {
        kpi: { type: Object },
        currency: { type: Object, optional: true },
    };

    setup() {
        this.action = useService("action");
    }

    get displayValue() {
        return formatValue(this.props.kpi.value, this.props.kpi.format, this.props.currency);
    }

    get accent() {
        return accentColor(this.props.kpi.accent);
    }

    get deltaClass() {
        const d = this.props.kpi.delta;
        if (d === null || d === undefined) {
            return "o_sgc_delta_flat";
        }
        return d >= 0 ? "o_sgc_delta_up" : "o_sgc_delta_down";
    }

    get deltaLabel() {
        const d = this.props.kpi.delta;
        if (d === null || d === undefined) {
            return "";
        }
        return `${d >= 0 ? "+" : ""}${d.toFixed(1)}%`;
    }

    get progress() {
        const { value, target } = this.props.kpi;
        if (!target) {
            return null;
        }
        return Math.min(100, Math.max(0, (value / target) * 100));
    }

    onDrill() {
        if (this.props.kpi.action) {
            this.action.doAction(this.props.kpi.action);
        }
    }
}
