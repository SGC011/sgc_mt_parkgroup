# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""HTTP smoke tests for the 5 new AI controller routes, mirroring
test_http.py's pattern for the original 2 routes.
"""
import json

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAiHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        viewer_group = cls.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_viewer')
        cls.viewer_login = 'sgc_ai_http_viewer_test'
        cls.viewer_password = 'sgc_ai_http_viewer_pwd_123!'
        cls.viewer_user = cls.env['res.users'].create({
            'name': 'SGC AI HTTP Viewer',
            'login': cls.viewer_login,
            'email': 'sgc_ai_http_viewer_test@sgctech.ai',
            'password': cls.viewer_password,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, viewer_group.id),
            ],
        })
        cls.plain_login = 'sgc_ai_http_plain_test'
        cls.plain_password = 'sgc_ai_http_plain_pwd_123!'
        cls.plain_user = cls.env['res.users'].create({
            'name': 'SGC AI HTTP Plain User',
            'login': cls.plain_login,
            'email': 'sgc_ai_http_plain_test@sgctech.ai',
            'password': cls.plain_password,
            'group_ids': [(4, cls.env.ref('base.group_user').id)],
        })

    def _jsonrpc(self, route, params):
        payload = {'jsonrpc': '2.0', 'method': 'call', 'params': params}
        response = self.url_open(
            route, data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_ai_meta_route(self):
        self.authenticate(self.viewer_login, self.viewer_password)
        body = self._jsonrpc('/sgc_executive_dashboard/ai_meta', {})
        self.assertNotIn('error', body, body.get('error'))
        result = body['result']
        self.assertIn('presets', result)
        self.assertIn('providers', result)
        self.assertTrue(result['presets'], "Expected the 5 shipped presets to be visible")

    def test_preset_route_anomaly_scan(self):
        self.authenticate(self.viewer_login, self.viewer_password)
        preset = self.env.ref('sgc_executive_dashboard.preset_anomaly_scan')
        body = self._jsonrpc('/sgc_executive_dashboard/preset',
                             {'preset_id': preset.id, 'period': 'ytd'})
        self.assertNotIn('error', body, body.get('error'))
        self.assertTrue(body['result'].get('ok'))

    def test_route_plan_only_is_fast_and_llm_free(self):
        self.authenticate(self.viewer_login, self.viewer_password)
        body = self._jsonrpc('/sgc_executive_dashboard/route', {
            'prompt': 'why did margin drop', 'context': {'plan_only': True},
        })
        self.assertNotIn('error', body, body.get('error'))
        result = body['result']
        self.assertTrue(result.get('ok'))
        self.assertTrue(result.get('deferred'))
        self.assertEqual(result.get('intent'), 'explain')

    def test_non_viewer_denied_on_every_new_route(self):
        self.authenticate(self.plain_login, self.plain_password)
        preset = self.env.ref('sgc_executive_dashboard.preset_anomaly_scan')

        for route, params in [
            ('/sgc_executive_dashboard/ai_meta', {}),
            ('/sgc_executive_dashboard/preset',
             {'preset_id': preset.id, 'period': 'ytd'}),
            ('/sgc_executive_dashboard/route', {'prompt': 'brief'}),
            ('/sgc_executive_dashboard/enqueue', {'prompt': 'brief'}),
        ]:
            body = self._jsonrpc(route, params)
            self.assertIn(
                'error', body,
                f"Expected an AccessError JSON-RPC error from {route} for "
                f"a non-viewer user, got a successful result")
