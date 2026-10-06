# -*- coding: utf-8 -*-
# Part of SGC UI Brand Palette (standalone, v19.0.2.0.0).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Passthrough to the two colours that already exist on res.company
    # (defined by Odoo's own `web` module for document/report branding).
    # Reusing them here — under a new field name scoped to this
    # module's settings panel — means a tenant configures their brand
    # colour ONCE and it drives both PDF documents and the backend UI.
    sgc_brand_primary_color = fields.Char(
        related="company_id.primary_color", readonly=False,
        string="Primary colour",
    )
    sgc_brand_secondary_color = fields.Char(
        related="company_id.secondary_color", readonly=False,
        string="Secondary colour",
    )

    # Genuinely new fields (defined on res.company by this module).
    sgc_brand_link_color = fields.Char(
        related="company_id.brand_link_color", readonly=False,
        string="Link colour override",
    )
    sgc_brand_navbar_bg_color = fields.Char(
        related="company_id.brand_navbar_bg_color", readonly=False,
        string="Navbar background",
    )
    sgc_brand_navbar_text_color = fields.Char(
        related="company_id.brand_navbar_text_color", readonly=False,
        string="Navbar text",
    )

    def action_sgc_reset_brand_defaults(self):
        self.ensure_one()
        self.company_id.action_reset_brand_defaults()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
