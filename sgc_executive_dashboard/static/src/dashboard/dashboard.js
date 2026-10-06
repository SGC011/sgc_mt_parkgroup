import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { SgcKpiCard } from "./kpi_card";
import { SgcChartCard } from "./chart_card";
import { SgcAppUniverse } from "./app_universe";
import { SgcAiBar } from "../ai/ai_bar";
import { SgcAiResult } from "../ai/ai_result";

export class SgcExecutiveDashboard extends Component {
    static template = "sgc_executive_dashboard.Dashboard";
    static components = { Layout, SgcKpiCard, SgcChartCard, SgcAppUniverse, SgcAiBar, SgcAiResult };
    static props = { ...Component.props, action: { type: Object, optional: true } };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.display = { controlPanel: {} };

        this.periods = [
            { key: "mtd", label: _t("Month to date") },
            { key: "qtd", label: _t("Quarter to date") },
            { key: "ytd", label: _t("Year to date") },
            { key: "last12", label: _t("Rolling 12 months") },
        ];

        this.state = useState({
            loading: true,
            period: "ytd",
            data: null,
            view: "overview",   // overview | universe
            ai: { result: null },
        });

        // Handoff from the Ctrl+K (/sgcai) command palette: either a
        // pre-computed result (deterministic answers, e.g. the anomaly
        // scan) or a prompt still to be asked once the dashboard is up.
        const handoffContext = (this.props.action && this.props.action.context) || {};
        this._pendingPrompt = handoffContext.sgcai_prompt || null;
        if (handoffContext.sgcai_result) {
            this.state.ai.result = handoffContext.sgcai_result;
        }

        onWillStart(async () => {
            await this.load();
            if (this._pendingPrompt) {
                const result = await rpc("/sgc_executive_dashboard/route", {
                    prompt: this._pendingPrompt, context: { period: this.state.period },
                });
                this.state.ai.result = result;
            }
        });
    }

    onAiResult(result) {
        this.state.ai.result = result;
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await rpc("/sgc_executive_dashboard/data", {
                period: this.state.period,
            });
        } finally {
            this.state.loading = false;
        }
    }

    async setPeriod(key) {
        if (key === this.state.period) {
            return;
        }
        this.state.period = key;
        await this.load();
    }

    get meta() {
        return this.state.data ? this.state.data.meta : {};
    }

    get currency() {
        return this.meta.currency || {};
    }

    get headline() {
        // Promote the highest-signal KPIs into the hero band.
        const kpis = (this.state.data && this.state.data.kpis) || [];
        const priority = ["re_sales_value", "fin_margin", "dl_value", "fin_overdue", "cn_contract_value"];
        const hero = priority.map((k) => kpis.find((x) => x.key === k)).filter(Boolean);
        return hero.length ? hero : kpis.slice(0, 4);
    }

    get secondary() {
        const hero = new Set(this.headline.map((k) => k.key));
        return ((this.state.data && this.state.data.kpis) || [])
            .filter((k) => !hero.has(k.key));
    }

    get charts() {
        return (this.state.data && this.state.data.charts) || [];
    }

    get greeting() {
        const h = new Date().getHours();
        if (h < 12) return _t("Good morning");
        if (h < 18) return _t("Good afternoon");
        return _t("Good evening");
    }
}

registry.category("actions").add("sgc_executive_dashboard.main", SgcExecutiveDashboard);
