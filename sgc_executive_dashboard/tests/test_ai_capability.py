# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Tests for sgc.capability -- the hardcoded safety allowlist that
sgc.provider.dynamic validates every AI-driven query against.
"""
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAiCapability(TransactionCase):

    def test_installed_models_are_present_and_pruned_correctly(self):
        Capability = self.env['sgc.capability']
        caps = Capability.available_capabilities()

        for model_name, cap in caps.items():
            self.assertIn(model_name, self.env.registry.models)
            Model = self.env[model_name]
            for role in ('date_fields', 'measures'):
                for field_name in cap[role]:
                    field = Model._fields.get(field_name)
                    self.assertIsNotNone(
                        field, f"{model_name}.{field_name} ({role}) must exist")
                    self.assertTrue(
                        field.store,
                        f"{model_name}.{field_name} ({role}) must be stored")
            for field_name in cap['groups']:
                field = Model._fields.get(field_name)
                self.assertIsNotNone(field)
                self.assertIn(field.type, (
                    'many2one', 'selection', 'char', 'boolean', 'date', 'datetime'))

    def test_computed_nonstored_fields_are_excluded(self):
        """construction.project.progress/planned_progress/open_ncr_count and
        kyc.application.is_kyc_complete are computed, non-stored fields per
        the providers' own code comments -- they must never appear in any
        role, on any model, ever.
        """
        Capability = self.env['sgc.capability']
        caps = Capability.available_capabilities()

        excluded = {
            'construction.project': ('progress', 'planned_progress', 'open_ncr_count'),
            'kyc.application': ('is_kyc_complete',),
        }
        for model_name, bad_fields in excluded.items():
            cap = caps.get(model_name)
            if not cap:
                continue  # gating module not installed in this DB -- fine
            all_listed = set(cap['date_fields']) | set(cap['measures']) \
                | set(cap['groups']) | set(cap['filters'])
            for bad_field in bad_fields:
                self.assertNotIn(
                    bad_field, all_listed,
                    f"{model_name}.{bad_field} is computed/non-stored and "
                    f"must never be allowlisted in any role")

    def test_field_info_rejects_unlisted_fields(self):
        Capability = self.env['sgc.capability']
        self.assertIsNone(Capability.field_info('res.users', 'login'))
        self.assertIsNone(Capability.field_info('res.users', 'password'))
        self.assertIsNone(Capability.field_info('ir.config_parameter', 'value'))
        self.assertIsNone(Capability.field_info('sale.order', 'not_a_real_field'))

    def test_disallowed_models_are_never_allowlisted(self):
        Capability = self.env['sgc.capability']
        for model_name in ('res.users', 'res.company', 'ir.config_parameter',
                           'ir.module.module', 'stock.picking', 'mrp.production'):
            self.assertFalse(
                Capability.is_model_allowed(model_name),
                f"{model_name} must never be an allowlisted model")

    def test_describe_for_llm_returns_nonempty_string(self):
        Capability = self.env['sgc.capability']
        description = Capability.describe_for_llm()
        self.assertIsInstance(description, str)
        self.assertTrue(description.strip())
