# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SgcKpiDefinition(models.Model):
    """A saved/dynamic KPI definition — created either by an executive's
    "build" request (`sgc.ai.intent._do_build`) or by an admin directly.
    Every write and every run re-validates through
    `sgc.provider.dynamic._sgc_validate` — a bad definition cannot be
    stored, and one that was valid at creation but references a field
    removed by a later upgrade cannot silently misbehave either.

    Deliberately NOT wrapped in a `sgc.kpi.provider` subclass in this pass —
    that would auto-register via `sgc.executive.dashboard._sgc_providers()`
    and break the hard-asserted 12-provider count in `test_aggregator.py`.
    """
    _name = 'sgc.kpi.definition'
    _description = 'SGC AI — Saved KPI Definition'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=100)

    model_name = fields.Char(required=True, string='Model')
    aggregate = fields.Selection(
        [('count', 'Count'), ('sum', 'Sum'), ('avg', 'Average'),
         ('min', 'Minimum'), ('max', 'Maximum')],
        default='count', required=True)
    measure_field = fields.Char()
    date_field = fields.Char(
        help='If set, this definition is eligible for the anomaly scan.')
    group_field = fields.Char()
    domain_json = fields.Text(default='[]', string='Domain')
    limit = fields.Integer(default=10)
    viz = fields.Selection(
        [('kpi', 'KPI'), ('bar', 'Bar'), ('line', 'Line'),
         ('doughnut', 'Doughnut'), ('polarArea', 'Polar Area')],
        default='kpi')
    value_format = fields.Selection(
        [('number', 'Number'), ('currency', 'Currency'),
         ('percent', 'Percent'), ('duration', 'Duration')],
        default='number')
    accent = fields.Selection(
        [('brand', 'Brand'), ('teal', 'Teal'), ('amber', 'Amber'),
         ('violet', 'Violet'), ('rose', 'Rose'), ('slate', 'Slate')],
        default='brand')
    icon = fields.Char(default='fa-magic')
    description = fields.Char(translate=True)

    source = fields.Selection(
        [('shipped', 'Shipped'), ('ai', 'AI (saved from a question)'),
         ('manual', 'Manual')],
        default='manual', required=True)
    created_by_prompt = fields.Char(readonly=True)
    group_ids = fields.Many2many('res.groups', string='Restricted To')

    _code_uniq = models.Constraint('UNIQUE(code)', 'KPI code must be unique.')

    def _to_spec(self):
        self.ensure_one()
        try:
            domain = ast.literal_eval(self.domain_json or '[]')
        except (ValueError, SyntaxError):
            domain = []
        if not isinstance(domain, list):
            domain = []
        domain = [tuple(leaf) if isinstance(leaf, list) else leaf for leaf in domain]
        return {
            'code': self.code,
            'name': self.name,
            'model_name': self.model_name,
            'aggregate': self.aggregate,
            'measure_field': self.measure_field or None,
            'date_field': self.date_field or None,
            'group_field': self.group_field or None,
            'domain': domain,
            'limit': self.limit or 10,
            'viz': self.viz,
            'value_format': self.value_format,
        }

    def run(self, period='ytd', date_from=None, date_to=None):
        self.ensure_one()
        Dashboard = self.env['sgc.executive.dashboard']
        Dashboard._sgc_check_access()
        ctx = Dashboard._sgc_context(period, date_from, date_to)
        return self.env['sgc.provider.dynamic']._sgc_execute(self._to_spec(), ctx)

    @api.constrains('model_name', 'aggregate', 'measure_field', 'date_field',
                     'group_field', 'domain_json', 'limit')
    def _sgc_check_valid_spec(self):
        Dynamic = self.env['sgc.provider.dynamic']
        for record in self:
            try:
                Dynamic._sgc_validate(record._to_spec())
            except Exception as err:
                _logger.info(
                    "SGC AI: rejected kpi.definition %s: %s", record.code, err)
                raise ValidationError(_(
                    "This KPI definition is not valid: %s", str(err)))
