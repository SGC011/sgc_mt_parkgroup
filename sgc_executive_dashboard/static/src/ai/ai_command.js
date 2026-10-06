/** @odoo-module **/
/**
 * Global Ctrl+K (/sgcai) command-palette provider.
 *
 * Correction vs. the original proposal sketch: that draft RPC'd the full,
 * LLM-backed `/route` endpoint on every ~500ms debounce tick while typing,
 * which would fire a 5-60s LLM call per keystroke burst. Here, while the
 * user is still typing, only cheap classification calls are made
 * (`plan_only`: prefix-match only, no LLM, no ORM; `deterministic_only`:
 * only the anomaly scan runs). The actual question is only answered after
 * the user commits and the dashboard action opens.
 */
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

const NS = "/sgcai";
const DASHBOARD_ACTION = "sgc_executive_dashboard.action_sgc_executive_dashboard";

registry.category("command_setup").add(NS, {
    debounceDelay: 300,
    emptyMessage: _t("Ask SGC AI a business question..."),
    name: _t("SGC AI"),
    placeholder: _t("e.g. why did margin drop, top 10 late customers, brief me"),
});

registry.category("command_categories").add("sgcai", { namespace: NS, name: _t("SGC AI") });

registry.category("command_provider").add("sgcai_provider", {
    namespace: NS,
    async provide(env, options) {
        const query = (options.searchValue || "").trim();
        if (query.length < 3) {
            return [
                {
                    name: _t("Brief me on this period"),
                    category: "sgcai",
                    action: () => openDashboard(env, { sgcai_prompt: "brief" }),
                },
                {
                    name: _t("Scan for anomalies"),
                    category: "sgcai",
                    action: async () => {
                        const result = await rpc("/sgc_executive_dashboard/route", {
                            prompt: "anomaly", context: { deterministic_only: true },
                        });
                        openDashboard(env, { sgcai_result: result });
                    },
                },
            ];
        }

        let planned;
        try {
            planned = await rpc("/sgc_executive_dashboard/route", {
                prompt: query, context: { plan_only: true },
            });
        } catch {
            return [{
                name: _t("SGC AI is unavailable"), category: "sgcai", action: () => {},
            }];
        }

        const verb = (planned && planned.intent) || "metric";
        return [{
            name: _t("Ask SGC AI (%s): %s", verb, query),
            category: "sgcai",
            action: () => openDashboard(env, { sgcai_prompt: query }),
        }];
    },
});

function openDashboard(env, extraContext) {
    env.services.action.doAction(DASHBOARD_ACTION, { additionalContext: extraContext });
}
