# -*- coding: utf-8 -*-
{
    'name': "Ultramsg",

    'summary': """
        Ultramsg Implementation""",

    'description': """
        Send whatsapp messages usingUltramsg
    """,

    'author': "Ahmed Addawody",
    'website': "https://wide-techno.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Communications',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/sequrity.xml',
        'security/ir.model.access.csv',
        'wizard/wizard_views.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
