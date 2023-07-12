# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round
from lxml import etree
import base64
import io
import pandas as pd
from ..utils.funcs import is_phone_number, format_phone_number

Max_UPLOAD_SIZE = "5242880"
MIMETYPE = "text/csv"

class SendWizard(models.TransientModel):
    _name = "ultramsg.wizard.send"
    _description = "Wizard for sending text message"

    instance_id = fields.Many2one('ultramsg.instance', string='Instance', required=True)
    message_id = fields.Many2one('ultramsg.message', string='Select Message')
    message_body = fields.Text(related='message_id.body', string='Message Body')
    message = fields.Text(string='Enter Message')
    

    def temp_mobile(self, number):
        name = "Ultramsg Send Wizard Temp Mobile Number"
        mobile_no =  self.env['ultramsg.moblie_no'].search(['|', ('name', '=', name), ('number', '=', number)])
        if mobile_no:
            return mobile_no
         
        return self.env['ultramsg.moblie_no'].create({
                'name': name, 'number': number    
            })
        

    def action_send(self):
        print('*' * 100)
        print(self.env.context)
        data = self.read(['instance_id', 'message_id', 'message'])[0]
        if not (data['message_id'] or data['message']):
            raise UserError(_('Select or enter a message'))
        
        instance = self.env['ultramsg.instance'].browse(data['instance_id'][0])
        message = data['message'] or self.env['ultramsg.message'].browse(data['message_id'][0]).body
        
        active_model = self.env.context.get('active_model', '')
        if active_model == 'ultramsg.moblie_no':
            mobile_no =  self.env['ultramsg.moblie_no'].browse(self.env.context.get('active_ids'))
        elif active_model == 'res.partner':
            number =  self.env['res.partner'].browse(self.env.context.get('active_ids')).ultramsg_number
            mobile_no = self.temp_mobile(number)
        else:
            raise ValidationError(_('Uknown model for Ultramsg: ') + active_model)

        sent, instance_connected = mobile_no.send_text(instance, message)
        if sent:
            return {
                'effect': {
                    'fadeout': 'slow',
                        'message': _('Your message was sent.'),
                        'type': 'rainbow_man',
                        } 
                }
        
        if instance_connected:
            raise ValidationError(_('Message not sent, please ensure mobile number have WhatsApp'))
        else:
            raise ValidationError(_('Message not sent, please check Ultramsg instance'))
        

        

class AddNumbersWizard(models.TransientModel):
    _name = "ultramsg.wizard.add_numbers"
    _description = "Wizard for adding numbers to send group from a CSV file"

    numbers_file = fields.Binary(required=True)
    file_name = fields.Char()
    number_column = fields.Char(string='Number', required=True, help="The label of the number column in the CSV file")
    name_column = fields.Char(string='Name', required=True, help="The label of the name column in the CSV file")
    

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(AddNumbersWizard, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(result['arch'])
            _file = doc.xpath("//field[@name='numbers_file']")
            if _file:
                _file[0].set("max_upload_size", Max_UPLOAD_SIZE)
                _file[0].set("mimetype", MIMETYPE)
                result['arch'] = etree.tostring(doc, encoding='unicode')
        return result


    def action_import(self):
        data = self.read(['numbers_file', 'file_name', 'number_column', 'name_column'])[0]

        if data['file_name'].split('.')[-1] != 'csv':
            raise ValidationError(_('The selected file must be of type "csv"'))
        
        # create df, check if not empty or file not corrupted
        # all types object so validation 
        try:
            with io.BytesIO(base64.b64decode(data['numbers_file'])) as f:
                df = pd.read_csv(f, dtype=str)
        except Exception as e:
            raise ValidationError(_('ERROR while readig the file: ') + str(e))

        if df.size <0 :
            raise ValidationError(_('The file is empty!!'))
        
        df.columns = [col.strip() for col in df.columns]
        number_col = data['number_column'].strip() 
        name_col = data['name_column'].strip()
        # check cols labels
        try:
            df = df[[number_col, name_col]]
        except Exception as e:
            raise ValidationError(str(e))
        
        df.columns = ['number', 'name']
        number_col, name_col = df.columns.to_list()
        
        n_records = len(df)
        n_nan = df[number_col].isna().sum()
        df = df.dropna()

        n_duplicates = df.duplicated(subset=number_col).sum()
        df = df.drop_duplicates(subset=number_col)
        
        df[number_col] = df[number_col].apply(format_phone_number)
        df['check'] = df[number_col].apply(self.check_number)

        df_valid = df.query('check == 1')[[number_col, name_col]]
        n_invalid = len(df.query('check == 0'))
        df_exists = df.query('check == 2')[[number_col, name_col]]
        df_ingroup = df.query('check == 2')[number_col].to_list()

        new_phones = self.env['ultramsg.moblie_no'].create(df_valid.to_dict(orient="records"))
        current_phones = self.env['ultramsg.moblie_no'].search([('number', 'in', df_exists[number_col].to_list())])
        self.env['ultramsg.send_group'].browse(self.env.context.get('active_ids')).write({
            'mobile_no_ids': [(4, id) for id in (new_phones + current_phones).ids]
        })

        df['status'] = df['check'].replace({
            0: 'invalid',
            1: 'created_and_added',
            2: 'added',
            3: 'skipped',
        })
        temp_mobiles = self.env['ultramsg.temp_mobile'].create(df[[number_col, 'status']].to_dict(orient="records"))
        action = self.env.ref('wt_ultramsg.import_mobile_numbers_result_action').read()[0]
        action.update({
            'target': 'new',
            'context': {
                'default_file_name': data['file_name'],
                'default_n_records': n_records,
                'default_n_nan': n_nan,
                'default_n_duplicates': n_duplicates,
                'default_n_invalid': n_invalid,
                'default_mobile_ids': [(4, id) for id in temp_mobiles.ids],
                }
            })
        return action


    def check_number(self, number):
        """
        Check number is valid and if it already added:
        0 invalid number
        1 valid not added
        2 already exists
        3 already in group
        """
        if is_phone_number(number):
            phone_number = self.env['ultramsg.moblie_no'].search([('number', '=', number)])
            if phone_number:
                if phone_number in self.env['ultramsg.send_group'].browse(self.env.context.get('active_ids')).mobile_no_ids:
                    return 3
                return 2
            return 1
        return 0


class TempMobile(models.TransientModel):
    _name = "ultramsg.temp_mobile"
    _description = "Temporary hold mobile number info to be used in the report"

    number = fields.Char(string='Number', required=True)
    status = fields.Selection([
            ('invalid', 'Invalid Number'), 
            ('created_and_added', 'Created and Added'),
            ('added', 'Added'), 
            ('skipped', 'Already in Group'),  
        ],
        required=True, 
        )



class AddNumbersResults(models.TransientModel):
    _name = "ultramsg.add_result"

    file_name = fields.Char(string='File Name', required=True)
    n_records = fields.Integer(string='Records in file', required=True)
    n_nan = fields.Integer(string='Empty numbers', required=True)
    n_duplicates = fields.Integer(string='Duplicated numbers', required=True)
    n_invalid = fields.Integer(string='Invalid numbers', required=True)
    mobile_ids = fields.Many2many('ultramsg.temp_mobile', required=True)



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    max_active_groups = fields.Integer("Max Active Groups", help="Maximmum number of active groups at the same time")
    min_duration = fields.Float('Duration HH:mm', help="Minimum duration between each message in a group")

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['max_active_groups'] = int(self.env['ir.config_parameter'].sudo().get_param('wt_ultramsg.max_active_groups'))
        res['min_duration'] = self.env['ir.config_parameter'].sudo().get_param('wt_ultramsg.min_duration')
        return res

    @api.model
    def set_values(self):
        message = ''
        res = self.env['ultramsg.send_group']
        if self.max_active_groups < res.n_active:
            message +=  '●    ' + _("Max active groups can't be less than current active groups") + f' ({res.n_active})'
        
        print('*' * 100)
        print(self.min_duration, max(self.min_duration, 1.0), res.smallest_duration, max(self.min_duration, 1.0) < res.smallest_duration)
        
        self.min_duration = max(self.min_duration, 1.0)
        if  self.min_duration < res.smallest_duration:
            # first value "self.min_duration" smaller
            message +=  '\n●    ' + _("Minimum duration can't be less than current minimum duration") + f' ({res.smallest_duration})'

        if message:
            raise ValidationError(message)
        else:
            self.env['ir.config_parameter'].sudo().set_param('wt_ultramsg.max_active_groups', self.max_active_groups or 1)
            
            self.env['ir.config_parameter'].sudo().set_param('wt_ultramsg.min_duration', self.min_duration)
        
        super(ResConfigSettings, self).set_values()



