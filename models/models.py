# -*- coding: utf-8 -*-

from odoo import models, fields, api
import requests


'''
{"status":{"accountStatus":{"status":"standby","substatus":"normal"}}}

{"status":{"accountStatus":{"status":"qr","substatus":"normal"}}}

{"status":{"accountStatus":{"status":"authenticated","substatus":"connected"}}}

{"error":"Wrong token. Please provide token as a GET parameter."}

{'error': 'Instance not found'}
'''

def get_status(response):
    result = response.json()
    print('*' * 100)
    print(result)
    print(type(result))
    print('*' * 100)
    out = ''
    err = result.get('error', '')
    print(err)
    if err:
        if 'Wrong token' in err:
            return 'token_error'
        elif 'Instance not found' in err:
            return 'instance_error'
        else:
            return 'unknown_error'

    acc_status =  result.get('status', '')
    if acc_status:
        acc_status = acc_status.get('accountStatus', '')
    
    print(acc_status)

    sub_status =acc_status.get('substatus', '')
    status = acc_status.get('status', '')
    print(sub_status)
    print(status)

    if sub_status == 'connected':
        return 'connected'
    elif sub_status == 'normal':
        return 'disconnected'


        
class UltramsgInstance(models.Model):
    _name = 'ultramsg.instance'
    _description = 'Ultramsg Instance Information'
    _order = 'create_date desc'

    name = fields.Text(required=True, help='Name to identify the instance')
    instance_id = fields.Text(required=True, help='Ultramsg instance id')
    token = fields.Text(required=True, help='Ultramsg instance token')
    daily_checks = fields.Integer(required=True, help='Numebr of required daily cheacks')
    status = fields.Selection([
        ('connected', 'Connected'), 
        ('disconnected', 'Disconnected'), 
        ('expired', 'Expired'),
        ('token_error', 'Token Error'),
        ('instance_error', 'Not Found'),
        ('unknown_error', 'Unknown Error'),
        ],
        compute="_status_comp"
        )
        
    

    @api.depends('instance_id', 'token')
    def _status_comp(self):
        for rec in self:
            rec.status = rec.check_status()


    def check_status(self):
        if not self.instance_id or not self.token:
            return None
        
        url = f"https://api.ultramsg.com/{self.instance_id}/instance/status"

        querystring = {
            "token": self.token
        }

        headers = {'content-type': 'application/x-www-form-urlencoded'}

        response = requests.request("GET", url, headers=headers, params=querystring)
        return get_status(response)
    

    def _register_instance_url(self):
        instance_url = f"https://api.ultramsg.com/{self.instance_id}/instance/settings"
        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        payload = {
            "token": self.token,
            "sendDelay": 1,
            "webhook_url": url + f"/ultramsg/instance/{self.instance_id}"
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(instance_url, json=payload, headers=headers)

        print(response.json())


    @api.model
    def create(self, vals):
        print('creaaaaaaaaaaaaaaaaaaaaaaaat')
        print(vals)
        x = super(UltramsgInstance, self).create(vals)
        print('x', x)
        x._register_instance_url()
        return x



class UltramsgUpdate(models.Model):
    _name = 'ultramsg.update'
    _description = 'Ultramsg instance Status Update'
    _order = 'create_date desc'

    raw_data = fields.Text(required=True)
    # data = fields.Text(required=True)
    instance_id = fields.Many2one('ultramsg.instance', string='instance',)


