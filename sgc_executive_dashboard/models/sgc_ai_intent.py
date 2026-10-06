# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Verb router fronting the AI assistant and the deterministic anomaly scan.

Adapted from a proposal sketch in `executive_dashboard.md` (lines 3072+)
with several corrections applied against the real codebase:
  - `sgc_get_dashboard()` has no `compare` kwarg -- never pass one.
  - `sgc.kpi.provider` has `_sgc_previous_range`, not the sketch's invented
    `_sgc_compare_range`.
  - `_sgc_series()` has no `with_domains` kwarg.
  - `_do_anomaly` forces a `last12` context regardless of the caller's
    period -- any shorter window yields under 4 monthly buckets and the
    scan silently finds nothing.
"""
import datetime
import json
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

_PREFIXES = {
    'metric': ('metric', 'kpi', 'show', 'what'),
    'compare': ('compare', 'vs', 'versus'),
    'explain': ('explain', 'why'),
    'rank': ('rank', 'top', 'bottom', 'worst', 'best'),
    'anomaly': ('anomaly', 'anomalies', 'unusual', 'check'),
    'build': ('build', 'add', 'create', 'save'),
    'navigate': ('open', 'go', 'goto'),
    'brief': ('brief', 'summary', 'summarise', 'summarize', 'digest'),
}

_EXPLAIN_GROUP_CANDIDATES = (
    'partner_id', 'user_id', 'team_id', 'product_id', 'department_id', 'stage_id',
)


class SgcAiIntent(models.AbstractModel):
    _name = 'sgc.ai.intent'
    _description = 'SGC AI Intent Router'

    # ------------------------------------------------------------ classify
    @api.model
    def _classify(self, prompt):
        head = (prompt or '').strip().split(' ', 1)
        first = head[0].lower().strip(':') if head else ''
        for intent, words in _PREFIXES.items():
            if first in words:
                rest = head[1] if len(head) > 1 else ''
                return intent, (rest or prompt).strip()
        low = (prompt or '').lower()
        if ' vs ' in low or 'versus' in low:
            return 'compare', prompt
        if low.startswith('why'):
            return 'explain', prompt
        return 'metric', prompt

    # -------------------------------------------------------------- routing
    @api.model
    def sgc_route(self, prompt, context=None):
        self.env['sgc.executive.dashboard']._sgc_check_access()
        context = dict(context or {})
        intent, argument = self._classify(prompt)

        # Cheap, LLM-free, ORM-free classification-only response -- what the
        # Ctrl+K palette calls while the user is still typing.
        if context.get('plan_only'):
            return {'ok': True, 'intent': intent, 'argument': argument, 'deferred': True}

        if context.get('deterministic_only') and intent != 'anomaly':
            return {'ok': False, 'async_required': True, 'intent': intent}

        handler = getattr(self, f'_do_{intent}', None)
        if handler is None:
            result = self.env['sgc.ai.assistant'].sgc_ask(
                argument, period=context.get('period', 'ytd'))
        else:
            result = handler(argument, context)
        if not isinstance(result, dict):
            result = {'ok': False, 'message': _("The AI returned an unexpected result.")}
        result['intent'] = intent
        return result

    # --------------------------------------------------------------- verbs
    @api.model
    def _do_metric(self, argument, context):
        return self.env['sgc.ai.assistant'].sgc_ask(
            argument, period=context.get('period', 'ytd'))

    @api.model
    def _do_build(self, argument, context):
        return self.env['sgc.ai.assistant'].sgc_ask(
            argument, period=context.get('period', 'ytd'), persist=True)

    @api.model
    def _do_compare(self, argument, context):
        base = self.env['sgc.ai.assistant'].sgc_ask(
            argument, period=context.get('period', 'ytd'))
        if not base.get('ok'):
            return base
        Dashboard = self.env['sgc.executive.dashboard']
        Dynamic = self.env['sgc.provider.dynamic']
        spec = base['spec']
        grid = []
        for period in ('mtd', 'qtd', 'ytd'):
            ctx = Dashboard._sgc_context(period, None, None)
            res = Dynamic._sgc_execute(spec, ctx)
            if res:
                grid.append({'period': period, 'value': res['value']})
        base['comparison_grid'] = grid
        return base

    @api.model
    def _do_rank(self, argument, context):
        result = self.env['sgc.ai.assistant'].sgc_ask(
            argument, period=context.get('period', 'ytd'))
        if result.get('ok') and not result.get('breakdown'):
            result['message'] = _(
                "No grouping dimension was inferred -- try naming one, "
                "e.g. 'top customers by revenue'.")
        return result

    @api.model
    def _do_explain(self, argument, context):
        """Attribution: which dimension members drove the delta."""
        Assistant = self.env['sgc.ai.assistant']
        base = Assistant.sgc_ask(argument, period=context.get('period', 'ytd'))
        if not base.get('ok'):
            return base
        spec = dict(base['spec'])
        Capability = self.env['sgc.capability']
        if not spec.get('group_field'):
            for candidate in _EXPLAIN_GROUP_CANDIDATES:
                if Capability.field_info(spec['model_name'], candidate):
                    spec['group_field'] = candidate
                    spec['viz'] = 'bar'
                    break
        if not spec.get('group_field'):
            base['drivers'] = []
            return base

        Dashboard = self.env['sgc.executive.dashboard']
        Dynamic = self.env['sgc.provider.dynamic']
        period = context.get('period', 'ytd')
        ctx = Dashboard._sgc_context(period, None, None)
        # Re-validate: group_field may have just been added above.
        try:
            spec = Dynamic._sgc_validate(spec)
        except Exception:
            base['drivers'] = []
            return base
        cur = Dynamic._sgc_execute(spec, ctx) or {}

        prev_from, prev_to = self.env['sgc.kpi.provider']._sgc_previous_range(ctx)
        cmp_ctx = dict(ctx)
        cmp_ctx['date_from'] = prev_from
        cmp_ctx['date_to'] = prev_to
        cmp_ctx['dt_from'] = datetime.datetime.combine(prev_from, datetime.time.min)
        cmp_ctx['dt_to'] = datetime.datetime.combine(prev_to, datetime.time.max)

        drivers = []
        if cur.get('breakdown'):
            prev = Dynamic._sgc_execute(spec, cmp_ctx) or {}
            prev_breakdown = prev.get('breakdown') or {'labels': [], 'values': []}
            prev_map = dict(zip(prev_breakdown['labels'], prev_breakdown['values']))
            for label, value in zip(cur['breakdown']['labels'], cur['breakdown']['values']):
                before = prev_map.get(label, 0.0)
                drivers.append({'label': label, 'current': value, 'previous': before,
                                'delta': round(value - before, 2)})
            drivers.sort(key=lambda d: abs(d['delta']), reverse=True)
        base['drivers'] = drivers[:6]
        base['spec'] = spec
        return base

    @api.model
    def _do_anomaly(self, argument, context):
        """Statistical scan of every saved KPI definition -- no LLM call.
        Forces a last12 context regardless of the caller's period: with
        anything shorter than ~4 monthly buckets the scan trivially finds
        nothing and silently looks broken.
        """
        Dashboard = self.env['sgc.executive.dashboard']
        Dynamic = self.env['sgc.provider.dynamic']
        ctx = Dashboard._sgc_context('last12', None, None)
        findings = []
        for definition in self.env['sgc.kpi.definition'].search(
                [('date_field', '!=', False)]):
            try:
                spec = Dynamic._sgc_validate(definition._to_spec())
            except Exception:
                continue
            cap = self.env['sgc.capability'].model_info(spec['model_name'])
            if not cap:
                continue
            domain = list(spec['domain']) + list(cap['default_domain'])
            if cap['company_field']:
                domain = domain + [(cap['company_field'], 'in', ctx['company_ids'])]
            try:
                series = self.env['sgc.kpi.provider']._sgc_series(
                    spec['model_name'], domain, spec['date_field'],
                    spec['measure_field'], ctx)
            except Exception:
                continue
            values = series['values']
            if len(values) < 4:
                continue
            body, latest = values[:-1], values[-1]
            mean = sum(body) / len(body)
            variance = sum((v - mean) ** 2 for v in body) / len(body)
            sd = variance ** 0.5
            if sd and abs(latest - mean) > 2 * sd:
                findings.append({
                    'code': spec['code'] or definition.code, 'name': spec['name'],
                    'latest': latest, 'baseline': round(mean, 2),
                    'sigma': round((latest - mean) / sd, 1),
                    'direction': 'above' if latest > mean else 'below',
                })
        findings.sort(key=lambda f: abs(f['sigma']), reverse=True)
        return {'ok': True, 'findings': findings[:8],
                'message': _("%s signal(s) outside two standard deviations.",
                             len(findings))}

    @api.model
    def _do_navigate(self, argument, context):
        result = self.env['sgc.ai.assistant'].sgc_ask(
            argument, period=context.get('period', 'ytd'))
        if result.get('ok') and not result.get('action') and result.get('drill'):
            drill = result['drill']
            result['action'] = {
                'type': 'ir.actions.act_window',
                'name': drill['name'],
                'res_model': drill['res_model'],
                'domain': drill['domain'],
                'views': [[False, 'list'], [False, 'form']],
            }
        return result

    @api.model
    def _do_brief(self, argument, context):
        """Narrative digest grounded in already-computed numbers -- no
        `compare` kwarg (doesn't exist on sgc_get_dashboard).
        """
        Dashboard = self.env['sgc.executive.dashboard']
        period = context.get('period', 'ytd')
        data = Dashboard.sgc_get_dashboard(period=period)
        facts = [{'label': k['label'], 'value': k['value'],
                  'delta': k.get('delta'), 'source': k.get('source')}
                 for k in data['kpis']]
        system = (
            "You are a CFO's chief of staff. Using ONLY the JSON facts "
            "given, write a 120-word executive brief: headline, two "
            "movements worth attention, one risk. Never invent numbers. "
            "Plain prose, no lists, no preamble such as 'Here is'.")
        narrative = self.env['sgc.ai.assistant']._call_llm(
            system, json.dumps(facts, default=str))
        return {'ok': True, 'narrative': narrative, 'facts': facts,
                'period': data['meta']['period']}
