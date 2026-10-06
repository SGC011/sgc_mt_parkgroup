# (c) SGC TECH AI (https://sgctech.ai)
from . import models
from . import controllers

_SGC_SEED_KPI_DEFINITIONS = [
    {'code': 'def_sale_revenue', 'name': 'Confirmed Sales Revenue',
     'model_name': 'sale.order', 'aggregate': 'sum',
     'measure_field': 'amount_untaxed', 'date_field': 'date_order',
     'domain_json': "[('state', 'in', ['sale', 'done'])]",
     'value_format': 'currency', 'sequence': 10},
    {'code': 'def_invoiced', 'name': 'Customer Invoiced',
     'model_name': 'account.move', 'aggregate': 'sum',
     'measure_field': 'amount_untaxed_signed', 'date_field': 'invoice_date',
     'domain_json': "[('move_type', '=', 'out_invoice')]",
     'value_format': 'currency', 'sequence': 20},
    {'code': 'def_spend', 'name': 'Committed Procurement Spend',
     'model_name': 'purchase.order', 'aggregate': 'sum',
     'measure_field': 'amount_untaxed', 'date_field': 'date_approve',
     'domain_json': "[('state', 'in', ['purchase', 'done'])]",
     'value_format': 'currency', 'sequence': 30},
    {'code': 'def_pipeline', 'name': 'Open Pipeline Value',
     'model_name': 'crm.lead', 'aggregate': 'sum',
     'measure_field': 'expected_revenue', 'date_field': 'create_date',
     'domain_json': '[]', 'value_format': 'currency', 'sequence': 40},
    {'code': 'def_tasks_due', 'name': 'Project Tasks by Deadline',
     'model_name': 'project.task', 'aggregate': 'count',
     'date_field': 'date_deadline', 'domain_json': '[]',
     'value_format': 'number', 'sequence': 50},
    {'code': 'def_meetings', 'name': 'Video Meetings Held',
     'model_name': 'video.meeting', 'aggregate': 'count',
     'date_field': 'start_time', 'domain_json': '[]',
     'value_format': 'number', 'sequence': 60},
]


def _sgc_seed_ai_definitions(env):
    """Best-effort seed data for the AI anomaly scan.

    Deliberately a Python post-init hook, not a plain XML data file: this
    module has no hard dependency on sale_management/crm/purchase/account/
    project/sgc_video_conferencing (by design -- it must install cleanly on
    any bare Odoo 19 database), but `sgc.kpi.definition`'s own
    `@api.constrains` re-validates every definition against the
    `sgc.capability` allowlist, which rejects a model that isn't installed.
    A plain noupdate XML data file would hard-fail the whole module install
    the first time any one of these optional modules is missing. Seeding
    here, one record at a time with its own try/except, means a missing
    module just means fewer seed definitions -- never a broken install.
    """
    KpiDefinition = env['sgc.kpi.definition'].sudo()
    for vals in _SGC_SEED_KPI_DEFINITIONS:
        if KpiDefinition.search_count([('code', '=', vals['code'])]):
            continue
        try:
            KpiDefinition.create(dict(vals, source='shipped'))
        except Exception:
            # Model not installed / field renamed by a later Odoo version --
            # skip this one seed definition, never break the install.
            continue


def post_init_hook(env):
    _sgc_seed_ai_definitions(env)
