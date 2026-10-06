# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Tests for the sgc.executive.dashboard aggregator.

Covers spec §7 bullets:
- "All 12 providers return correct KPI values against the restored local
  dev DB" (existence/non-empty at the aggregator level; per-KPI value
  cross-checks are the debugger/production-qa's Stage 5 job, not unit
  test scope).
- Security boundary: dashboard restricted to executive users.
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

EXPECTED_PROVIDER_COUNT = 12


@tagged('post_install', '-at_install')
class TestAggregator(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer_group = cls.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_viewer')
        cls.viewer_user = cls.env['res.users'].create({
            'name': 'SGC Exec Viewer',
            'login': 'sgc_exec_viewer_test',
            'email': 'sgc_exec_viewer_test@sgctech.ai',
            # Internal-user base group plus the executive viewer group: a
            # dashboard viewer is a real internal user in practice, not a
            # bare group_sgc_executive_viewer-only account.
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.viewer_group.id),
            ],
        })
        cls.plain_user = cls.env['res.users'].create({
            'name': 'SGC Plain User',
            'login': 'sgc_plain_user_test',
            'email': 'sgc_plain_user_test@sgctech.ai',
            'group_ids': [(4, cls.env.ref('base.group_user').id)],
        })

    def test_dashboard_all_12_sections_present(self):
        dashboard = self.env['sgc.executive.dashboard'].with_user(
            self.viewer_user)
        data = dashboard.sgc_get_dashboard(period='ytd')

        self.assertIn('sections', data)
        self.assertIn('kpis', data)
        self.assertIn('charts', data)
        self.assertIn('meta', data)
        self.assertIn('universe', data)

        section_keys = {s['key'] for s in data['sections']}
        self.assertEqual(
            len(section_keys), EXPECTED_PROVIDER_COUNT,
            f"Expected {EXPECTED_PROVIDER_COUNT} provider sections (all "
            f"gating modules installed in demo_presentation_dev), got "
            f"{len(section_keys)}: {sorted(section_keys)}")

        self.assertTrue(data['kpis'], "Aggregated KPI list must be non-empty")
        self.assertTrue(data['charts'], "Aggregated chart list must be non-empty")

        # Every provider's gating module IS installed in this DB, so every
        # section must have actually collected KPIs (kpi_count > 0), never
        # silently degrade to the {'kpis': [], 'error': True} safe-fallback.
        broken = [s['key'] for s in data['sections'] if s['kpi_count'] == 0]
        self.assertFalse(
            broken,
            f"Providers returned zero KPIs (likely swallowed an exception "
            f"in _sgc_collect): {broken}")

    def test_ai_models_do_not_register_as_providers(self):
        """sgc.provider.dynamic must NEVER inherit sgc.kpi.provider -- the
        aggregator auto-discovers any model that does, and this would
        silently become a 13th dashboard section.
        """
        dashboard = self.env['sgc.executive.dashboard']
        providers = dashboard._sgc_providers()
        self.assertEqual(
            len(providers), EXPECTED_PROVIDER_COUNT,
            f"Expected exactly {EXPECTED_PROVIDER_COUNT} registered "
            f"providers, got {len(providers)}: {[p._name for p in providers]}")
        provider_names = {p._name for p in providers}
        self.assertNotIn('sgc.provider.dynamic', provider_names)

    def test_dashboard_denies_non_viewer(self):
        dashboard = self.env['sgc.executive.dashboard'].with_user(
            self.plain_user)
        with self.assertRaises(AccessError):
            dashboard.sgc_get_dashboard(period='ytd')

    def test_app_universe_sane_counts(self):
        dashboard = self.env['sgc.executive.dashboard'].with_user(
            self.viewer_user)
        universe = dashboard.sgc_get_app_universe()

        self.assertIn('installed_count', universe)
        self.assertIn('dormant_count', universe)
        self.assertIn('coverage', universe)

        self.assertGreater(universe['installed_count'], 0)
        self.assertEqual(
            universe['installed_count'] + universe['dormant_count'],
            len(universe['installed']) + len(universe['dormant']))
        self.assertGreaterEqual(universe['coverage'], 0.0)
        self.assertLessEqual(universe['coverage'], 100.0)
