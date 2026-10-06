# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Table-driven security tests for sgc.provider.dynamic._sgc_validate --
the single choke point every AI-driven or AI-saved query must pass through.
Each "bad" case must raise UserError; each "good" case must succeed and the
executed domain must always carry the forced company/date scoping that the
caller-supplied spec cannot remove or override.
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAiDynamicSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer_group = cls.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_viewer')
        cls.viewer_user = cls.env['res.users'].create({
            'name': 'SGC AI Security Test Viewer',
            'login': 'sgc_ai_sec_viewer_test',
            'email': 'sgc_ai_sec_viewer_test@sgctech.ai',
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.viewer_group.id),
            ],
        })
        cls.dynamic = cls.env['sgc.provider.dynamic'].with_user(cls.viewer_user)

    def test_rejects_disallowed_model(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({'model_name': 'res.users', 'aggregate': 'count'})

    def test_rejects_config_parameter_model(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate(
                {'model_name': 'ir.config_parameter', 'aggregate': 'count'})

    def test_rejects_non_allowlisted_measure_field(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'account.move', 'aggregate': 'sum',
                'measure_field': 'id',
            })

    def test_rejects_computed_nonstored_measure_field(self):
        """construction.project.progress is computed/non-stored -- even if
        it were mistakenly added to the allowlist, the store-check in
        _sgc_validate must still reject it as a measure.
        """
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'construction.project', 'aggregate': 'sum',
                'measure_field': 'progress',
            })

    def test_rejects_dotted_domain_field_not_curated(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['partner_id.email', 'ilike', '@']],
            })

    def test_rejects_disallowed_operator_any(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['id', 'any', [['id', '=', 1]]]],
            })

    def test_rejects_disallowed_operator_inselect(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['id', 'inselect', 'SELECT 1']],
            })

    def test_rejects_dict_as_domain_value(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['state', '=', {'nested': 'dict'}]],
            })

    def test_rejects_nested_list_domain_value(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['state', 'in', [['nested', 'list']]]],
            })

    def test_rejects_oversized_string_value(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['state', 'ilike', 'x' * 300]],
            })

    def test_rejects_oversized_in_list(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['state', 'in', list(range(150))]],
            })

    def test_rejects_oversized_domain(self):
        domain = [['state', '=', 'sale'] for _ in range(25)]
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count', 'domain': domain,
            })

    def test_rejects_many2many_group_field(self):
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'group_field': 'message_follower_ids',
            })

    def test_limit_is_clamped_to_50(self):
        spec = self.dynamic._sgc_validate({
            'model_name': 'sale.order', 'aggregate': 'count', 'limit': 10000,
        })
        self.assertLessEqual(spec['limit'], 50)

    def test_valid_count_spec_succeeds(self):
        spec = self.dynamic._sgc_validate({
            'model_name': 'sale.order', 'aggregate': 'count',
            'domain': [['state', 'in', ['sale', 'done']]],
        })
        self.assertEqual(spec['model_name'], 'sale.order')
        self.assertEqual(spec['aggregate'], 'count')

    def test_valid_sum_with_group_field_succeeds(self):
        spec = self.dynamic._sgc_validate({
            'model_name': 'sale.order', 'aggregate': 'sum',
            'measure_field': 'amount_untaxed', 'group_field': 'partner_id',
            'domain': [['state', 'in', ['sale', 'done']]],
        })
        self.assertEqual(spec['measure_field'], 'amount_untaxed')
        self.assertEqual(spec['group_field'], 'partner_id')

    def test_execute_forces_company_and_date_scope(self):
        Dashboard = self.env['sgc.executive.dashboard'].with_user(self.viewer_user)
        ctx = Dashboard._sgc_context('ytd', None, None)
        spec = {
            'model_name': 'sale.order', 'aggregate': 'sum',
            'measure_field': 'amount_untaxed', 'date_field': 'date_order',
            'domain': [['state', 'in', ['sale', 'done']]],
        }
        result = self.dynamic._sgc_execute(spec, ctx)
        self.assertIsNotNone(result)
        domain_fields = {leaf[0] for leaf in result['domain'] if isinstance(leaf, (list, tuple))}
        self.assertIn('company_id', domain_fields)
        self.assertIn('date_order', domain_fields)

    def test_company_id_is_never_a_client_settable_filter(self):
        """company_id is deliberately absent from every model's `filters`
        allowlist -- company scoping is 100% server-forced via
        `company_field`/`_sgc_execute`, never something a spec can even
        mention, let alone override. Stronger than "gets AND'd together":
        the field simply isn't reachable from a caller-supplied domain.
        """
        with self.assertRaises(UserError):
            self.dynamic._sgc_validate({
                'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['company_id', 'in', [999999]]],
            })

    def test_execute_result_company_scope_matches_context_exactly(self):
        """The company scoping actually appended by _sgc_execute always
        matches ctx['company_ids'] verbatim -- there is no path for a
        caller to influence it.
        """
        Dashboard = self.env['sgc.executive.dashboard'].with_user(self.viewer_user)
        ctx = Dashboard._sgc_context('ytd', None, None)
        spec = {'model_name': 'sale.order', 'aggregate': 'count',
                'domain': [['state', 'in', ['sale', 'done']]]}
        result = self.dynamic._sgc_execute(spec, ctx)
        self.assertIsNotNone(result)
        company_leaves = [leaf for leaf in result['domain']
                          if isinstance(leaf, tuple) and leaf[0] == 'company_id']
        self.assertEqual(company_leaves, [('company_id', 'in', ctx['company_ids'])])
