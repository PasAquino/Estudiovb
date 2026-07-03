import base64
import datetime
import io
import json
import logging
import re

import pytz
import qrcode
from num2words import num2words

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # --- Campos de control electrónico ---
    fcws_state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("sent", "Enviado"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
            ("canceling", "Cancelando"),
            ("cancelled", "Cancelado"),
            ("disabled", "Inutilizado"),
            ("error", "Error"),
        ],
        string="Estado FCWS",
        default="draft",
        tracking=True,
        copy=False,
    )

    fcws_cdc = fields.Char(string="CDC", readonly=True, copy=False)
    fcws_qr_code = fields.Char(string="QR", readonly=True, copy=False)
    fcws_message = fields.Char(string="Mensaje FCWS", readonly=True, copy=False)
    fcws_document_id = fields.Many2one(
        "fcws.document", string="Documento FCWS", ondelete="set null"
    )
    fcws_tipo_transaccion = fields.Selection(
        [
            ("1", "Venta de mercadería"),
            ("2", "Prestación de servicios"),
            ("3", "Mixto (venta de mercadería y servicios)"),
            ("4", "Venta de activo fijo"),
            ("5", "Venta de divisas"),
            ("6", "Compra de divisas"),
            ("7", "Promoción o entrega de muestras"),
            ("8", "Donación"),
            ("9", "Anticipo"),
            ("10", "Compra de productos"),
            ("11", "Compra de servicios"),
            ("12", "Venta de crédito fiscal"),
            ("13", "Muestras médicas (Art. 3 RG 24/2014)"),
        ],
        string="Tipo de Transacción (DNIT)",
        default="3",
        help="Define el tipo de transacción según la clasificación de la DNIT.",
        copy=False,
    )
    fcws_motivo_emision = fields.Selection(
        [
            ("1", "Devolución y Ajuste de precios"),
            ("2", "Devolución"),
            ("3", "Descuento"),
            ("4", "Bonificación"),
            ("5", "Crédito incobrable"),
            ("6", "Recupero de costo"),
            ("7", "Recupero de gasto"),
            ("8", "Ajuste de precio"),
        ],
        string="Motivo de Emisión",
        copy=False,
    )
    fcws_cancel_reason = fields.Selection(
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
        string="Motivo de Cancelación (DNIT)",
        tracking=True,
        copy=False,
    )
    fcws_qr_image = fields.Image(
        "QR Image",
        compute="_compute_qr_image",
        max_width=256,
        max_height=256,
    )
    fcws_tipo_cambio = fields.Float(
        string="Tipo de cambio FCWS", readonly=True, copy=False
    )
    fcws_manual_timbrado = fields.Char(
            string="Timbrado documento manual",
            copy=False,
        )
    fcws_manual_establecimiento = fields.Char(
        string="Establecimiento documento manual",
        copy=False,
    )
    fcws_manual_punto_expedicion = fields.Char(
        string="Punto de expedición documento manual",
        copy=False,
    )
    fcws_manual_numero = fields.Char(
        string="Número documento manual",
        copy=False,
    )
    fcws_manual_fecha_emision = fields.Date(
        string="Fecha emisión documento manual",
        copy=False,
    )
    fcws_manual_doc_asociado = fields.Boolean(
        string="Documento asociado manual",
        copy=False,
    )

    # --------------------------------------------------------------------------
    # Acciones principales
    # --------------------------------------------------------------------------

    def generar_texto(self, numero, moneda):
        if moneda == 2:
            new_number = round(numero, 2)
            nuevo_numero = str(new_number).split('.')
            entero = num2words(int(nuevo_numero[0]), lang='es').capitalize()
            if len(nuevo_numero[1]) == 1:
                if nuevo_numero[1] == '0':
                    decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
                else:
                    decimal = num2words(int(nuevo_numero[1] + '0'), lang='es').capitalize()
            else:
                decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
            letras = entero + ' con ' + decimal + ' Centavos'
        else:
            letras = num2words(numero, lang='es').capitalize()
        letras_return = letras
        return letras_return

    def action_send_fcws(self):
        """Envía la factura o nota de crédito al FCWS y guarda resultado."""
        client = self.env["fcws.client"]

        for move in self:
            if move.move_type not in ("out_invoice", "out_refund"):
                raise UserError(
                    _("Solo se pueden enviar facturas o notas de crédito electrónicas.")
                )

            payload = move._prepare_fcws_payload()
            try:
                if move.move_type == "out_invoice":
                    result = client.send_invoice(payload)
                else:
                    result = client.send_credit_note(payload)

                move._handle_fcws_response(result, payload)

            except ValidationError as e:
                move._log_fcws_error(payload, str(e))

        return True

    def _get_receptor_data(self):
        """Prepara el bloque 'receptor' del payload según el tipo de documento (usando edi_code)."""
        self.ensure_one()
        partner = self.partner_id
        vat_number = partner.vat or ""
        id_type = partner.l10n_latam_identification_type_id

        data = {}
        tipo_doc = str(id_type.edi_code or 1)

        # ----------------------------------------------------------------------
        # RUC – cuando es_vat=True
        # ----------------------------------------------------------------------
        if id_type.is_vat or "RUC" in (id_type.name or "").upper():
            if not vat_number:
                raise ValidationError(
                    _("El contacto '%s' no tiene número de RUC.") % partner.name
                )
            if "-" not in vat_number:
                raise ValidationError(
                    _("El RUC '%s' no contiene dígito verificador.") % vat_number
                )
            parts = vat_number.split("-")
            data.update(
                {
                    "docNro": parts[0].strip(),
                    "dv": parts[1].strip(),
                    "razonSocial": partner.name.strip(),
                }
            )

        # ----------------------------------------------------------------------
        # Documento estándar según edi_code (CI, Pasaporte, Extranjero, etc.)
        # ----------------------------------------------------------------------
        else:
            data.update(
                {
                    "tipoDocumento": tipo_doc,
                    "docNro": re.sub(r"[^0-9A-Za-z]", "", vat_number or "") or "0",
                    "razonSocial": partner.name.strip() or "SIN NOMBRE",
                }
            )

            # Caso especial para exterior
            if tipo_doc == "9":
                data["tipoDocumentoOtro"] = "Identificación fiscal extranjera"

            # Sin nombre
            if tipo_doc == "5":
                data["docNro"] = 0

        # # ----------------------------------------------------------------------
        # # Dirección limpia (sin acentos ni saltos)
        #  NO IMPLEMENTADO EN LA API
        # # ----------------------------------------------------------------------
        # direccion = " ".join(
        #     (partner.contact_address or "")
        #     .replace("\n", " ")
        #     .replace("\r", " ")
        #     .translate(str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN"))
        #     .split()
        # )
        # if direccion:
        #     data["direccion"] = direccion

        # ----------------------------------------------------------------------
        # Ciudad y País (solo si válidos)
        # ----------------------------------------------------------------------
        if partner.city_id and getattr(partner.city_id, "edi_code", None):
            data["ciudad"] = int(partner.city_id.edi_code)
        elif partner.city and partner.city.isdigit():
            data["ciudad"] = int(partner.city)

        if partner.country_id and partner.country_id.code:
            data["pais"] = partner.country_id.code

        return data

    def action_consult_fcws(self):
        client = self.env["fcws.client"]
        for move in self.filtered(lambda m: m.fcws_cdc):
            try:
                result = client.consult_document(move.fcws_cdc)
                move._handle_fcws_response(result)
                # Auto-sincronizar estado cancelado
                if isinstance(result, dict) and result.get("estado") == "Cancelado":
                    move.fcws_state = "cancelled"
            except ValidationError as e:
                move._log_fcws_error(None, str(e))

    def action_fcws_cancel_event(self):
        """Genera y envía el evento de cancelación (EV-CANCEL) al FCWS."""
        client = self.env["fcws.client"]

        for move in self.filtered(lambda m: m.fcws_state in ("approved", "rejected")):
            if not move.fcws_cdc:
                raise ValidationError(
                    _("No existe CDC para generar evento de cancelación.")
                )

            motivo = move._get_cancel_reason()
            if not motivo:
                raise ValidationError(
                    _("Debe especificar un motivo de cancelación válido.")
                )

            payload = {
                "contribuyente": client._get_taxpayer_data(),
                "fecha": fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                "cdc": move.fcws_cdc,
                "motivo": motivo,
            }

            try:
                if move.move_type == "out_invoice":
                    result = client.cancel_invoice(payload)
                elif move.move_type == "out_refund":
                    result = client.cancel_credit_note(payload)
                else:
                    raise UserError(
                        _("Tipo de documento no soportado para cancelación FCWS.")
                    )

                move._handle_fcws_response(result, payload)
            except ValidationError as e:
                move._log_fcws_error(payload, str(e))

    def _get_cancel_reason(self):
        """Devuelve el motivo elegido o uno genérico."""
        self.ensure_one()
        if not self.fcws_cancel_reason:
            return "Cancelacion"
        reason_text = dict(self._fields["fcws_cancel_reason"].selection).get(
            self.fcws_cancel_reason
        )
        return f"{self.fcws_cancel_reason} - {reason_text}"

    def _get_document_date(self):
        asu_timezone = pytz.timezone("America/Asuncion")
        invoice_date = self.invoice_date
        now_asu = datetime.datetime.now(asu_timezone)
        today_asu = now_asu.date()

        if invoice_date == today_asu:
            dt_to_send = now_asu
        else:
            dt_to_send = asu_timezone.localize(
                datetime.datetime.combine(invoice_date, datetime.time(12, 0, 0))
            )
        return dt_to_send.strftime("%Y-%m-%dT%H:%M:%S%z")

    # --------------------------------------------------------------------------
    # Construcción de Payload
    # --------------------------------------------------------------------------

    def _prepare_fcws_payload(self):
        """Genera el JSON compatible con la API FCWS."""
        self.ensure_one()
        if not self.journal_id.fcws_enabled:
            raise ValidationError(
                _(
                    "El diario '%s' no está habilitado para Facturación Electrónica (FCWS). "
                    "Active la opción en la configuración del diario."
                )
                % self.journal_id.display_name
            )

        client = self.env["fcws.client"]
        company = self.company_id
        partner = self.partner_id

        # --------------------------------------------------------------------------
        # CONTRIBUYENTE
        # --------------------------------------------------------------------------
        taxpayer = client._get_taxpayer_data()
        if not taxpayer.get("contribuyenteid") or not taxpayer.get("pass"):
            raise ValidationError("Faltan credenciales FCWS en la configuración.")

        # --------------------------------------------------------------------------
        # TIMBRADO
        # --------------------------------------------------------------------------
        if not company.fcws_docstamp_number:
            raise ValidationError(
                _("Falta configurar el número de timbrado en la compañía.")
            )

        if not company.fcws_timbrado_fec_ini:
            raise ValidationError(
                _("Falta la fecha de inicio del timbrado en la compañía.")
            )
        timbrado = company.fcws_docstamp_number if company.fcws_is_production else company.fcws_docstamp_number_test
        if not timbrado:
            raise ValidationError("Falta configurar el timbrado FCWS en la compania.")

        establecimiento, punto_expedicion, nro = (self.name or "0-0-0").split("-")

        fec_ini = (
            company.fcws_timbrado_fec_ini.strftime("%Y-%m-%dT03:00:00-03:00")
            if company.fcws_timbrado_fec_ini
            else None
        )
        if not fec_ini:
            raise ValidationError("Falta la fecha de inicio del timbrado.")

        timbrado_data = {
            "timbrado": timbrado,
            "establecimiento": establecimiento.zfill(3),
            "puntoExpedicion": punto_expedicion.zfill(3),
            "documentoNro": nro,
            "fecIni": fec_ini,
        }

        # --------------------------------------------------------------------------
        # SUCURSAL
        # --------------------------------------------------------------------------
        sucursal = company.fcws_branch_name or "Casa Central"

        # --------------------------------------------------------------------------
        # RECEPTOR (Usando helper centralizado)
        # --------------------------------------------------------------------------

        receptor = self._get_receptor_data()

        # --------------------------------------------------------------------------
        # CONDICIÓN DE OPERACIÓN
        # --------------------------------------------------------------------------
        if not self.invoice_payment_term_id:
            condicion = 1  # contado
        else:
            condicion = 2  # crédito

        condicion_operacion = {"condicion": condicion}
        if condicion == 1:
            condicion_operacion["tiposPagos"] = [
                {"tipoPagoCodigo": 1, "monto": float(self.amount_total)}
            ]
        else:
            condicion_operacion["operacionTipo"] = (
                3
                if self.partner_id.property_account_position_id
                and self.partner_id.property_account_position_id.is_government
                else 1
            )
            condicion_operacion["plazoCredito"] = self.payment_term_days()

        # --------------------------------------------------------------------------
        # DETALLES
        # --------------------------------------------------------------------------
        items = []
        for line in self.invoice_line_ids:
            if line.quantity <= 0:
                continue

            iva = line.tax_ids[:1].amount if line.tax_ids else 0
            descuento = (
                abs((line.quantity * line.price_unit) - line.price_total)
                / line.quantity
            )

            items.append(
                {
                    "itemCodigo": line.product_id.default_code or "001",
                    "itemDescripcion": line.name or "",
                    "cantidad": line.quantity,
                    "precioUnitario": round(line.price_unit, 2),
                    "descuento": descuento,
                    "afectacionTributaria": 1 if iva > 0 else 3,  # 1=Gravado, 3=Exento
                    "proporcionIVA": 100 if iva > 0 else 0,
                    "tasaIVA": int(iva),
                }
            )

        if not items:
            raise ValidationError("No hay líneas válidas para enviar al FCWS.")

        tipo_transaccion = None
        if self.move_type in ("out_invoice", "out_refund"):
            tipo_transaccion = int(self.fcws_tipo_transaccion or 3)

        # --------------------------------------------------------------------------
        # ENSAMBLE FINAL
        # --------------------------------------------------------------------------
        tipo_cambio = self.currency_id._get_conversion_rate(
            self.currency_id,  # Desde la moneda del documento (USD)
            self.company_currency_id,  # Hacia la moneda de la compañía (PYG)
            self.company_id,
            self.invoice_date or fields.Date.today(),
        )
        self.fcws_tipo_cambio = tipo_cambio

        payload = {
            "contribuyente": taxpayer,
            "timbrado": timbrado_data,
            "sucursal": sucursal,
            "receptor": receptor,
            "fecha": self._get_document_date(),
            "operacionMoneda": self.currency_id.name,
            "operacionMonedaCambio": tipo_cambio,
            "tipoTransaccion": tipo_transaccion,
            "condicionOperacion": condicion_operacion,
            "detalles": items,
            "totalComprobante": abs(self.currency_id.round(self.amount_total_signed)),
        }

        # --------------------------------------------------------------------------
        # NOTA DE CRÉDITO
        # --------------------------------------------------------------------------
        if self.move_type == "out_refund":
            payload["notaCreditoDebito"] = {
                "motivoEmision": int(self.fcws_motivo_emision or "1")
            }

            if self.fcws_manual_doc_asociado:
                missing = []
                if not self.fcws_manual_timbrado:
                    missing.append(_("Timbrado"))
                if not self.fcws_manual_establecimiento:
                    missing.append(_("Establecimiento"))
                if not self.fcws_manual_punto_expedicion:
                    missing.append(_("Punto de expedición"))
                if not self.fcws_manual_numero:
                    missing.append(_("Número del documento"))
                if not self.fcws_manual_fecha_emision:
                    missing.append(_("Fecha de emisión"))

                if missing:
                    raise ValidationError(
                        _("Faltan datos del documento manual asociado:\n- %s")
                        % "\n- ".join(missing)
                    )

                payload["docAsociados"] = [{
                    "tipo": 2,
                    "timbrado": self.fcws_manual_timbrado,
                    "establecimiento": str(self.fcws_manual_establecimiento).zfill(3),
                    "puntoExpedicion": str(self.fcws_manual_punto_expedicion).zfill(3),
                    "docNro": str(self.fcws_manual_numero).zfill(7),
                    "tipoDocAsociado": "1",
                    "fechaEmision": self._get_fcws_manual_fecha_emision(),
                }]

            elif self.reversed_entry_id and (self.reversed_entry_id.fcws_cdc or self.reversed_entry_id.cdc):
                payload["docAsociados"] = [{
                    "tipo": 1,
                    "cdc": self.reversed_entry_id.fcws_cdc or self.reversed_entry_id.cdc,
                    "tipoDocAsociado": "1",
                }]

            else:
                raise ValidationError(
                    _("La nota de crédito debe tener un documento asociado electrónico o manual.")
                )

        return payload

    def _get_fcws_manual_fecha_emision(self):
        self.ensure_one()
        if not self.fcws_manual_fecha_emision:
            raise ValidationError(_("Falta la fecha de emisión del documento manual."))

        tz = pytz.timezone("America/Asuncion")
        dt = tz.localize(
            datetime.datetime.combine(
                self.fcws_manual_fecha_emision,
                datetime.time(0, 0, 0),
            )
        )
        formatted = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        return f"{formatted[:-2]}:{formatted[-2:]}"

    # --------------------------------------------------------------------------
    # Procesamiento de Respuesta
    # --------------------------------------------------------------------------

    def _handle_fcws_response(self, result, payload=None):
        """Procesa respuesta del FCWS, manejando texto plano y JSON con eventos."""
        self.ensure_one()

        # 🔹 1. Texto plano (cancelación o inutilización)
        _logger.debug("[FCWS] Respuesta texto plano: %s", result)
        if isinstance(result, str):
            text = result.strip()
            _logger.debug("[FCWS] Respuesta texto plano: %s", text)

            if text in (
                "Cancelacion de factura enviada",
                "Cancelacion de Nota de Credito recibida",
            ):
                self.fcws_state = "canceling"
                self.fcws_message = text
                status_label = "canceling"
            elif "Inutilizacion" in text:
                self.fcws_state = "pending"
                self.fcws_message = text
                status_label = "disabling"
            else:
                self.fcws_state = "error"
                self.fcws_message = text
                status_label = "error"

            self.fcws_document_id = (
                self.env["fcws.document"]
                .create(
                    {
                        "move_id": self.id,
                        "payload": json.dumps(
                            payload or {}, ensure_ascii=False, indent=2
                        ),
                        "response": json.dumps(
                            {"respuesta": text}, ensure_ascii=False, indent=2
                        ),
                        "status": status_label,
                    }
                )
                .id
            )

            _logger.debug(
                "[FCWS] %s actualizado → Estado: %s | Mensaje: %s",
                self.name,
                self.fcws_state,
                self.fcws_message,
            )
            return

        # 🔹 2. Convertir a dict si viene en texto JSON
        if not isinstance(result, dict):
            try:
                result = json.loads(result)
            except Exception:
                result = {"respuesta": str(result)}

        # 🔹 3. Crear registro histórico del intercambio
        self.fcws_document_id = (
            self.env["fcws.document"]
            .create(
                {
                    "move_id": self.id,
                    "payload": json.dumps(payload or {}, ensure_ascii=False, indent=2),
                    "response": json.dumps(result or {}, ensure_ascii=False, indent=2),
                }
            )
            .id
        )

        # 🔹 3.b Caso: emisión exitosa sin campo 'estado'
        if result.get("cdc") and result.get("qr") and not result.get("estado"):
            self.fcws_cdc = result["cdc"]
            self.fcws_qr_code = result["qr"]
            self.fcws_state = "sent"
            self.fcws_message = "Documento electrónico enviado correctamente al FCWS."

            self.fcws_document_id = (
                self.env["fcws.document"]
                .create(
                    {
                        "move_id": self.id,
                        "payload": json.dumps(
                            payload or {}, ensure_ascii=False, indent=2
                        ),
                        "response": json.dumps(
                            result or {}, ensure_ascii=False, indent=2
                        ),
                        "status": "sent",
                    }
                )
                .id
            )

            _logger.debug(
                "[FCWS] %s enviada al FCWS (CDC: %s)", self.name, self.fcws_cdc
            )
            return
        estado = result.get("estado", "")
        respuesta = result.get("respuesta", "") or result.get("tipo", "")

        # 🔹 4. Procesar evento (cancelación, inutilización, etc.)
        evento = result.get("evento")
        if self.fcws_state == "canceling" and not evento:
            _logger.debug(
                "[FCWS] %s mantiene estado 'canceling' (aún sin evento confirmado por DNIT)",
                self.name,
            )
            return
        if evento and isinstance(evento, dict):
            evento_estado = evento.get("estado")
            evento_motivo = (evento.get("motivo") or "").lower()

            # ✅ Caso: evento de cancelación aprobado por DNIT
            if evento_estado == "Aprobado":
                self.fcws_state = "cancelled"
                respuesta = "Cancelación aprobada por DNIT"
                status_label = "cancelled"

                # 🔸 Anular la factura contable (si aún no lo está)
                if self.state not in ("cancel", "draft"):
                    try:
                        _logger.debug(
                            "[FCWS] Anulando factura %s por cancelación aprobada en DNIT",
                            self.name,
                        )
                        self.button_cancel()  # método estándar de Odoo
                        self.message_post(
                            body=_(
                                "Factura anulada automáticamente tras aprobación del evento de cancelación por la DNIT."
                            )
                        )
                    except Exception as e:
                        _logger.error(
                            "[FCWS] Error al cancelar factura %s: %s", self.name, e
                        )

            # ✅ Caso: inutilización aprobada
            elif "inutilizacion" in evento_motivo and evento_estado == "Aprobado":
                self.fcws_state = "disabled"
                respuesta = "Inutilización aprobada por DNIT"
                status_label = "disabled"

            # ⚠️ Caso: evento rechazado
            elif evento_estado == "Rechazado":
                self.fcws_state = "error"
                respuesta = f"Evento rechazado: {evento.get('respuesta', '')}"
                status_label = "error"

            # ⏳ Caso: evento en trámite o desconocido
            else:
                self.fcws_state = "pending"
                respuesta = f"Evento en proceso: {evento_estado or 'Desconocido'}"
                status_label = "pending"

            # Registrar el documento con el resultado del evento
            self.fcws_document_id = (
                self.env["fcws.document"]
                .create(
                    {
                        "move_id": self.id,
                        "payload": json.dumps(
                            payload or {}, ensure_ascii=False, indent=2
                        ),
                        "response": json.dumps(
                            result or {}, ensure_ascii=False, indent=2
                        ),
                        "status": status_label,
                    }
                )
                .id
            )

        else:
            # 🔹 5. Si no hay evento, procesar respuesta estándar
            self.fcws_state = self._map_fcws_state(estado)
            status_label = self.fcws_state

        # 🔹 6. Campos finales comunes
        self.fcws_message = respuesta[:250]
        self.fcws_cdc = result.get("cdc") or self.fcws_cdc
        self.fcws_qr_code = (
            result.get("enlaceQR") or result.get("qr") or self.fcws_qr_code
        )
        # ----------------------------------------------------------
        # 📧 Enviar correo al cliente cuando el documento está aprobado
        # ----------------------------------------------------------
        if self.fcws_state == "approved":
            try:
                template = self.env.ref(
                    "py_ctrm_fcws.email_template_electronic_invoice",
                    raise_if_not_found=False,
                )
                if template:
                    # Buscar si hay XML firmado para adjuntar
                    attachment_ids = []
                    xml_attachment = self.env["ir.attachment"].search(
                        [
                            ("res_model", "=", "account.move"),
                            ("res_id", "=", self.id),
                            ("name", "ilike", ".xml"),
                        ],
                        limit=1,
                    )
                    if xml_attachment:
                        attachment_ids.append(xml_attachment.id)

                    # Enviar el correo con el PDF personalizado y XML (si existe)
                    template.send_mail(
                        self.id,
                        force_send=True,
                        email_values={"attachment_ids": attachment_ids},
                    )
                    _logger.debug(
                        "[FCWS] Correo de factura electrónica enviado al cliente (%s)",
                        self.partner_id.email,
                    )
                else:
                    _logger.warning(
                        "[FCWS] No se encontró la plantilla de correo electrónico para envío automático."
                    )
            except Exception as e:
                _logger.error(
                    "[FCWS] Error al enviar correo electrónico de factura aprobada: %s",
                    e,
                )

        _logger.debug(
            "[FCWS] %s actualizado → Estado: %s | Mensaje: %s",
            self.name,
            self.fcws_state,
            self.fcws_message,
        )

    def _log_fcws_error(self, payload, message):
        """Guarda errores de integración."""
        self.fcws_state = "error"
        self.fcws_message = message
        self.env["fcws.document"].create(
            {
                "move_id": self.id,
                "payload": json.dumps(payload or {}, ensure_ascii=False, indent=2),
                "response": json.dumps(
                    {"error": message}, ensure_ascii=False, indent=2
                ),
                "status": "error",
            }
        )
        _logger.error("[FCWS] Error en factura %s: %s", self.name, message)

    def _map_fcws_state(self, estado):
        mapping = {
            "Listo": "pending",
            "Pendiente": "pending",
            "Enviado": "sent",
            "Aprobado": "approved",
            "Rechazado": "rejected",
            "Cancelando": "canceling",
            "Cancelado": "cancelled",
            "Inutilizado": "disabled",
            "Error": "error",
        }
        return mapping.get(estado, "error")

    def payment_term_days(self):
        self.ensure_one()
        if self.invoice_payment_term_id:
            return self.invoice_payment_term_id.name
        if self.invoice_date and self.invoice_date_due:
            days = (self.invoice_date_due - self.invoice_date).days
            return "1 día" if days == 1 else f"{days} días"
        return "30 días"

    def button_draft(self):
        """Evita volver a borrador si la factura fue enviada o aprobada en FCWS (excepto procesos automáticos)."""
        for move in self:
            # Permitir si lo ejecuta Odoobot (por cron o sistema)
            if self.env.user.login == "__system__":
                _logger.debug("[FCWS] Odoobot ejecuta button_draft(), omitiendo validación de restricción.")
                return super().button_draft()

            # Solo aplica a facturas electrónicas (con CDC o diario habilitado)
            if move.journal_id.fcws_enabled or move.fcws_cdc:
                # Si no está en error, bloquear
                if move.fcws_state not in ("draft", "error", "cancelled", "rejected"):
                    raise ValidationError(
                        _(
                            "No puede restablecer a borrador una factura electrónica "
                            "que ya fue enviada al FCWS o aprobada por la DNIT.\n\n"
                            "Solo las facturas con error pueden volver a borrador para corrección."
                        )
                    )

        return super().button_draft()

    def cdc_format(self, cdc):
        for record in self:
            resultado_formateado = " ".join(
                [cdc[i : i + 4] for i in range(0, len(cdc), 4)]
            )
            return resultado_formateado

    @api.depends("fcws_qr_code")
    def _compute_qr_image(self):
        for rec in self:
            qr = qrcode.make(rec.fcws_qr_code or rec.name)
            buffer = io.BytesIO()
            qr.save(buffer, format="PNG")
            rec.fcws_qr_image = base64.b64encode(buffer.getvalue())

        # --------------------------------------------------------------------------

    # Publicación automática en FCWS
    # --------------------------------------------------------------------------

    def action_post(self):
        """Publica la factura y, si el diario es electrónico, la envía automáticamente al FCWS."""
        res = super().action_post()

        for move in self:
            # Cargar tipdocing para ventas
            if move.move_type == "out_invoice" and not move.tipdocing:
                tipdoc = self.env["account.tip.doc"].search([
                    ("tipdoc", "=", "sale"),
                    ("internal_type", "=", "invoice"),
                ], limit=1)
                if tipdoc:
                    move.tipdocing = tipdoc.id

            elif move.move_type == "out_refund" and not move.tipdocing:
                tipdoc = self.env["account.tip.doc"].search([
                    ("tipdoc", "=", "sale"),
                    ("internal_type", "=", "credit_note"),
                ], limit=1)
                if tipdoc:
                    move.tipdocing = tipdoc.id

        for move in self.filtered(lambda m: m.journal_id.fcws_enabled):
            try:
                _logger.debug(
                    "[FCWS] Diario electrónico detectado: %s → enviando documento %s al FCWS",
                    move.journal_id.name,
                    move.name,
                )
                move.action_send_fcws()
            except Exception as e:
                move._log_fcws_error(
                    {}, f"Error al enviar automáticamente al FCWS: {e}"
                )
                _logger.error(
                    "[FCWS] Error automático al enviar factura %s: %s", move.name, e
                )

        return res

    # --------------------------------------------------------------------------
    # Sincronización automática con FCWS (para cron)
    # --------------------------------------------------------------------------

    @api.model
    def cron_sync_fcws_documents(self):
        """Sincroniza automáticamente los comprobantes electrónicos no finalizados con el FCWS."""
        _logger.debug(
            "[FCWS CRON] Iniciando sincronización de comprobantes pendientes..."
        )

        domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            (
                "fcws_state",
                "not in",
                ["approved", "rejected", "cancelled", "error", "disabled"],
            ),
            ("journal_id.fcws_enabled", "=", True),
            ("fcws_cdc", "!=", False),
        ]

        moves = self.search(
            domain, limit=200
        )  # Evita sobrecargar la API en lotes grandes

        _logger.debug("[FCWS CRON] %s comprobantes pendientes encontrados.", len(moves))

        for move in moves:
            try:
                move.action_consult_fcws()
                _logger.debug(
                    "[FCWS CRON] Consultado %s (%s)", move.name, move.fcws_state
                )
            except Exception as e:
                _logger.error("[FCWS CRON] Error al consultar %s: %s", move.name, e)

        _logger.debug("[FCWS CRON] Sincronización finalizada.")
        return True
