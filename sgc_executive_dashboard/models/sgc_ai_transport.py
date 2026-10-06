# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
"""Shared LLM transport — reuses `sgc_ai_powerbox`'s exact config-parameter
surface (`sgc_ai.*`) so both modules share one place to set keys, with zero
manifest dependency and zero regression risk to that live module. This is
config-surface reuse only, not code reuse — `sgc_ai_powerbox` exposes its
LLM access solely via an HTTP controller (no callable model method), so this
model is a from-scratch, server-side-callable equivalent.
"""
import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Mirrors sgc_ai_powerbox's parameter contract exactly — one config surface.
PROVIDERS = {
    'default': {
        'endpoint': ('sgc_ai.api_endpoint',
                     'http://freellmapi-prod:3001/v1/chat/completions'),
        'key': ('sgc_ai.api_key', ''),
        'model': ('sgc_ai.model', 'nemotron-3-super-120b'),
        'label': 'Default (internal)',
    },
    'minimax': {
        'endpoint': ('sgc_ai.minimax_endpoint',
                     'https://api.minimax.io/v1/chat/completions'),
        'key': ('sgc_ai.minimax_api_key', ''),
        'model': ('sgc_ai.minimax_model', 'MiniMax-M2.7'),
        'label': 'MiniMax',
    },
}


class SgcAiTransport(models.AbstractModel):
    _name = 'sgc.ai.transport'
    _description = 'SGC AI Transport (shared with sgc_ai_powerbox config)'

    @api.model
    def provider_status(self):
        """Which providers are actually usable right now. Never leaks keys."""
        ICP = self.env['ir.config_parameter'].sudo()
        out = []
        for code, cfg in PROVIDERS.items():
            key = ICP.get_param(cfg['key'][0], cfg['key'][1])
            out.append({
                'code': code,
                'label': cfg['label'],
                'model': ICP.get_param(cfg['model'][0], cfg['model'][1]),
                'configured': bool(key and key.strip()),
                'param': cfg['key'][0],
            })
        return out

    @api.model
    def powerbox_available(self):
        """Soft detection — informational only, never a hard requirement."""
        return bool(self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'sgc_ai_powerbox'),
            ('state', 'in', ('installed', 'to upgrade'))]))

    @api.model
    def complete(self, system, user, provider='default', max_tokens=2048,
                 timeout=45, temperature=0.1):
        ICP = self.env['ir.config_parameter'].sudo()
        cfg = PROVIDERS.get(provider) or PROVIDERS['default']
        endpoint = ICP.get_param(cfg['endpoint'][0], cfg['endpoint'][1])
        api_key = ICP.get_param(cfg['key'][0], cfg['key'][1])
        model = ICP.get_param(cfg['model'][0], cfg['model'][1])

        if not (api_key and api_key.strip()):
            raise UserError(_(
                "SGC AI is not configured for the '%(p)s' provider. Set the "
                "system parameter '%(k)s' in Settings -> Technical -> System "
                "Parameters.", p=cfg['label'], k=cfg['key'][0]))

        try:
            response = requests.post(
                endpoint, timeout=timeout,
                headers={'Authorization': f'Bearer {api_key}',
                         'Content-Type': 'application/json'},
                json={'model': model, 'temperature': temperature,
                      'max_tokens': max_tokens,
                      'messages': [{'role': 'system', 'content': system},
                                   {'role': 'user', 'content': user}]})
            response.raise_for_status()
        except requests.Timeout:
            raise UserError(_(
                "The AI backend did not respond within %ss. Large models can "
                "exceed this on complex requests -- try a preset, or switch "
                "provider.", timeout))
        except requests.RequestException as err:
            _logger.warning("SGC AI transport failure: %s", err)
            raise UserError(_("The AI backend is unreachable right now."))

        try:
            data = response.json()
        except ValueError:
            raise UserError(_("The AI backend returned an unreadable payload."))

        # MiniMax can return HTTP 200 with an error embedded in base_resp
        # (e.g. insufficient balance, invalid params) instead of a non-2xx
        # status code -- without this check that error reads as success.
        base_resp = data.get('base_resp') or {}
        if base_resp.get('status_code') not in (0, None):
            _logger.error("SGC AI (%s) base_resp error: %s", provider, base_resp)
            raise UserError(_(
                "AI service error: %s", base_resp.get('status_msg') or base_resp))

        try:
            return data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise UserError(_("The AI backend returned an unexpected payload."))

    @api.model
    def complete_json(self, system, user, provider='default', **kw):
        """Same call, but tolerant extraction of a JSON object."""
        raw = self.complete(system + "\n\nRespond with JSON only.",
                             user, provider=provider, **kw)
        cleaned = (raw or '').strip()
        if '```' in cleaned:
            parts = cleaned.split('```')
            cleaned = max(parts, key=len)
            if cleaned.lower().startswith('json'):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned[cleaned.index('{'):cleaned.rindex('}') + 1])
        except (ValueError, IndexError):
            _logger.warning("SGC AI: unparseable JSON: %s", (raw or '')[:400])
            return None
