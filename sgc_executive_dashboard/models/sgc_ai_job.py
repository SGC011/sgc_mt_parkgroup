# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Async job queue so a 60s+ narrative preset never blocks a request past
nginx/worker timeouts. Deterministic presets bypass this entirely and
return synchronously (see the /preset controller route).

Two lines of defence around job visibility: the inline `user_id` check in
`poll()` (cheap, obvious) and the real boundary, an `ir.rule` in
`security/sgc_ai_security.xml` restricting non-admin users to their own
records at the ORM level -- the inline check alone would not stop a raw
`search()`/`read()` on this model from leaking another executive's
prompts/results.
"""
import datetime
import json
import logging

from odoo import _, api, fields, models
from odoo.tools import config as odoo_config

_logger = logging.getLogger(__name__)

_MAX_JOBS_PER_CRON_RUN = 5
_JOB_RETENTION_DAYS = 7


class SgcAiJob(models.Model):
    _name = 'sgc.ai.job'
    _description = 'SGC AI Async Job'
    _order = 'id desc'

    preset_id = fields.Many2one('sgc.ai.preset', ondelete='cascade')
    prompt = fields.Char()
    period = fields.Char(default='ytd')
    state = fields.Selection(
        [('queued', 'Queued'), ('running', 'Running'),
         ('done', 'Done'), ('failed', 'Failed')], default='queued', index=True)
    result_json = fields.Text()
    error = fields.Char()
    user_id = fields.Many2one('res.users', default=lambda s: s.env.user, index=True)
    started_at = fields.Datetime(readonly=True)
    ended_at = fields.Datetime(readonly=True)

    @api.model
    def enqueue(self, preset_id=None, prompt=None, period='ytd'):
        self.env['sgc.executive.dashboard']._sgc_check_access()
        job = self.create({
            'preset_id': preset_id,
            'prompt': prompt,
            'period': period,
            'user_id': self.env.user.id,   # forced -- never taken from the caller
        })
        cron = self.env.ref('sgc_executive_dashboard.cron_ai_jobs', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return {'job_id': job.id}

    def poll(self):
        self.ensure_one()
        if self.user_id != self.env.user and not self.env.user.has_group('base.group_system'):
            return {'state': 'failed', 'error': _('Not your job.')}
        return {
            'state': self.state,
            'error': self.error,
            'result': json.loads(self.result_json) if self.result_json else None,
        }

    def _sgc_commit(self):
        """No-op when the process was launched with --test-enable -- a raw
        commit() there would corrupt the Stage 3 test run, since tests
        execute inside a transaction that's rolled back at the end, not
        actually committed. (`Registry.in_test_mode()` does not exist in
        this Odoo version -- `config['test_enable']` is the real,
        process-wide marker the test runner sets.)
        """
        if odoo_config['test_enable']:
            return
        self.env.cr.commit()

    @api.model
    def _cron_process(self):
        # sudo() so the cron (running as its configured user) sees every
        # user's queued jobs, not just its own -- the ir.rule on this model
        # would otherwise hide them from a non-admin cron identity.
        jobs = self.sudo().search([('state', '=', 'queued')], limit=_MAX_JOBS_PER_CRON_RUN)
        for job in jobs:
            job.write({'state': 'running', 'started_at': fields.Datetime.now()})
            job._sgc_commit()
            try:
                job_as_user = job.with_user(job.user_id) if job.user_id else job
                if job.preset_id:
                    result = job.preset_id.with_user(job.user_id).run({'period': job.period})
                else:
                    result = job_as_user.env['sgc.ai.intent'].sgc_route(
                        job.prompt, {'period': job.period})
                job.write({
                    'state': 'done',
                    'result_json': json.dumps(result, default=str),
                    'ended_at': fields.Datetime.now(),
                })
            except Exception as err:
                _logger.exception("SGC AI job %s failed", job.id)
                job.write({'state': 'failed', 'error': str(err)[:500],
                          'ended_at': fields.Datetime.now()})
            job._sgc_commit()

    @api.model
    def _cron_gc(self):
        cutoff = fields.Datetime.now() - datetime.timedelta(days=_JOB_RETENTION_DAYS)
        stale = self.sudo().search([
            ('state', 'in', ('done', 'failed')),
            ('write_date', '<', cutoff),
        ])
        stale.unlink()
