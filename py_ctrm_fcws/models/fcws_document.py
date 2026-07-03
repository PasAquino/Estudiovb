from datetime import timedelta
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class FCWSDocument(models.Model):
    _name = "fcws.document"
    _description = "Documento Electrónico FCWS"
    _order = "create_date desc"

    move_id = fields.Many2one(
        "account.move", string="Factura", ondelete="cascade", required=True
    )
    payload = fields.Text(string="Payload Enviado")
    response = fields.Text(string="Respuesta Recibida")
    status = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("sent", "Enviado"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
            ("cancelled", "Cancelado"),
            ("canceling", "Cancelando"),
            ("disabled", "Inutilizado"),
            ("disabling", "Inutilizando"),
            ("error", "Error"),
        ],
        string="Estado",
        default="draft",
    )
    error_message = fields.Char(string="Mensaje de Error")
    timestamp = fields.Datetime(default=fields.Datetime.now, string="Fecha Registro")

    # Referencias rápidas
    cdc = fields.Char(string="CDC", related="move_id.fcws_cdc", readonly=True)
    partner_id = fields.Many2one(
        related="move_id.partner_id", store=True, string="Cliente"
    )
    company_id = fields.Many2one(
        related="move_id.company_id", store=True, string="Compañía"
    )

    @api.model
    def cron_clean_old_records(self):
        """Elimina registros FCWS antiguos (más de 60 días)."""
        days = 60
        limit = 1000  # borrar en lotes

        date_limit = fields.Datetime.now() - timedelta(days=days)

        domain = [("create_date", "<", date_limit)]

        total_deleted = 0

        while True:
            records = self.search(domain, limit=limit)
            if not records:
                break

            count = len(records)
            records.unlink()
            total_deleted += count

            _logger.info(
                "[FCWS CRON] Eliminados %s registros antiguos (>%s días)",
                count,
                days,
            )

        _logger.info(
            "[FCWS CRON] Limpieza finalizada. Total eliminados: %s",
            total_deleted,
        )

        return True
