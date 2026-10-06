# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""One-click AI command library. Three execution modes:
  - deterministic: no LLM call, real numbers only (e.g. the anomaly scan).
  - narrative:      real numbers + an AI-written summary of them.
  - generative:     the free-text intent router handles the whole request.

Corrections applied vs. the original proposal draft:
  - `_collect_facts` calls `sgc_get_dashboard(period=period)` with no
    `compare` kwarg (doesn't exist).
  - reads `k.get('action')`, not `k.get('drill')`, on real dashboard KPI
    dicts (the real field name -- see `sgc_kpi_provider._sgc_kpi`).
  - `visible_presets()` checks group membership via `env.user.group_ids`
    intersection rather than building a possibly-empty xmlid string.
"""
import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SgcAiPreset(models.Model):
    _name = 'sgc.ai.preset'
    _description = 'SGC AI Preset Command'
    _order = 'category, sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=100)
    active = fields.Boolean(default=True)
    category = fields.Selection([
        ('brief', 'Executive Briefing'),
        ('risk', 'Risk & Exposure'),
        ('growth', 'Growth & Pipeline'),
        ('ops', 'Operations'),
        ('people', 'People'),
        ('custom', 'Custom'),
    ], default='custom', required=True)
    icon = fields.Char(default='fa-magic')
    accent = fields.Selection(
        [('brand', 'Brand'), ('teal', 'Teal'), ('amber', 'Amber'),
         ('violet', 'Violet'), ('rose', 'Rose'), ('slate', 'Slate')],
        default='brand')
    description = fields.Char(translate=True,
                               help="Shown on the preset chip as a tooltip.")

    mode = fields.Selection([
        ('deterministic', 'Deterministic (no LLM call)'),
        ('narrative', 'Deterministic data + AI narrative'),
        ('generative', 'Fully AI generated'),
    ], default='narrative', required=True)

    intent = fields.Selection([
        ('metric', 'Metric'), ('compare', 'Compare'), ('explain', 'Explain'),
        ('rank', 'Rank'), ('anomaly', 'Anomaly Scan'), ('brief', 'Brief'),
        ('navigate', 'Navigate'),
    ], default='metric', required=True)

    prompt_template = fields.Text(
        help="Supports {period}, {company}, {date_from}, {date_to}, {user}.")
    kpi_codes = fields.Char(
        help="Comma-separated KPI keys from sgc_get_dashboard()['kpis'] fed to the preset.")
    spec_json = fields.Text(
        help="Pre-validated sgc.provider.dynamic spec. When set, no LLM planning call is made.")
    provider = fields.Selection(
        [('default', 'Default'), ('minimax', 'MiniMax')], default='default')
    group_ids = fields.Many2many('res.groups', string='Restricted To')
    run_count = fields.Integer(readonly=True, default=0)

    _code_uniq = models.Constraint('UNIQUE(code)', 'Preset code must be unique.')

    # ------------------------------------------------------------------ render
    def _render_prompt(self, ctx):
        self.ensure_one()
        try:
            return (self.prompt_template or self.name).format(
                period=ctx.get('period', 'ytd'),
                company=self.env.company.name,
                date_from=ctx.get('date_from', ''),
                date_to=ctx.get('date_to', ''),
                user=self.env.user.name)
        except (KeyError, IndexError, ValueError):
            # A stray "{revenue}" in a hand-edited template must not 500 the
            # dashboard -- fall back to the raw, unformatted template.
            return self.prompt_template or self.name

    @api.model
    def visible_presets(self):
        self.env['sgc.executive.dashboard']._sgc_check_access()
        user_group_ids = set(self.env.user.group_ids.ids)
        presets = self.search([]).filtered(
            lambda p: not p.group_ids or set(p.group_ids.ids) & user_group_ids)
        return [{
            'id': p.id, 'code': p.code, 'name': p.name,
            'category': p.category, 'icon': p.icon, 'accent': p.accent,
            'description': p.description or '', 'mode': p.mode,
            'instant': p.mode == 'deterministic',
        } for p in presets]

    # --------------------------------------------------------------------- run
    def run(self, dashboard_ctx=None):
        self.ensure_one()
        Dashboard = self.env['sgc.executive.dashboard']
        Dashboard._sgc_check_access()
        ctx = dashboard_ctx or {}
        period = ctx.get('period', 'ytd')

        facts = self._collect_facts(period)

        if self.mode == 'deterministic':
            payload = {'ok': True, 'preset': self.code, 'facts': facts,
                       'narrative': None}
        elif self.mode == 'narrative':
            payload = {'ok': True, 'preset': self.code, 'facts': facts,
                       'narrative': self._narrate(facts, ctx)}
        else:
            payload = self.env['sgc.ai.intent'].sgc_route(
                self._render_prompt(ctx), {'period': period, 'provider': self.provider})
            payload['preset'] = self.code

        self.sudo().run_count += 1
        payload['name'] = self.name
        payload['icon'] = self.icon
        payload['accent'] = self.accent
        return payload

    def _collect_facts(self, period):
        """Pull real numbers first. Nothing here touches an LLM."""
        self.ensure_one()
        Dashboard = self.env['sgc.executive.dashboard']
        Dynamic = self.env['sgc.provider.dynamic']

        if self.spec_json:
            try:
                spec = json.loads(self.spec_json)
            except ValueError:
                return []
            ctx = Dashboard._sgc_context(period, None, None)
            try:
                spec = Dynamic._sgc_validate(spec)
            except Exception:
                return []
            result = Dynamic._sgc_execute(spec, ctx)
            if not result:
                return []
            return [{'label': spec.get('name', self.name),
                     'value': result['value'],
                     'breakdown': result.get('breakdown'),
                     'drill': {'res_model': spec['model_name'],
                               'domain': result['domain'],
                               'name': spec.get('name', self.name)}}]

        if self.intent == 'anomaly':
            scan = self.env['sgc.ai.intent']._do_anomaly('', {'period': period})
            return [{'label': f['name'], 'value': f['latest'],
                     'baseline': f['baseline'], 'sigma': f['sigma']}
                    for f in scan.get('findings', [])]

        codes = [c.strip() for c in (self.kpi_codes or '').split(',') if c.strip()]
        data = Dashboard.sgc_get_dashboard(period=period)
        kpis = data['kpis']
        if codes:
            kpis = [k for k in kpis if k['key'] in codes]
        return [{'label': k['label'], 'value': k['value'],
                 'delta': k.get('delta'), 'source': k.get('source'),
                 'format': k.get('format'), 'drill': k.get('action')}
                for k in kpis]

    def _narrate(self, facts, ctx):
        if not facts:
            return None
        system = (
            "You are chief of staff to the SGC executive team. Using ONLY "
            "the JSON facts provided, write the requested briefing. "
            "Absolute rules: never invent or extrapolate a number; never "
            "restate every fact -- select what matters; write flowing "
            "prose, no bullet lists; under 150 words; no preamble such as "
            "'Here is'. Instruction: " + self._render_prompt(ctx))
        try:
            return self.env['sgc.ai.transport'].complete(
                system, json.dumps(facts, default=str),
                provider=self.provider, max_tokens=600, timeout=40)
        except Exception:
            # A dead LLM must never kill the data that's already computed.
            return None
