import json
import logging
import unicodedata

import requests

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FCWSClient(models.AbstractModel):
    _name = "fcws.client"
    _description = "Cliente API FCWS (Factura Criterium Web Service)"

    # ----------------------------------------------------------------------
    # Configuración
    # ----------------------------------------------------------------------
    def _get_base_url(self):
        company = self.env.company
        base_url = company.fcws_base_url or "https://ekuatia.criterium.com.py/fcws"
        return base_url.rstrip("/")

    def _get_headers(self):
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }

    # ----------------------------------------------------------------------
    # Credenciales
    # ----------------------------------------------------------------------
    def _get_taxpayer_data(self):
        """Obtiene credenciales del contribuyente desde la compañía activa."""
        company = self.env.company  # ← en lugar de ir.config_parameter

        is_prod = bool(company.fcws_is_production)
        contribuyente_id = company.fcws_prod_user if is_prod else company.fcws_test_user
        password = company.fcws_prod_password if is_prod else company.fcws_test_password

        if not contribuyente_id:
            raise ValidationError(
                _("Falta cargar el ID de contribuyente en la compañía '%s'.")
                % company.display_name
            )
        if not password:
            raise ValidationError(
                _("Falta cargar la contraseña del contribuyente en la compañía '%s'.")
                % company.display_name
            )

        try:
            contribuyente_id = int(str(contribuyente_id).strip())
        except ValueError:
            raise ValidationError(
                _("El ID de contribuyente debe ser numérico (valor actual: %s).")
                % contribuyente_id
            )

        _logger.info(
            "[FCWS] Empresa: %s | Ambiente: %s | Contribuyente ID: %s",
            company.name,
            "Producción" if is_prod else "Test",
            contribuyente_id,
        )

        return {"contribuyenteid": contribuyente_id, "pass": password}

    # ----------------------------------------------------------------------
    # Sanitización de caracteres
    # ----------------------------------------------------------------------
    def _sanitize_ascii(self, obj):
        """Elimina acentos y ñ de forma recursiva."""
        if isinstance(obj, (int, float)) or obj is None:
            return str(obj) if obj is not None else ""
        if isinstance(obj, str):
            nfkd = unicodedata.normalize("NFKD", obj)
            only_ascii = nfkd.encode("ASCII", "ignore").decode("ASCII")
            return " ".join(only_ascii.split())
        elif isinstance(obj, dict):
            return {k: self._sanitize_ascii(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_ascii(i) for i in obj]
        return obj

    # ----------------------------------------------------------------------
    # Llamadas HTTP
    # ----------------------------------------------------------------------
    def _request(self, endpoint, method="GET", data=None, timeout=30):
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        clean_data = self._sanitize_ascii(data or {})
        payload = json.dumps(clean_data, ensure_ascii=False).encode("utf-8")

        _logger.info("[FCWS] %s %s", method, url)
        _logger.debug(
            "[FCWS] Payload JSON: %s",
            json.dumps(clean_data, ensure_ascii=False, indent=2),
        )

        try:
            if method.upper() == "POST":
                response = requests.post(
                    url, headers=headers, data=payload, timeout=timeout
                )
            else:
                response = requests.get(url, headers=headers, timeout=timeout)

            _logger.debug(
                "[FCWS] Response %s: %s", response.status_code, response.text[:800]
            )

            if not response.ok:
                raise ValidationError(
                    _("Error HTTP %s: %s") % (response.status_code, response.text)
                )

            try:
                result = response.json()
                if isinstance(result, list) and len(result) == 1:
                    result = result[0]
                return result
            except ValueError:
                _logger.warning("[FCWS] Respuesta no JSON, devolviendo texto plano")
                return response.text

        except requests.Timeout:
            raise ValidationError(_("Timeout conectando con FCWS"))
        except requests.ConnectionError:
            raise ValidationError(_("Error de conexión con FCWS"))
        except Exception as e:
            raise ValidationError(_("Error al llamar FCWS: %s") % str(e))

    # ----------------------------------------------------------------------
    # Endpoints
    # ----------------------------------------------------------------------
    def send_invoice(self, data):
        return self._request("factura", "POST", data)

    def send_credit_note(self, data):
        return self._request("notacredito", "POST", data)

    def send_delivery_note(self, data):
        return self._request("remision", "POST", data)

    def consult_document(self, cdc):
        return self._request(f"consultar/comprobante/{cdc}", "GET")

    def cancel_invoice(self, data):
        return self._request("evento/cancelarfactura", "POST", data)

    def cancel_credit_note(self, data):
        return self._request("evento/cancelarnotacredito", "POST", data)

    def disable_invoice(self, data):
        return self._request("evento/inutilizacionnumfactura", "POST", data)

    def disable_credit_note(self, data):
        return self._request("evento/inutilizacionnumnotacredito", "POST", data)
