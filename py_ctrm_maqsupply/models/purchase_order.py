# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

READONLY_STATES = {
    'purchase': [('readonly', True)],
    'done': [('readonly', True)],
    'cancel': [('readonly', True)],
}


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    traking_bl = fields.Char(string="Traking/BL", states=READONLY_STATES)
    fecha_embarque = fields.Date(string="Fecha de embarque", states=READONLY_STATES)
    fecha_llegada = fields.Date(string="Fecha de llegada", states=READONLY_STATES)
    estado_aduana = fields.Date(string="Estado de aduana", states=READONLY_STATES)
    despacho_number = fields.Char(string="Despacho", states=READONLY_STATES)
