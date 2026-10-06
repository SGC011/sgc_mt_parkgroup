# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Free-text business question -> validated spec -> executed result.

The "brain" both AI-extension proposal documents assumed already existed —
neither ever defined it. `sgc_ask()` is the one place a natural-language
question is turned into a `sgc.provider.dynamic` spec, and every spec it
proposes is validated against `sgc.capability` before anything touches the
ORM (see `sgc_provider_dynamic.py`).
"""
import collections
import logging
import threading
import time

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# In-process (per Odoo worker) soft rate limiter -- a safety net, not the
# security boundary. The allowlist in sgc.capability/sgc.provider.dynamic is
# what actually prevents unsafe access; this just stops one user hammering
# the LLM endpoint.
_rate_lock = threading.Lock()
_rate_buckets = collections.defaultdict(collections.deque)


def _sgc_check_rate(uid, max_per_minute):
    now = time.monotonic()
    with _rate_lock:
        bucket = _rate_buckets[uid]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= max_per_minute:
            return False
        bucket.append(now)
        return True


_SPEC_SCHEMA = """Return exactly one JSON object, no prose, no code fences, matching:
{
  "code": "short_snake_case_id",
  "name": "Human-readable label",
  "model_name": "<one model from the CATALOGUE below, verbatim>",
  "aggregate": "count|sum|avg|min|max",
  "measure_field": "<a 'measures' field from that model, or null if aggregate is count>",
  "date_field": "<a 'dates' field from that model, or null>",
  "group_field": "<a 'group by' field from that model, or null>",
  "domain": [["field", "op", value], ...],
  "limit": 10,
  "order": "asc|desc",
  "viz": "kpi|bar|line|doughnut|polarArea",
  "value_format": "currency|number|percent|duration"
}
Allowed domain operators: =, !=, >, >=, <, <=, in, not in, ilike, not ilike, like, =like.
Every field name in "domain", "measure_field", "group_field" and "date_field" MUST be
one of the field names listed for that exact model in the CATALOGUE below. Never
invent a field name by analogy with another model. Do NOT add a company_id or date
range filter to "domain" yourself -- the server applies multi-company scoping and the
requested time period automatically, after your answer."""

_EXAMPLES = """EXAMPLES (hand-written, use only as a pattern -- always use the real
CATALOGUE fields for the actual model, never copy these field names onto a
different model):
Q: "how much revenue this period"
A: {"code":"revenue","name":"Confirmed Revenue","model_name":"sale.order","aggregate":"sum","measure_field":"amount_untaxed","date_field":"date_order","group_field":null,"domain":[["state","in",["sale","done"]]],"limit":10,"order":"desc","viz":"kpi","value_format":"currency"}
Q: "how many open purchase orders"
A: {"code":"open_po","name":"Open Purchase Orders","model_name":"purchase.order","aggregate":"count","measure_field":null,"date_field":null,"group_field":null,"domain":[["state","in",["draft","sent","to approve"]]],"limit":10,"order":"desc","viz":"kpi","value_format":"number"}
Q: "top customers by revenue"
A: {"code":"top_customers","name":"Revenue by Customer","model_name":"sale.order","aggregate":"sum","measure_field":"amount_untaxed","date_field":"date_order","group_field":"partner_id","domain":[["state","in",["sale","done"]]],"limit":10,"order":"desc","viz":"bar","value_format":"currency"}"""


class SgcAiAssistant(models.AbstractModel):
    _name = 'sgc.ai.assistant'
    _description = 'SGC AI Assistant — Free-Text Query Engine'

    @api.model
    def _sgc_system_prompt(self):
        catalogue = self.env['sgc.capability'].describe_for_llm()
        return (
            "You translate a business question into a JSON query spec for "
            "an Odoo 19 reporting layer. You may reference ONLY the model "
            "and field names in the CATALOGUE below -- any other name is a "
            "hard failure and will be rejected.\n\n"
            + _SPEC_SCHEMA + "\n\nCATALOGUE:\n" + catalogue + "\n\n" + _EXAMPLES
        )

    @api.model
    def sgc_ask(self, question, period='ytd', persist=False, provider='default',
                date_from=None, date_to=None):
        Dashboard = self.env['sgc.executive.dashboard']
        Dashboard._sgc_check_access()

        max_per_minute = int(self.env['ir.config_parameter'].sudo().get_param(
            'sgc_ai.max_calls_per_minute', '20') or 20)
        if not _sgc_check_rate(self.env.uid, max_per_minute):
            return {'ok': False, 'question': question,
                    'message': _("Too many AI requests -- please wait a moment.")}

        Transport = self.env['sgc.ai.transport']
        Dynamic = self.env['sgc.provider.dynamic']

        try:
            raw_spec = Transport.complete_json(
                self._sgc_system_prompt(), question, provider=provider,
                max_tokens=700, timeout=45)
        except UserError as err:
            return {'ok': False, 'question': question, 'message': str(err)}

        if not raw_spec:
            return {'ok': False, 'question': question, 'message': _(
                "The AI could not turn that into a query. Try naming the "
                "figure and the period, e.g. 'total revenue this quarter'.")}

        try:
            spec = Dynamic._sgc_validate(raw_spec)
        except UserError as err:
            _logger.warning(
                "SGC AI: rejected spec from user %s for question %r: %s -- raw=%s",
                self.env.user.login, question, err, raw_spec)
            return {'ok': False, 'question': question, 'message': str(err),
                    'rejected_spec': raw_spec}

        ctx = Dashboard._sgc_context(period, date_from, date_to)
        result = Dynamic._sgc_execute(spec, ctx)
        if result is None:
            return {'ok': False, 'question': question, 'message': _(
                "The query could not be executed against live data."),
                'spec': spec}

        definition_id = None
        if persist:
            if not self.env.user.has_group(
                    'sgc_executive_dashboard.group_sgc_executive_officer'):
                raise AccessError(_(
                    "Only Executive Officers can save a new KPI definition."))
            base_code = spec['code'] or 'ai_kpi'
            code = base_code
            suffix = 1
            KpiDefinition = self.env['sgc.kpi.definition']
            while KpiDefinition.search_count([('code', '=', code)]):
                suffix += 1
                code = f'{base_code}_{suffix}'
            definition = KpiDefinition.create({
                'name': spec['name'],
                'code': code,
                'model_name': spec['model_name'],
                'aggregate': spec['aggregate'],
                'measure_field': spec['measure_field'],
                'date_field': spec['date_field'],
                'group_field': spec['group_field'],
                'domain_json': str(spec['domain']),
                'limit': spec['limit'],
                'viz': spec['viz'],
                'value_format': spec['value_format'],
                'source': 'ai',
                'created_by_prompt': question[:250],
            })
            definition_id = definition.id

        action = Dynamic._sgc_action(spec, result['domain'], name=spec['name'])

        return {
            'ok': True,
            'question': question,
            'spec': spec,
            'value': result['value'],
            'value_format': result['value_format'],
            'period': period,
            'date_from': str(ctx['date_from']),
            'date_to': str(ctx['date_to']),
            'breakdown': result['breakdown'],
            'series': result['series'],
            'drill': {'res_model': spec['model_name'], 'domain': result['domain'],
                      'name': spec['name']},
            'action': action,
            'narrative': None,
            'message': '',
            'definition_id': definition_id,
            'intent': None,
        }

    @api.model
    def _call_llm(self, system, user, provider='default'):
        """Thin wrapper over transport.complete() -- returns None rather than
        raising, so a dead LLM never breaks a caller that still has real
        facts to show (e.g. sgc.ai.intent._do_brief).
        """
        try:
            return self.env['sgc.ai.transport'].complete(system, user, provider=provider)
        except Exception:
            _logger.warning("SGC AI: _call_llm failed", exc_info=True)
            return None
