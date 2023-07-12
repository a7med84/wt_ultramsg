# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
from ..utils.funcs import validate_number, get_valid_number


ULTRAMSG_BASE_URL = "https://api.ultramsg.com/"


def get_ultramsg_data(url_extra, params=None, data=None, method='GET'):
    url = ULTRAMSG_BASE_URL + url_extra
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    return requests.request(method, url, headers=headers, params=params, data=data)


def get_status(response):
    '''
    Get the status of an ultramsg instance from response object
    Known responses:
        {"status":{"accountStatus":{"status":"standby","substatus":"normal"}}}

        {"status":{"accountStatus":{"status":"qr","substatus":"normal"}}}

        {"status":{"accountStatus":{"status":"authenticated","substatus":"connected"}}}

        {"error":"Wrong token. Please provide token as a GET parameter."}

        {'error': 'Instance not found'}

        {'error': 'Your instance has been Stopped due to non-payment. you can activate this instance by extending your subscription. Payment information updates every 5 minutes.'}
    '''
    result = response.json()
    err = result.get('error', '')
    if err:
        if 'Wrong token' in err:
            return 'token_error'
        elif 'Instance not found' in err:
            return 'instance_error'
        elif 'Stopped due to non-payment' in err:
            return "payment_error"
        else:
            return 'unknown_error'

    acc_status =  result.get('status', '')
    if acc_status:
        acc_status = acc_status.get('accountStatus', '')
    
    sub_status =acc_status.get('substatus', '')
    status = acc_status.get('status', '')

    if sub_status == 'connected':
        return 'connected'
    elif sub_status == 'normal':
        return 'disconnected'
    else:
        return 'unknown'


        
class UltramsgInstance(models.Model):
    _name = 'ultramsg.instance'
    _description = 'Ultramsg Instance Information'
    _order = 'create_date desc'
    _sql_constraints = [
        ('instance_id_uniq', 'unique (instance_id)', "instance_id already exists!"),
    ]

    name = fields.Char(help='Name to identify the instance', translate=True)
    linked_name = fields.Char(compute="_linked_comp", help='Name of linked whatsapp account')
    linked_number = fields.Char(compute="_linked_comp", help='Number of linked whatsapp account')
    instance_id = fields.Char(string="Instance ID", required=True, help='Ultramsg instance id')
    token = fields.Char(required=True, help='Ultramsg instance token')
    status = fields.Selection([
        ('connected', 'Connected'), 
        ('disconnected', 'Disconnected'), 
        ('expired', 'Expired'),
        ('token_error', 'Token Error'),
        ('instance_error', 'Not Found'),
        ('unknown_error', 'Unknown Error'),
        ('payment_error', 'Payment Error'),
        ('network_error', 'Network Error'),
        ('unknown', 'Unknown'),
        ],
        compute="_status_comp"
        )
    send_group_ids = fields.One2many('ultramsg.send_group', 'instance_id', string='Groups')
    message_report_ids = fields.One2many('ultramsg.message_report', 'instance_id', string='Sent Report')
        
    
    @api.depends('instance_id', 'token')
    def _status_comp(self):
        try:
            for rec in self:
                if not self.instance_id or not self.token:
                    rec.status = False
                else:
                    url_extra = self.instance_id + "/instance/status"
                    querystring = {
                        "token": self.token
                    }
                    
                    response = get_ultramsg_data(url_extra, params=querystring)
                    rec.status = get_status(response)
        except:
            rec.status = "network_error"


    @api.depends('instance_id', 'token')
    def _linked_comp(self):
        for rec in self:
            if not self.instance_id or not self.token:
                rec.linked_name = False
                rec.linked_number = False
            else:
                url_extra = self.instance_id + "/instance/me"
                querystring = {
                    "token": self.token
                }
                 
                response = get_ultramsg_data(url_extra, params=querystring)
                result = response.json()
                err = result.get('error', '')
                if err:
                    rec.linked_name = False
                    rec.linked_number = False
                else:    
                    rec.linked_name = result.get('name', '')
                    number = result.get('id', '')
                    if not number:
                        rec.linked_number = False
                    else:
                        rec.linked_number = number.split('@')[0] 
   

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



class UltramsgMobileNo(models.Model):
    _name = 'ultramsg.moblie_no'
    _sql_constraints = [
        ('number_uniq', 'unique (number)', "number already exists!"),
    ]

    number = fields.Char(required=True)
    name = fields.Char(translate=True)
    send_group_ids = fields.Many2many('ultramsg.send_group', string='Send Groups')
    message_report_ids = fields.One2many('ultramsg.message_report', 'mobile_no_id', string='Sent Report')
    

    @api.model
    def create(self, vals):
        if 'number' in vals:
            vals['number'] = validate_number(vals['number'])
        return super().create(vals)

    def write(self, vals):
        if 'number' in vals:
            vals['number'] = validate_number(vals['number'])
    

    def name_get(self):
        result = []         
        for rec in self:
            result.append((rec.id, f'{rec.name} - {rec.number}'))  
        return result
     
         
    def action_send_wizard(self):
        return self.env.ref('wt_ultramsg.send_whatsapp_message_wizard_action').read()[0]


    def send_text(self, instance, message, group=None):
        status = 'failed'
        result = None
        if instance.status != 'connected':
            result = {
                "sent": "false",
                'error': instance.name + ": " + instance.status
                }
        else:
            url_extra = instance.instance_id + "/messages/chat"
            payload = f"token={instance.token}&to={self.number}&body={message}"
            payload = payload.encode('utf8').decode('iso-8859-1')
                
            response = get_ultramsg_data(url_extra, data=payload, method="POST")
            result = response.json()

            if not result.get('error') and result.get('sent') == 'true' and result.get('message') == 'ok':
                status = "delivered"
        
        self.env['ultramsg.message_report'].create({
            'mobile_no_id': self.id,
            'mobile_no': self.number,
            'instance_id': instance.id,
            'ultramsg_instance': instance.name,
            'sending_acc': f"{instance.linked_number} {instance.linked_name}",
            'send_group': group.name if group else None,
            'send_group_id': group.id if group else None,
            'message': message,
            'respond_data': json.dumps(result, indent=4),
            'status': status
        })
        return status == 'delivered', instance.status == 'connected'



def min_duration(self):
    return float(self.env['ir.config_parameter'].get_param('wt_ultramsg.min_duration', 1.0))
    

def max_active_groups(self):
    return int(self.env['ir.config_parameter'].get_param('wt_ultramsg.max_active_groups', 5))


DEFAULT_MIN_DURATION = 1.0
DEFAULT_MAX_ACTIVE_GROUPS = 5.0

class UltramsgSendGroup(models.Model):
    _name = 'ultramsg.send_group'
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "name already exists!"),
    ]

    name = fields.Char(required=True, translate=True)
    is_active = fields.Boolean(string= 'Activate', default=False)
    duration = fields.Float('Duration HH:mm', default=min_duration, help="Durations between each message")
    iterations = fields.Integer(string='Iterations', default=1, help="Count of send iterations: '0' for infinite iterations")
    current_iteration = fields.Integer(string='Current Iteration', default=1)
    sent_to = fields.Text()
    sent_to_comp = fields.Char(string='Sent To', compute='_compute_sent_to')
    mobile_no_ids = fields.Many2many('ultramsg.moblie_no', string='Mobiles')
    message_id = fields.Many2one(string='Message', comodel_name='ultramsg.message', ondelete='set null')
    message_body = fields.Text(related='message_id.body', string='Message Body')
    instance_id = fields.Many2one(string='Instance', comodel_name='ultramsg.instance', ondelete='set null')
    is_sendable = fields.Boolean(compute='_compute_is_sendable')
    cron_id = fields.Integer()
    instance_is_connected = fields.Boolean(compute='_compute_instance_is_connected')
    message_report_ids = fields.One2many('ultramsg.message_report', 'send_group_id', string='Sent Report')
    
    
    def write(self, vals):
        rec = super(UltramsgSendGroup, self).write(vals)
        if 'is_active' in vals:
            cron = self.get_or_create_cron()
            if cron:
                cron.active = self.is_active
        return rec
    

    def unlink(self):
        if self.is_active:
            raise UserError(_("Can't delete an active group"))
        cron = self.get_or_create_cron(create=False)
        if cron:
            cron.unlink()
        return super().unlink()


    @api.depends('mobile_no_ids', 'message_id', 'instance_id')
    def _compute_is_sendable(self):
        for rec in self:
            rec.is_sendable = bool(rec.instance_id and rec.message_id and rec.mobile_no_ids)
            if not rec.is_sendable:
                rec.is_active = False
                cron = rec.get_or_create_cron()
                if cron:
                    cron.active = rec.is_active


    @api.depends('sent_to')
    def _compute_sent_to(self):
        for rec in self:
            html = '<ul class="list-group">'
            html += ''.join([f'<li class="list-group-item">{x.number} {x.name}</li>' for x in rec.sent_to_ids])
            html += '</ul>' 
            rec.sent_to_comp = html

    
    @api.depends('instance_id')
    def _compute_instance_is_connected(self):
        for rec in self:
            rec.instance_is_connected = not rec.instance_id or rec.instance_id.status == 'connected'


    @api.onchange('is_active')
    def onchange_is_active(self):
        if self.is_active and not self._origin.is_active:
            if self.sent_to:
                title = _("Warning")
                message = _("The group will be activated with these settings:") + "\n"
                message += "    ●" + "    " + _("Iterations: ") + str(self.iterations )+ "\n"
                message += "    ●" + "    " + _("Current iteration: ") + str(self.current_iteration) + "\n"
                message += "    ●" + "    " + _("Sent to:") + "\n"
                for x in self.sent_to_ids:
                    message += "    " +  "     ○" +  "    " + x.number + " " + x.name
                return {
                    'warning': {'title': title, 'message': message},
                }
            if self.n_active >= max_active_groups(self):
                title = _('Error')
                message = _("Active groups reached the maximum allowed, disable a group or contact the Administrator for more")
                self.is_active = False
                return {
                    'warning': {'title': title, 'message': message},
                }
        
    @property
    def cron(self):
        return self.env['ir.cron'].sudo().browse([self.cron_id])
    
    @property
    def sent_to_ids(self):
        sent_to = self.sent_to or ''
        return self.mobile_no_ids.browse([int(x) for x in sent_to.split(',') if x.isdigit()])

    @property
    def next_mob(self):
        mobs = self.mobile_no_ids - self.sent_to_ids
        return mobs[0], len(mobs) <= 1
    

    @property
    def n_active(self):
        return self.search_count([('is_active', '=', True)])


    @property
    def smallest_duration(self):
        groups = self.search([])
        if groups:
            return min([x.duration for x in groups])
        else:
            return DEFAULT_MIN_DURATION


    def get_or_create_cron(self, create=True):
        if not isinstance(self.id, int):
            # called from on change or befor creating object
            return
        cron = None
        if self.cron_id:
            cron = self.cron
            if cron:
                return cron
        if create:
            cron = self.env['ir.cron'].sudo().create({
                'name': f'Ultramsg: Send To Group {self.id}',
                'model_id': self.env['ir.model'].sudo().search([('model', '=', 'ultramsg.send_group')]).ids[0],
                'state': 'code',
                'code': f'model.action_group_send({self.id})',
                'interval_number': 1,
                'interval_type': 'minutes',
                'numbercall': -1,
                'doall': False,
                'active': self.is_active,
            })
            self.cron_id = cron.id
        return cron


    def sent_to_add_mob(self, _id=None):
        self.sent_to = self.sent_to + f',{_id}' if self.sent_to else f'{_id}'


    def action_reset_iterations(self):
        self.current_iteration = 1


    def action_clear_sent_to(self):
        self.sent_to = False


    def action_add_numbers_wizard(self):
        return self.env.ref('wt_ultramsg.import_mobile_numbers_wizard_action').read()[0]
    

    def action_confirmation_wizard(self):
        return self.env.ref('wt_ultramsg.confirmation_wizard_action').read()[0]
    

    def action_group_send(self, rec_id):
        rec = self.env['ultramsg.send_group'].browse(rec_id)

        # update rec.is_active if not is_sendable and return
        if not rec.is_sendable:
            rec.is_active = False
            return 

        mob, is_last = rec.next_mob
        sent, instance_connected = mob.send_text(rec.instance_id, rec.message_body, rec)

        # retun if instance not connected
        if not instance_connected:
            return
        
        if sent:
            rec.sent_to_add_mob(mob.id) 
            if is_last:
                # an iteration has ended
                rec.sent_to = False
                if not rec.iterations or rec.iterations > rec.current_iteration:
                    # reiterate
                    rec.current_iteration += 1
                else:
                    # deactivate
                    rec.is_active = False
                    rec.current_iteration = 1



class UltramsgMessageReport(models.Model):
    _name = 'ultramsg.message_report'

    mobile_no_id = fields.Many2one(string='To', comodel_name='ultramsg.moblie_no', ondelete='set null') 
    send_group_id = fields.Many2one(string='Send Group', comodel_name='ultramsg.send_group', ondelete='set null')
    instance_id = fields.Many2one(string='Instance', comodel_name='ultramsg.instance', ondelete='set null') 
    mobile_no = fields.Char('To', required=True)
    send_group = fields.Char('Send Group')
    ultramsg_instance = fields.Char('Instance', required=True)
    sending_acc = fields.Char('Linked whatsapp', required=True) 
    message = fields.Text('Message', required=True, translate=True)
    respond_data = fields.Text("Respond", required=True)
    status = fields.Selection([
        ('delivered', 'Delivered'), 
        ('failed', 'Failed'), 
        ],
        required=True, 
        )
    

class TextMessage(models.Model):
    _name = 'ultramsg.message'
    _sql_constraints = [
        ('title_uniq', 'unique (title)', "title already exists!"),
        ('body_uniq', 'unique (body)', "body already exists!"),
    ]

    title = fields.Char(string='Title', required=True, translate=True)
    body = fields.Text(string='Body', required=True, translate=True)
    send_group_ids = fields.One2many('ultramsg.send_group', 'message_id', string='Send Groups')

    def name_get(self):
        result = []         
        for rec in self:
            result.append((rec.id, rec.title))  
        return result



class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    ultramsg_number = fields.Char(compute='_compute_ultramsg_number')
    
    @api.depends('phone', 'mobile')
    def _compute_ultramsg_number(self):
        for record in self:
            record.ultramsg_number = get_valid_number(self.phone or self.mobile or '')

    def action_send_whatsapp(self):
        return self.env.ref('wt_ultramsg.send_whatsapp_message_wizard_action').read()[0]