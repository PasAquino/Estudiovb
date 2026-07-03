from odoo import api, fields, models


class FcwsCancelWizard(models.TransientModel):
    _name = "fcws.cancel.wizard"
    _description = "Asistente para Cancelar Factura Electrónica (EV-CANCEL)"

    move_id = fields.Many2one("account.move", string="Factura", required=True)
    cancel_reason = fields.Selection(
        [
            ("001", "Error en los datos del receptor"),
            ("002", "Documento duplicado"),
            ("003", "Error en los montos o impuestos"),
            ("004", "Operación no concretada / venta anulada"),
            ("005", "Error en la fecha de emisión"),
            ("006", "Error en el tipo de documento"),
            ("007", "Anulación por pruebas o testeo"),
            ("008", "Factura emitida con timbrado incorrecto"),
            ("009", "Error en la descripción de productos o servicios"),
            ("010", "Anulación por solicitud del cliente"),
        ],
        string="Motivo de Cancelación",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get("active_id")
        if active_id:
            res["move_id"] = active_id
        return res

    def action_confirm_cancel(self):
        """Confirma y ejecuta la cancelación."""
        self.ensure_one()
        move = self.move_id
        move.fcws_cancel_reason = self.cancel_reason
        move.action_fcws_cancel_event()
        return {"type": "ir.actions.act_window_close"}
