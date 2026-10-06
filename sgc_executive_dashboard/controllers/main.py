# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import http
from odoo.http import request


class SgcExecutiveDashboardController(http.Controller):

    @http.route('/sgc_executive_dashboard/data', type='jsonrpc', auth='user')
    def sgc_data(self, period='ytd', date_from=None, date_to=None, **kw):
        return request.env['sgc.executive.dashboard'].sgc_get_dashboard(
            period=period, date_from=date_from, date_to=date_to)

    @http.route('/sgc_executive_dashboard/activate', type='jsonrpc', auth='user')
    def sgc_activate(self, module_id, **kw):
        return request.env['sgc.executive.dashboard'].sgc_install_module(module_id)

    @http.route('/sgc_executive_dashboard/route', type='jsonrpc', auth='user')
    def sgc_route(self, prompt, context=None, **kw):
        return request.env['sgc.ai.intent'].sgc_route(prompt, context or {})

    @http.route('/sgc_executive_dashboard/ai_meta', type='jsonrpc', auth='user')
    def sgc_ai_meta(self, **kw):
        env = request.env
        return {
            'presets': env['sgc.ai.preset'].visible_presets(),
            'providers': env['sgc.ai.transport'].provider_status(),
            'powerbox': env['sgc.ai.transport'].powerbox_available(),
            'capability_models': len(env['sgc.capability'].available_capabilities()),
        }

    @http.route('/sgc_executive_dashboard/preset', type='jsonrpc', auth='user')
    def sgc_preset(self, preset_id, period='ytd', **kw):
        preset = request.env['sgc.ai.preset'].browse(int(preset_id))
        if not preset.exists():
            return {'ok': False, 'message': 'Preset not found.'}
        if preset.mode != 'deterministic':
            # Never block a request on a potentially 60s+ LLM call -- the
            # caller should enqueue this one instead.
            return {'ok': False, 'async_required': True}
        return preset.run({'period': period})

    @http.route('/sgc_executive_dashboard/enqueue', type='jsonrpc', auth='user')
    def sgc_enqueue(self, preset_id=None, prompt=None, period='ytd', **kw):
        return request.env['sgc.ai.job'].enqueue(
            preset_id=preset_id, prompt=prompt, period=period)

    @http.route('/sgc_executive_dashboard/job', type='jsonrpc', auth='user')
    def sgc_job(self, job_id, **kw):
        job = request.env['sgc.ai.job'].browse(int(job_id))
        if not job.exists():
            return {'state': 'failed', 'error': 'Job not found.'}
        return job.poll()
