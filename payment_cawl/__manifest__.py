# -*- coding: utf-8 -*-

{
    'name': 'CAWL Payment Provider',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Payment',
    'summary': 'Integrate CAWL payment services with Odoo',
    'description': """
        CAWL Payment Provider for Odoo

        Features:
        - Secure hosted checkout integration
        - Real-time webhook processing
        - Multi-currency support
        - Automatic payment confirmation
        - Refund processing
        - Comprehensive logging and error handling

        This module integrates with CAWL's payment platform to provide
        secure, reliable payment processing for your Odoo e-commerce.
    """,

    'license': 'AGPL-3',

    'depends': [
        'payment',
        'sale',
        'website_sale',
    ],

    # External Python dependencies
    'external_dependencies': {
        'python': ['onlinepayments-sdk-python3'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/payment_method_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_cawl_templates.xml',
    ],

    # Assets
    'assets': {
        'web.assets_frontend': [
            'payment_cawl/static/src/css/payment_cawl.css',
            'payment_cawl/static/src/js/payment_cawl.js',
        ],
    },

    'installable': True,
    'application': False,
    'auto_install': False,

    # Hooks
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
