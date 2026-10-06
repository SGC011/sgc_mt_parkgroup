# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Unit tests for the sgc.kpi.provider base contract.

Covers spec §7 bullet: "Uninstalling any one of the 12 backing modules
causes that provider's section to disappear cleanly (dormant fallback),
no traceback." — exercised here at the single-provider unit level (the
aggregator-level "12 sections present" side is covered by
test_aggregator.py).
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestKpiProviderContract(TransactionCase):

    def test_run_returns_none_when_module_not_installed(self):
        """A provider whose _sgc_module is genuinely not installed must
        return None from _sgc_run (dormant fallback), never raise."""
        provider = self.env['sgc.kpi.provider']
        # Pick a module name that is certain not to exist/be installed.
        with patch.object(type(provider), '_sgc_module',
                           'sgc_definitely_not_a_real_module_xyz'):
            result = provider._sgc_run({})
        self.assertIsNone(result)

    def test_run_returns_well_formed_payload_when_installed(self):
        """A provider whose gating module IS installed returns a
        well-formed {'kpis': [...], 'charts': [...]} dict."""
        provider = self.env['sgc.provider.realestate']
        self.assertTrue(
            provider._sgc_is_installed(),
            "sgc_offplan_rental_property_management must be installed "
            "in this seeded DB for the test to be meaningful")

        dashboard = self.env['sgc.executive.dashboard']
        ctx = dashboard._sgc_context('ytd', None, None)
        payload = provider._sgc_run(ctx)

        self.assertIsNotNone(payload)
        self.assertIn('kpis', payload)
        self.assertIn('charts', payload)
        self.assertIsInstance(payload['kpis'], list)
        self.assertIsInstance(payload['charts'], list)
        self.assertNotIn('error', payload)
        # Sanity-check the KPI envelope shape for at least one entry.
        if payload['kpis']:
            kpi = payload['kpis'][0]
            for key in ('key', 'label', 'value', 'format', 'icon', 'accent'):
                self.assertIn(key, kpi)

    def test_run_catches_exception_in_collect(self):
        """A provider that raises inside _sgc_collect must be caught by
        _sgc_run and return the safe error envelope, never propagate."""
        provider = self.env['sgc.provider.realestate']
        self.assertTrue(provider._sgc_is_installed())

        def boom(self, ctx):
            raise ValueError("boom: simulated provider failure")

        with patch.object(type(provider), '_sgc_collect', boom):
            result = provider._sgc_run({})

        self.assertEqual(result, {'kpis': [], 'charts': [], 'error': True})
