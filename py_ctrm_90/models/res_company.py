# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import time
import calendar
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz


class ResCompany90(models.Model):
    _inherit = "res.company"
    _description = "Campos para resolucion 90"

    imputa_iva = fields.Boolean(
        string="Imputa al IVA?"
    )
    imputa_ire = fields.Boolean(
        string="Imputa al IRE?"
    )
    imputa_irp = fields.Boolean(
        string="Imputa al IRP-RSP?"
    )
