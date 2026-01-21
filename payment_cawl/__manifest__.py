{
    "name": "CAWL Payment Provider",
    "summary": "Integrate CAWL payment services with Odoo",
    "version": "16.0.1.0.0",
    "development_status": "Beta",
    "category": "Accounting/Payment",
    "website": "https://github.com/OCA/bank-payment",
    "author": "Laurent Bélorgey, Odoo Community Association (OCA)",
    "maintainers": ["lbelorgey"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "preloadable":  True,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {
        "python": ["onlinepayments-sdk-python3"],
    },
    "depends": [
        "payment",
        "sale",
        "website_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/payment_provider_data.xml",
        "views/payment_provider_views.xml",
        "views/payment_cawl_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "payment_cawl/static/src/css/payment_cawl.css",
            "payment_cawl/static/src/js/payment_cawl.js",
        ],
    },
}
