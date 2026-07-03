from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountJournalInherit(models.Model):
    _inherit = "account.journal"

    cheques_diferidos = fields.Boolean(string="Cheques Diferidos")
    cheques_al_dia = fields.Boolean(string="Cheques al día")
    diario_de_cheques = fields.Boolean(string="Diario Cheque")
    cheques_tipo_cobro = fields.Boolean(string="Cheque Tipo Cobro")
    cheques_tipo_pago = fields.Boolean(string="Cheques Tipo Pago")
