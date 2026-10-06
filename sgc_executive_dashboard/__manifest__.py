# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
{
    'license': 'OPL-1',
    'price': 89,
    'currency': 'EUR',
    "name": "Executive Command Center",
    "version": "19.0.1.1.0",
    "category": "Productivity/Dashboard",
    "summary": "Unified C-level command center across every SGC application.",
    "description": """
SGC Executive Command Center
=============================
A single source of truth for executive decision making. Aggregates live KPIs
from every installed SGC/Odoo application (real estate, construction, deals,
commission, CRM & sales, purchase, finance, HR & UAE payroll, compliance/KYC,
projects, learning, video conferencing) and surfaces dormant applications as
capability gaps, without hard dependencies on any business module.

Also includes an AI command layer: one-click preset briefings (board pack,
cash risk, pipeline health, anomaly scan), free-text business questions
answered against a safety-validated, allowlisted query engine, and a
global Ctrl+K command-palette integration.
""",
    "author": "SGC TECH AI",
    "maintainer": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    "license": "OPL-1",
    # Intentionally minimal: business apps are discovered at runtime, never
    # force-installed just to power a KPI tile.
    "depends": ["base", "web"],
    "data": [
        "security/sgc_security.xml",
        "security/ir.model.access.csv",
        "security/sgc_ai_security.xml",
        "data/sgc_ai_cron.xml",
        "data/sgc_ai_presets.xml",
        "views/sgc_dashboard_views.xml",
        "views/sgc_ai_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sgc_executive_dashboard/static/src/scss/sgc_tokens.scss",
            "sgc_executive_dashboard/static/src/dashboard/**/*",
            "sgc_executive_dashboard/static/src/ai/**/*",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
