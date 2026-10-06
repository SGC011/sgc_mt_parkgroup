import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

export class SgcAppUniverse extends Component {
    static template = "sgc_executive_dashboard.AppUniverse";
    static props = {
        universe: { type: Object },
        canInstall: { type: Boolean, optional: true },
        onReload: { type: Function, optional: true },
    };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ tab: "installed", busy: null, query: "" });
    }

    get list() {
        const src = this.state.tab === "installed"
            ? this.props.universe.installed
            : this.props.universe.dormant;
        const q = this.state.query.trim().toLowerCase();
        return q ? src.filter((a) => a.label.toLowerCase().includes(q)) : src;
    }

    openApp(app) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "ir.module.module",
            res_id: app.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    async activate(app) {
        if (!this.props.canInstall) {
            this.notification.add(
                _t("Activation requires system administrator rights."),
                { type: "warning" }
            );
            return;
        }
        this.state.busy = app.id;
        try {
            await rpc("/sgc_executive_dashboard/activate", { module_id: app.id });
            this.notification.add(
                _t("%s activated. Reloading the workspace…", app.label),
                { type: "success" }
            );
            window.location.reload();
        } catch (error) {
            this.state.busy = null;
            throw error;
        }
    }
}
