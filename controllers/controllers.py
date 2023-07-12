# -*- coding: utf-8 -*-
from odoo import http, _
import json
import uuid
import werkzeug.utils


""" class UltramsgController(http.Controller):
    @http.route('/ultramsg/instance/<string:instance_id>', type='json', auth="none", csrf=False)
    def update_status(self, instance_id, **kw):
        print(instance_id)
        print(kw)
        
        instance = http.request.env['ultramsg.instance'].sudo().search([
            ('instance_id', '=', instance_id),])
        
        print(instance)

        http.request.env['ultramsg.update'].sudo().create({
                'instance_id': instance_id,
                'raw_data': kw,
            }) """
