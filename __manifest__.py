# -*- coding: utf-8 -*-
{
    'name': "Ultramsg Check",

    'summary': """
        Ultramsg instances status checking""",

    'description': """
        Check the status of Ultramsg instances and send notification via SMS if not working
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/sequrity.xml',
        'security/ir.model.access.csv',
        'views/log_views.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
