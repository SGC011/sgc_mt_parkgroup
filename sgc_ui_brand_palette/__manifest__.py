# -*- coding: utf-8 -*-
# SGC TECH AI - UI Brand Palette
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)
# License OPL-1
{
    "name": "SGC TECH AI - UI Brand Palette",
    "version": "19.0.2.0.0",
    "category": "Theme/Brand",
    "summary": "Tenant-configurable UI colour palette (Primary, Secondary, Link, Navbar background, Navbar text) applied live to the backend web client via per-request CSS custom-property overrides",
    "description": """
SGC UI Brand Palette - Verdicta
===============================

Tenant-configurable UI colour palette. A "Brand & Theme" panel under
Settings lets any company/tenant set its own Primary, Secondary, Link,
Navbar background, and Navbar text colours. Colours are applied live to
the backend web client via a per-request CSS override (Bootstrap 5
custom properties + the top navbar), with zero SCSS recompilation -
safe on a single Odoo instance serving multiple companies with
different brand colours.

VENDOR NOTE (Verdicta, 30 Sep 2026)
-----------------------------------
Adapted from the sgc_mt tenant copy of sgc_ui_brand_palette
(manifest 19.0.2.0.0). The upstream 2.x menu-icon rebranding feature has
been REMOVED for this deployment: the `_register_hook` in
`models/ir_ui_menu.py` and all 23 bundled SGC menu icons under
`static/icons/` are gone, so Verdicta keeps stock Odoo menu icons. The
colour-palette feature is unmodified apart from this removal.
"""
,
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "OPL-1",
    "depends": [
        "base",
        "web",
        "base_setup",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "templates/web_layout.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
