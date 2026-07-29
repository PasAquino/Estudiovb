# -*- coding: utf-8 -*-
from odoo import models, fields


class InvoicesPaymentParaguay(models.Model):
    """Extiende invoices.payment.paraguay para agregar campos de retención."""
    _inherit = 'invoices.payment.paraguay'

    nro_retencion = fields.Char(string='N° Retención')
    importe_retencion = fields.Monetary(string='Importe Retención', currency_field='currency_id')

