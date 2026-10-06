# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
from odoo import _, api, models


class SgcProviderVideo(models.AbstractModel):
    _name = 'sgc.provider.video'
    _inherit = 'sgc.kpi.provider'
    _description = 'SGC Provider: Video Conferencing'

    _sgc_module = 'sgc_video_conferencing'
    _sgc_label = 'Video Conferencing'
    _sgc_icon = 'fa-video-camera'
    _sgc_accent = 'slate'
    _sgc_sequence = 12
    _sgc_pitch = 'Meeting cadence and platform adoption across the organisation.'

    @api.model
    def _sgc_collect(self, ctx):
        dom = [('start_time', '>=', ctx['dt_from']), ('start_time', '<=', ctx['dt_to'])]
        meetings = self._sgc_count('video.meeting', dom)
        minutes = self._sgc_sum('video.meeting', dom, 'actual_duration_minutes')
        trend = self._sgc_series('video.meeting', dom, 'start_time', None, ctx)

        # Adoption = distinct active users / headcount.
        Employee = self.env['hr.employee'].sudo()
        headcount = Employee.search_count([])
        if headcount:
            meeting_records = self.env['video.meeting'].sudo().search(dom)
            distinct_meeting_users = len({m.res_id for m in meeting_records if m.res_id})
        else:
            distinct_meeting_users = 0
        adoption_pct = (distinct_meeting_users / headcount * 100.0) if headcount else 0.0

        return {
            'kpis': [
                self._sgc_kpi('vc_meetings', _('Meetings Held'), meetings,
                              icon='fa-video-camera'),
                self._sgc_kpi('vc_minutes', _('Participant Minutes'), minutes,
                              format='duration', icon='fa-clock-o', accent='teal'),
                self._sgc_kpi('vc_adoption', _('Adoption'), round(adoption_pct, 1),
                              format='percent', icon='fa-users', accent='violet',
                              hint=_('Distinct active meeting users / headcount')),
            ],
            'charts': [{
                'key': 'vc_trend', 'title': _('Meeting Cadence'),
                'subtitle': _('Meetings per month'),
                'type': 'line', 'span': 2, 'accent': 'slate',
                'labels': trend['labels'],
                'datasets': [{'label': _('Meetings'), 'data': trend['values']}],
                'value_format': 'number',
            }] if trend['labels'] else [],
        }
