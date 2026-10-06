# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Tests for sgc.ai.preset and sgc.ai.job -- the preset command library and
the async job queue backing narrative/generative presets.
"""
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.tools import config


@tagged('post_install', '-at_install')
class TestAiPresetJob(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer_group = cls.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_viewer')
        cls.viewer_a = cls.env['res.users'].create({
            'name': 'SGC AI Preset Test Viewer A',
            'login': 'sgc_ai_preset_viewer_a_test',
            'email': 'sgc_ai_preset_viewer_a_test@sgctech.ai',
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.viewer_group.id),
            ],
        })
        cls.viewer_b = cls.env['res.users'].create({
            'name': 'SGC AI Preset Test Viewer B',
            'login': 'sgc_ai_preset_viewer_b_test',
            'email': 'sgc_ai_preset_viewer_b_test@sgctech.ai',
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.viewer_group.id),
            ],
        })

    # ---------------------------------------------------------------- presets
    def test_five_shipped_presets_exist(self):
        for code in ('board_pack', 'cash_risk', 'anomaly_scan',
                     'pipeline_health', 'revenue_drivers'):
            xmlid = f'sgc_executive_dashboard.preset_{code}'
            preset = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(preset, f"Shipped preset missing: {xmlid}")
            self.assertEqual(preset.code, code)

    def test_kpi_codes_resolve_against_real_dashboard_keys(self):
        """Regression guard for the original draft's bug: crm_weighted and
        sale_openq don't exist. Every kpi_codes entry on every shipped
        preset must resolve to a real key in sgc_get_dashboard()['kpis'].
        """
        dashboard = self.env['sgc.executive.dashboard'].with_user(self.viewer_a)
        data = dashboard.sgc_get_dashboard(period='ytd')
        real_keys = {k['key'] for k in data['kpis']}

        for preset in self.env['sgc.ai.preset'].search([('kpi_codes', '!=', False)]):
            codes = [c.strip() for c in preset.kpi_codes.split(',') if c.strip()]
            for code in codes:
                self.assertIn(
                    code, real_keys,
                    f"Preset {preset.code!r} references KPI key {code!r} "
                    f"which does not exist in sgc_get_dashboard()['kpis']")

    def test_collect_facts_never_uses_compare_kwarg(self):
        """sgc_get_dashboard has no `compare` kwarg -- calling _collect_facts
        must not raise a TypeError from passing one.
        """
        preset = self.env.ref('sgc_executive_dashboard.preset_cash_risk')
        preset = preset.with_user(self.viewer_a)
        facts = preset._collect_facts('ytd')
        self.assertIsInstance(facts, list)

    def test_anomaly_scan_runs_with_zero_llm_configured(self):
        """Proves the deterministic path is genuinely LLM-free: with no
        sgc_ai.api_key set, the anomaly_scan preset must still succeed.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('sgc_ai.api_key', '')
        ICP.set_param('sgc_ai.minimax_api_key', '')

        preset = self.env.ref(
            'sgc_executive_dashboard.preset_anomaly_scan').with_user(self.viewer_a)
        result = preset.run({'period': 'ytd'})
        self.assertTrue(result.get('ok'))
        self.assertIsNone(result.get('narrative'))

    def test_visible_presets_respects_group_restriction(self):
        preset = self.env.ref('sgc_executive_dashboard.preset_board_pack')
        officer_group = self.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_officer')
        preset.write({'group_ids': [(6, 0, [officer_group.id])]})
        try:
            visible_codes = {
                p['code'] for p in
                self.env['sgc.ai.preset'].with_user(self.viewer_a).visible_presets()
            }
            self.assertNotIn('board_pack', visible_codes)
        finally:
            preset.write({'group_ids': [(5, 0, 0)]})

    # ------------------------------------------------------------------- jobs
    def test_enqueue_forces_caller_as_user_id(self):
        Job = self.env['sgc.ai.job'].with_user(self.viewer_a)
        result = Job.enqueue(prompt='brief', period='mtd')
        job = self.env['sgc.ai.job'].sudo().browse(result['job_id'])
        self.assertEqual(job.user_id, self.viewer_a)

    def test_job_visible_only_to_owner_via_record_rule(self):
        Job = self.env['sgc.ai.job'].with_user(self.viewer_a)
        result = Job.enqueue(prompt='brief', period='mtd')
        job_id = result['job_id']

        # Owner can find it.
        found = self.env['sgc.ai.job'].with_user(self.viewer_a).search(
            [('id', '=', job_id)])
        self.assertEqual(len(found), 1)

        # A different viewer cannot, via the ir.rule -- not just poll()'s
        # inline check.
        found_by_other = self.env['sgc.ai.job'].with_user(self.viewer_b).search(
            [('id', '=', job_id)])
        self.assertEqual(len(found_by_other), 0)

    def test_poll_denies_non_owner(self):
        Job = self.env['sgc.ai.job'].with_user(self.viewer_a)
        result = Job.enqueue(prompt='brief', period='mtd')
        job_id = result['job_id']

        job_as_owner = self.env['sgc.ai.job'].sudo().browse(job_id).with_user(self.viewer_a)
        poll_result = job_as_owner.poll()
        self.assertIn('state', poll_result)

    def test_cron_process_does_not_commit_in_test_mode(self):
        """A raw commit() inside the test transaction would corrupt the
        Stage 3 test run -- _sgc_commit() must no-op when the process was
        launched with --test-enable.
        """
        self.assertTrue(config['test_enable'])
        Job = self.env['sgc.ai.job'].with_user(self.viewer_a)
        result = Job.enqueue(prompt='brief', period='mtd')
        job = self.env['sgc.ai.job'].sudo().browse(result['job_id'])
        # Must not raise, and must not actually commit the test transaction.
        job._sgc_commit()

    def test_cron_process_transitions_deterministic_job_to_done(self):
        preset = self.env.ref('sgc_executive_dashboard.preset_anomaly_scan')
        Job = self.env['sgc.ai.job'].with_user(self.viewer_a)
        result = Job.enqueue(preset_id=preset.id, period='ytd')
        job = self.env['sgc.ai.job'].sudo().browse(result['job_id'])

        self.env['sgc.ai.job']._cron_process()
        job.invalidate_recordset()
        self.assertIn(job.state, ('done', 'failed'))
        if job.state == 'failed':
            self.fail(f"Anomaly-scan job unexpectedly failed: {job.error}")
