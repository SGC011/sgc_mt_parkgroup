# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import api, fields, models
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class SgcKpiProvider(models.AbstractModel):
    """Base contract for every SGC dashboard data provider.

    Subclass, set the ``_sgc_*`` attributes and implement ``_sgc_collect``.
    The aggregator auto-discovers any registry model inheriting this one.
    """
    _name = 'sgc.kpi.provider'
    _description = 'SGC KPI Provider'

    # --- Provider descriptor -------------------------------------------------
    _sgc_module = None          # technical name of the Odoo module required
    _sgc_label = 'Application'  # human label shown on the card cluster
    _sgc_icon = 'fa-cube'       # FontAwesome glyph
    _sgc_accent = 'brand'       # token: brand | teal | amber | violet | rose | slate
    _sgc_sequence = 100
    _sgc_pitch = ''             # value proposition shown when NOT installed

    # --- Availability --------------------------------------------------------
    @api.model
    def _sgc_is_installed(self):
        if not self._sgc_module:
            return False
        Module = self.env['ir.module.module'].sudo()
        return bool(Module.search_count([
            ('name', '=', self._sgc_module),
            ('state', 'in', ('installed', 'to upgrade')),
        ]))

    @api.model
    def _sgc_collect(self, ctx):
        """Return {'kpis': [...], 'charts': [...]} — override in subclasses."""
        return {'kpis': [], 'charts': []}

    # --- Safe entry point ----------------------------------------------------
    @api.model
    def _sgc_run(self, ctx):
        if not self._sgc_is_installed():
            return None
        try:
            payload = self._sgc_collect(ctx) or {}
        except Exception:
            # A single broken provider must never take down the dashboard.
            _logger.exception("SGC dashboard: provider %s failed", self._name)
            return {'kpis': [], 'charts': [], 'error': True}
        payload.setdefault('kpis', [])
        payload.setdefault('charts', [])
        return payload

    # --- Shared helpers ------------------------------------------------------
    @api.model
    def _sgc_company_domain(self, ctx):
        return [('company_id', 'in', ctx['company_ids'])]

    @api.model
    def _sgc_sum(self, model, domain, field):
        """Sum a stored numeric field. Returns 0.0 when nothing matches."""
        Model = self.env[model].sudo()
        groups = Model._read_group(domain, [], [f'{field}:sum'])
        return (groups and groups[0][0]) or 0.0

    @api.model
    def _sgc_count(self, model, domain):
        return self.env[model].sudo().search_count(domain)

    @api.model
    def _sgc_series(self, model, domain, date_field, measure, ctx, granularity='month'):
        """Return {'labels': [...], 'values': [...]} bucketed over the range."""
        Model = self.env[model].sudo()
        agg = f'{measure}:sum' if measure else '__count'
        groups = Model._read_group(
            domain, [f'{date_field}:{granularity}'], [agg],
            order=f'{date_field}:{granularity} asc',
        )
        labels, values = [], []
        for bucket, value in groups:
            if not bucket:
                continue
            labels.append(bucket.strftime('%b %Y' if granularity == 'month' else '%d %b'))
            values.append(round(value or 0.0, 2))
        return {'labels': labels, 'values': values}

    @api.model
    def _sgc_kpi(self, key, label, value, **kw):
        """Normalised KPI envelope consumed by the OWL layer."""
        vals = {
            'key': key,
            'label': label,
            'value': value,
            'format': kw.get('format', 'number'),   # number|currency|percent|duration
            'icon': kw.get('icon', self._sgc_icon),
            'accent': kw.get('accent', self._sgc_accent),
            'delta': kw.get('delta'),               # signed % vs previous period
            'target': kw.get('target'),
            'spark': kw.get('spark'),               # list[float] for the sparkline
            'hint': kw.get('hint', ''),
            'action': kw.get('action'),             # {'type':'ir.actions.act_window', ...}
            'span': kw.get('span', 1),
        }
        return vals

    @api.model
    def _sgc_delta(self, current, previous):
        if not previous:
            return None
        return round(((current - previous) / abs(previous)) * 100.0, 1)

    @api.model
    def _sgc_previous_range(self, ctx):
        """Equivalent-length window immediately preceding the active one."""
        start, end = ctx['date_from'], ctx['date_to']
        span = (end - start).days + 1
        return start - relativedelta(days=span), start - relativedelta(days=1)
