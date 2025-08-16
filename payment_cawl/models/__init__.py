# -*- coding: utf-8 -*-

from . import cawl_payment_product
from . import payment_provider
from . import payment_transaction

from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(cr, registry):
    setup_provider(cr, registry, 'cawl')


def uninstall_hook(cr, registry):
    reset_payment_provider(cr, registry, 'cawl')