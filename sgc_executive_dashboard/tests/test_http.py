# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Lightweight HTTP smoke test for the /sgc_executive_dashboard/data route.

Covers spec §7 bullet: "Dashboard loads in <2s against the local dev DB" —
here we assert the controller route actually serves valid JSON over real
HTTP with an executive-viewer session; the <2s timing/full-UI E2E is
production-qa's Stage 5 job (real browser, real screenshots), not unit
test scope.
"""
import json
import time

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        viewer_group = cls.env.ref(
            'sgc_executive_dashboard.group_sgc_executive_viewer')
        cls.http_user_login = 'sgc_http_viewer_test'
        cls.http_user_password = 'sgc_http_viewer_pwd_123!'
        cls.http_user = cls.env['res.users'].create({
            'name': 'SGC HTTP Viewer',
            'login': cls.http_user_login,
            'email': 'sgc_http_viewer_test@sgctech.ai',
            'password': cls.http_user_password,
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, viewer_group.id),
            ],
        })

    def test_data_route_returns_dashboard_json(self):
        self.authenticate(self.http_user_login, self.http_user_password)

        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {'period': 'ytd'},
        }
        started = time.time()
        response = self.url_open(
            '/sgc_executive_dashboard/data',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        elapsed = time.time() - started

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn('error', body,
                          f"JSON-RPC error from /sgc_executive_dashboard/data: {body.get('error')}")
        self.assertIn('result', body)

        data = body['result']
        self.assertIn('meta', data)
        self.assertIn('sections', data)
        self.assertTrue(data['sections'], "Expected at least one provider section")

        # Soft perf signal only (spec's real <2s check is a Stage 5 E2E
        # measurement against the full UI, not this single controller call).
        self.assertLess(elapsed, 5.0,
                         "Dashboard data route took unexpectedly long")

    def test_backend_root_loads_for_authenticated_user(self):
        self.authenticate(self.http_user_login, self.http_user_password)
        response = self.url_open('/odoo')
        self.assertEqual(response.status_code, 200)
