# -*- coding: utf-8 -*-

from odoo import fields, models


class CawlPaymentProduct(models.Model):
    _name = 'cawl.payment.product'
    _description = 'CAWL Payment Product'
    _order = 'name'

    name = fields.Char(
        string="Product Name",
        required=True,
        help="Display name of the payment product"
    )
    product_id = fields.Integer(
        string="Product ID",
        required=True,
        help="CAWL payment product ID"
    )
    payment_method = fields.Char(
        string="Payment Method",
        help="Payment method type (e.g., card, wallet, bank transfer)"
    )
    is_active = fields.Boolean(
        string="Active",
        default=True,
        help="Whether this product is available for use"
    )
    provider_id = fields.Many2one(
        'payment.provider',
        string="Provider",
        domain=[('code', '=', 'cawl')],
        help="CAWL provider this product belongs to"
    )
