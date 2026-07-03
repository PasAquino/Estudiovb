# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime

import pytz
import re
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FcwsInutilization(models.Model):
    _name = "fcws.inutilization"
    _description = "FCWS - Inutilización de Numeración"
    _order = "id desc"

    # -----------------------
    # Datos base
    # -----------------------
    _rec_name = "name"

    name = fields.Char(
        string="Referencia",
        compute="_compute_name",
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    type = fields.Selection(
        [
            ("invoice", "Factura"),
            ("remision", "Remisión"),
            ("credit_note", "Nota de Crédito"),
        ],
        required=True,
        default="invoice",
        index=True,
    )

    fecha = fields.Datetime(
        string="Fecha del evento",
        required=True,
        default=lambda self: fields.Datetime.now(),
    )
    motivo = fields.Char(string="Motivo", required=True)

    timbrado_id = fields.Many2one(
        "account.journal.stamped",
        string="Timbrado",
        compute="_compute_timbrado_id",
        store=True,
        readonly=True,
    index=True,
    )
    timbrado = fields.Char(
        string="Timbrado (nro)",
        compute="_compute_timbrado",
        store=True,
        readonly=True,
        index=True,
    )
    establecimiento = fields.Char(
        string="Establecimiento", required=True, size=3, index=True
    )
    punto_expedicion = fields.Char(
        string="Punto Expedición", required=True, size=3, index=True
    )
    numero_ini = fields.Char(string="Número inicial", required=True, size=7, index=True)
    numero_fin = fields.Char(string="Número final", required=True, size=7, index=True)

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("sent", "Enviado"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
            ("error", "Error"),
        ],
        default="draft",
        tracking=True,
        copy=False,
    )

    message = fields.Char(string="Mensaje", readonly=True, copy=False)
    fcws_document_id = fields.Many2one(
        "fcws.document",
        string="Documento FCWS",
        ondelete="set null",
        readonly=True,
        copy=False,
    )

    payload_json = fields.Text(string="Payload", readonly=True, copy=False)
    response_json = fields.Text(string="Respuesta", readonly=True, copy=False)

    @api.depends("type", "timbrado_id", "establecimiento", "punto_expedicion", "numero_ini", "numero_fin")
    def _compute_name(self):
        type_map = {
            "invoice": "FACT",
            "remision": "REM",
            "credit_note": "NC",
        }
        for r in self:
            t = type_map.get(r.type, "INU")
            timb = r.timbrado or "SIN-TIMB"
            est = (r.establecimiento or "").zfill(3)
            pex = (r.punto_expedicion or "").zfill(3)
            ini = (r.numero_ini or "").zfill(7)
            fin = (r.numero_fin or "").zfill(7)
            r.name = f"INU/{t}/{timb}/{est}-{pex}/{ini}-{fin}"
    
    # -----------------------
    # Normalización / Validación
    # -----------------------
    def _pad(self):
        for r in self:
            r.establecimiento = (r.establecimiento or "").zfill(3)
            r.punto_expedicion = (r.punto_expedicion or "").zfill(3)
            r.numero_ini = (r.numero_ini or "").zfill(7)
            r.numero_fin = (r.numero_fin or "").zfill(7)

    @api.constrains(
        "type",
        "company_id",
        "timbrado_id",
        "establecimiento",
        "punto_expedicion",
        "numero_ini",
        "numero_fin",
    )
    def _check_numbers_not_exist(self):
        self._validate_range()
        self._validate_numbers_not_exist()

    def _to_int(self, s, label):
        try:
            return int(s)
        except Exception:
            raise ValidationError(_("Valor inválido para %s: %s") % (label, s))

    def _validate_range(self):
        for r in self:
            ini = r._to_int(r.numero_ini, "Número inicial")
            fin = r._to_int(r.numero_fin, "Número final")

            if fin < ini:
                raise ValidationError(
                    _("El número final debe ser mayor o igual al inicial.")
                )

            # DNIT: fin - ini <= 1000
            if (fin - ini) > 1000:
                raise ValidationError(
                    _("El rango no puede exceder 1000 números (fin - inicio <= 1000).")
                )

    def _validate_overlap(self):
        """Evita solapes con rangos ya enviados/aprobados para mismo timbrado/serie/tipo."""
        for r in self:
            timbrado = r._resolve_timbrado() 
            ini = r._to_int(r.numero_ini, "Número inicial")
            fin = r._to_int(r.numero_fin, "Número final")

            others = self.search(
                [
                    ("id", "!=", r.id),
                    ("company_id", "=", r.company_id.id),
                    ("type", "=", r.type),
                    ("timbrado_id", "=", r.timbrado_id.id),
                    ("establecimiento", "=", r.establecimiento),
                    ("punto_expedicion", "=", r.punto_expedicion),
                    ("state", "in", ["sent", "approved"]),
                ],
                limit=2000,
            )
            for o in others:
                oi = r._to_int(o.numero_ini, "Número inicial (otra)")
                of = r._to_int(o.numero_fin, "Número final (otra)")
                if not (fin < oi or ini > of):
                    raise ValidationError(
                        _("El rango %s..%s se solapa con %s..%s (registro %s).")
                        % (
                            r.numero_ini,
                            r.numero_fin,
                            o.numero_ini,
                            o.numero_fin,
                            o.display_name,
                        )
                    )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_vals(dict(v)) for v in vals_list]
        recs = super().create(vals_list)
        recs._validate_range()
        recs._validate_overlap()
        recs._validate_numbers_not_exist()
        return recs


    def write(self, vals):
        vals = self._normalize_vals(dict(vals))
        res = super().write(vals)
        self._validate_range()
        self._validate_overlap()
        self._validate_numbers_not_exist()
        return res

    # -----------------------
    # Payload FCWS (Swagger)
    # -----------------------
    def _get_event_date(self):
        """Swagger muestra -04:00; en Paraguay suele ser -03:00/-04:00 según DST.
        Usamos America/Asuncion y formateamos con offset real.
        """
        self.ensure_one()
        tz = pytz.timezone("America/Asuncion")
        dt = fields.Datetime.to_datetime(self.fecha)
        if not dt:
            dt = fields.Datetime.now()
        dt_local = (
            pytz.UTC.localize(dt).astimezone(tz)
            if dt.tzinfo is None
            else dt.astimezone(tz)
        )
        # ISO con offset
        return (
            dt_local.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2]
            + ":"
            + dt_local.strftime("%Y-%m-%dT%H:%M:%S%z")[-2:]
        )

    def _endpoint(self):
        self.ensure_one()
        if self.type == "invoice":
            return "evento/inutilizacionnumfactura"
        if self.type == "remision":
            return "evento/inutilizacionnumremision"
        return "evento/inutilizacionnumnotacredito"

    def _get_company_timbrado(self):
        self.ensure_one()
        return self._resolve_timbrado()

    def _prepare_payload(self):
        self.ensure_one()
        client = self.env["fcws.client"]

        payload = {
            "contribuyente": client._get_taxpayer_data(),  # igual que en tu ejemplo
            "fecha": self._get_event_date(),
            "timbrado": self._get_company_timbrado(),
            "establecimiento": self.establecimiento,
            "puntoExpedicion": self.punto_expedicion,
            "numeroIni": self.numero_ini,
            "numeroFin": self.numero_fin,
            "motivo": self.motivo,
        }
        return payload

    # -----------------------
    # Acción principal
    # -----------------------
    def action_send(self):
        client = self.env["fcws.client"]

        for rec in self:

            if rec.state not in ("draft", "rejected", "error"):
                continue

            rec._validate_range()
            rec._validate_overlap()
            rec._validate_numbers_not_exist()
            payload = rec._prepare_payload()
            rec.payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

            _logger.debug(
                "[FCWS-INU] Enviando inutilización %s -> %s", rec.id, rec._endpoint()
            )

            try:
                # Si tu client ya tiene métodos específicos, mejor:
                # result = client.disable_invoice(payload) / disable_credit_note / disable_remision
                result = client._request(rec._endpoint(), method="POST", data=payload)
            except ValidationError as e:
                rec._set_error(payload, str(e))
                continue
            except Exception as e:
                rec._set_error(payload, str(e))
                continue

            rec._handle_response(payload, result)

        return True

    def _set_error(self, payload, message):
        self.ensure_one()
        self.state = "error"
        self.message = message[:250]
        self.response_json = json.dumps(
            {"error": message}, ensure_ascii=False, indent=2
        )
        self._create_fcws_document(payload, {"error": message}, status="error")
        _logger.error("[FCWS-INU] Error %s: %s", self.id, message)

    def _handle_response(self, payload, result):
        self.ensure_one()

        # Swagger indica 201 “... recibida” y 403 credenciales
        # Tu integrador a veces responde texto plano.
        status = "sent"
        msg = ""

        if isinstance(result, str):
            msg = result.strip()
            if "recibida" in msg.lower() or "enviada" in msg.lower():
                self.state = "sent"
            else:
                self.state = "error"
                status = "error"
            self.message = msg[:250]
            self.response_json = json.dumps(
                {"respuesta": msg}, ensure_ascii=False, indent=2
            )
            self._create_fcws_document(payload, {"respuesta": msg}, status=status)
            return

        if not isinstance(result, dict):
            try:
                result = json.loads(result)
            except Exception:
                result = {"respuesta": str(result)}

        self.response_json = json.dumps(result, ensure_ascii=False, indent=2)

        # Heurística: si trae "evento" y "Aprobado" => approved
        evento = result.get("evento")
        if isinstance(evento, dict):
            ev_estado = evento.get("estado")
            if ev_estado == "Aprobado":
                self.state = "approved"
                self.message = "Inutilización aprobada por DNIT"[:250]
                self._create_fcws_document(payload, result, status="approved")
                return
            if ev_estado == "Rechazado":
                self.state = "rejected"
                self.message = (
                    "Inutilización rechazada: %s" % (evento.get("respuesta") or "")
                )[:250]
                self._create_fcws_document(payload, result, status="rejected")
                return

        # Si solo confirma “recibida”
        resp_txt = (result.get("respuesta") or result.get("tipo") or "") or ""
        if "recibida" in resp_txt.lower():
            self.state = "sent"
            self.message = resp_txt[:250]
            self._create_fcws_document(payload, result, status="sent")
        else:
            # si no sabemos, lo dejamos en sent para que luego se consulte por el integrador
            self.state = "sent"
            self.message = (resp_txt or "Inutilización enviada al FCWS.")[:250]
            self._create_fcws_document(payload, result, status="sent")

    def _create_fcws_document(self, payload, response, status="sent"):
        """Reutiliza el modelo de auditoría que ya tenés."""
        self.ensure_one()
        try:
            doc = self.env["fcws.document"].create(
                {
                    "payload": json.dumps(payload or {}, ensure_ascii=False, indent=2),
                    "response": json.dumps(
                        response or {}, ensure_ascii=False, indent=2
                    ),
                    "status": status,
                    # si tu fcws.document tiene campos extra, los completás acá
                }
            )
            self.fcws_document_id = doc.id
        except Exception as e:
            _logger.warning("[FCWS-INU] No se pudo crear fcws.document: %s", e)

    @api.depends(
        "company_id",
        "company_id.fcws_is_production",
        "company_id.fcws_docstamp_number",
        "company_id.fcws_docstamp_number_test",
    )
    def _compute_timbrado(self):
        for r in self:
            if not r.company_id:
                r.timbrado = False
                continue
            try:
                r.timbrado = r._resolve_timbrado()  # string
            except Exception:
                r.timbrado = False


    @api.depends("timbrado", "company_id")
    def _compute_timbrado_id(self):
        """
        Mapea el número de timbrado (string) al registro account.journal.stamped
        para poder validar contra account.move.timbrado_id.
        Ajustá el campo del stamped si no es 'name'.
        """
        Stamped = self.env["account.journal.stamped"]
        for r in self:
            r.timbrado_id = False
            if not r.company_id or not r.timbrado:
                continue
            stamped = Stamped.search(
                [
                    ("company_id", "=", r.company_id.id),
                    (
                        "name",
                        "=",
                        r.timbrado,
                    ),  # <-- si el nro está en otro campo, cambiá acá
                ],
                limit=1,
            )
            r.timbrado_id = stamped.id if stamped else False

    def _normalize_vals(self, vals):
        def zfill(v, n):
            if v is None:
                return v
            return str(v).zfill(n)

        if "establecimiento" in vals:
            vals["establecimiento"] = zfill(vals["establecimiento"], 3)
        if "punto_expedicion" in vals:
            vals["punto_expedicion"] = zfill(vals["punto_expedicion"], 3)
        if "numero_ini" in vals:
            vals["numero_ini"] = zfill(vals["numero_ini"], 7)
        if "numero_fin" in vals:
            vals["numero_fin"] = zfill(vals["numero_fin"], 7)

        return vals

    def _resolve_timbrado(self):
        self.ensure_one()
        company = self.company_id

        if not company.fcws_docstamp_number:
            raise ValidationError(_("Falta configurar el número de timbrado en la compañía."))

        if not company.fcws_timbrado_fec_ini:
            raise ValidationError(_("Falta la fecha de inicio del timbrado en la compañía."))

        timbrado = company.fcws_docstamp_number if company.fcws_is_production else company.fcws_docstamp_number_test
        if not timbrado:
            raise ValidationError(_("Falta configurar el timbrado FCWS en la compañía."))
        return str(timbrado)
 
    def _move_type_for_inutilization(self):
        self.ensure_one()
        return "out_invoice" if self.type == "invoice" else "out_refund"

    def _extract_number_from_move_name(self, move_name):
        """
        Espera formato: 001-001-0000123
        Devuelve int(0000123) o None si no matchea.
        """
        if not move_name:
            return None
        m = re.match(r"^\s*(\d{3})-(\d{3})-(\d+)\s*$", move_name)
        if not m:
            return None
        try:
            return int(m.group(3))
        except Exception:
            return None

    def _validate_numbers_not_exist(self):
        for r in self:
            if r.type not in ("invoice", "credit_note"):
                continue

            # Normalizar sin escribir en DB (evita loop)
            est = (r.establecimiento or "").zfill(3)
            pex = (r.punto_expedicion or "").zfill(3)
            ini_str = (r.numero_ini or "").zfill(7)
            fin_str = (r.numero_fin or "").zfill(7)

            ini = r._to_int(ini_str, "Número inicial")
            fin = r._to_int(fin_str, "Número final")

            move_type = "out_invoice" if r.type == "invoice" else "out_refund"
            prefix = f"{est}-{pex}-"

            # timbrado_id debe existir en fcws.inutilization
            if not r.timbrado_id:
                raise ValidationError(_("Debe seleccionar un Timbrado."))

            candidates = self.env["account.move"].search(
                [
                    ("company_id", "=", r.company_id.id),
                    ("move_type", "=", move_type),
                    ("state", "!=", "cancel"),
                    ("timbrado_id", "=", r.timbrado_id.id),
                    ("name", "=like", prefix + "%"),
                ]
            )

            for mv in candidates:
                n = r._extract_number_from_move_name(mv.name)
                if n is not None and ini <= n <= fin:
                    raise ValidationError(
                        _("No se puede inutilizar %s..%s porque ya existe %s con número %s.")
                        % (ini_str, fin_str, mv.display_name, str(n).zfill(7))
                    )
