import { Component } from "@odoo/owl";

export class SgcSparkline extends Component {
    static template = "sgc_executive_dashboard.Sparkline";
    static props = {
        data: { type: Array, optional: true },
        color: { type: String, optional: true },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
    };
    static defaultProps = { data: [], color: "#0A1B30", width: 120, height: 34 };

    get geometry() {
        const data = this.props.data || [];
        const { width: w, height: h } = this.props;
        if (data.length < 2) {
            return { line: "", area: "", last: null };
        }
        const min = Math.min(...data);
        const max = Math.max(...data);
        const span = max - min || 1;
        const pts = data.map((v, i) => {
            const x = (i / (data.length - 1)) * (w - 4) + 2;
            const y = h - 3 - ((v - min) / span) * (h - 8);
            return [x, y];
        });
        const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
        const area = `${line} L${pts.at(-1)[0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
        return { line, area, last: pts.at(-1) };
    }
}
