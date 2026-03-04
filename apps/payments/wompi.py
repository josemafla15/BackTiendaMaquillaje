from __future__ import annotations

import hashlib
import hmac
import logging
import requests

from django.conf import settings

logger = logging.getLogger(__name__)


class WompiService:
    """
    Cliente para la API de Wompi.
    Documentación: https://docs.wompi.co
    """

    def __init__(self):
        self.public_key       = settings.WOMPI_PUBLIC_KEY
        self.private_key      = settings.WOMPI_PRIVATE_KEY
        self.events_secret    = settings.WOMPI_EVENTS_SECRET
        self.integrity_secret = settings.WOMPI_INTEGRITY_SECRET   # ← nuevo
        self.base_url         = settings.WOMPI_BASE_URL

    # ─── Firma de integridad ───────────────────────────────────────────────

    def generate_integrity_hash(
        self,
        reference: str,
        amount_in_cents: int,
        currency: str = "COP",
    ) -> str:
        """
        Genera el hash de integridad requerido por el Widget de Wompi.
        Concatena: reference + amount_in_cents + currency + integrity_secret
        y aplica SHA256.
        """
        raw = f"{reference}{amount_in_cents}{currency}{self.integrity_secret}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # ─── Aceptación de términos ────────────────────────────────────────────

    def get_acceptance_token(self) -> str:
        """
        Obtiene el acceptance_token requerido para transacciones.
        """
        try:
            response = requests.get(
                f"{self.base_url}/merchants/{self.public_key}",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"]["presigned_acceptance"]["acceptance_token"]
        except Exception as e:
            logger.error("Error obteniendo acceptance token de Wompi: %s", e)
            return ""

    # ─── Consulta de transacción ───────────────────────────────────────────

    def get_transaction(self, transaction_id: str) -> dict | None:
        """
        Consulta el estado de una transacción por su ID.
        """
        try:
            response = requests.get(
                f"{self.base_url}/transactions/{transaction_id}",
                headers={"Authorization": f"Bearer {self.private_key}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("data")
        except Exception as e:
            logger.error("Error consultando transacción %s: %s", transaction_id, e)
            return None

    def get_transaction_by_reference(self, reference: str) -> dict | None:
        """
        Consulta el estado de una transacción por referencia.
        """
        try:
            response = requests.get(
                f"{self.base_url}/transactions",
                headers={"Authorization": f"Bearer {self.private_key}"},
                params={"reference": reference},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json().get("data", [])
            return data[0] if data else None
        except Exception as e:
            logger.error("Error consultando transacción por referencia %s: %s", reference, e)
            return None

    # ─── Validación de webhook ─────────────────────────────────────────────

    def validate_webhook_signature(
        self,
        properties: dict,
        checksum: str,
        timestamp: str,
    ) -> bool:
        """
        Valida la firma de un evento webhook de Wompi.
        """
        try:
            concat  = "".join(str(v) for v in properties.values())
            concat += timestamp
            concat += self.events_secret
            expected = hashlib.sha256(concat.encode()).hexdigest()
            return hmac.compare_digest(expected, checksum)
        except Exception as e:
            logger.error("Error validando firma webhook: %s", e)
            return False


    # ─── Devolucion wompi ─────────────────────────────────────────────

    def refund_transaction(self, transaction_id: str, amount_in_cents: int) -> dict | None:
        endpoint = "void" if settings.WOMPI_SANDBOX else "refund"
        try:
            response = requests.post(
                f"{self.base_url}/transactions/{transaction_id}/{endpoint}",
                headers={"Authorization": f"Bearer {self.private_key}"},
                json={"amount_in_cents": amount_in_cents},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            # void devuelve {"status": "APPROVED", "transaction": {...}}
            # refund devuelve {"id": "...", "status": "APPROVED"}
            if "transaction" in data:
                return {"id": transaction_id, "status": data.get("status")}
            return data
        except Exception as e:
            logger.error("Error procesando reembolso Wompi txn %s: %s", transaction_id, e)
            return None