/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

export class SgcAiBar extends Component {
    static template = "sgc_executive_dashboard.AiBar";
    static props = { period: String, onResult: Function };

    setup() {
        this.state = useState({
            presets: [], providers: [], warning: null,
            prompt: "", provider: "default", busy: null,
        });
        this._pollAlive = true;
        onWillStart(async () => {
            const meta = await rpc("/sgc_executive_dashboard/ai_meta", {});
            this.state.presets = meta.presets;
            const configured = meta.providers.filter((p) => p.configured);
            this.state.providers = configured;
            if (configured.length) {
                this.state.provider = configured[0].code;
            } else if (meta.providers.length) {
                this.state.warning = meta.providers[0].param;
            }
        });
    }

    willUnmount() {
        this._pollAlive = false;
    }

    get groupedPresets() {
        const groups = {};
        for (const preset of this.state.presets) {
            (groups[preset.category] ||= []).push(preset);
        }
        return groups;
    }

    async runPreset(preset) {
        this.state.busy = preset.code;
        try {
            let result;
            if (preset.instant) {
                result = await rpc("/sgc_executive_dashboard/preset", {
                    preset_id: preset.id, period: this.props.period,
                });
            } else {
                const { job_id } = await rpc("/sgc_executive_dashboard/enqueue", {
                    preset_id: preset.id, period: this.props.period,
                });
                result = await this.awaitJob(job_id);
            }
            this.props.onResult(result);
        } finally {
            this.state.busy = null;
        }
    }

    async runFreeText() {
        const prompt = (this.state.prompt || "").trim();
        if (!prompt) {
            return;
        }
        this.state.busy = "__freetext__";
        try {
            const result = await rpc("/sgc_executive_dashboard/route", {
                prompt, context: { period: this.props.period, provider: this.state.provider },
            });
            this.props.onResult(result);
            this.state.prompt = "";
        } finally {
            this.state.busy = null;
        }
    }

    async awaitJob(jobId, tries = 60) {
        for (let i = 0; i < tries; i++) {
            if (!this._pollAlive) {
                return { ok: false, message: _t("Cancelled.") };
            }
            await new Promise((resolve) => setTimeout(resolve, 1500));
            const res = await rpc("/sgc_executive_dashboard/job", { job_id: jobId });
            if (res.state === "done") {
                return res.result;
            }
            if (res.state === "failed") {
                return { ok: false, message: res.error || _t("The AI job failed.") };
            }
        }
        return { ok: false, message: _t("Timed out waiting for the AI backend.") };
    }
}
