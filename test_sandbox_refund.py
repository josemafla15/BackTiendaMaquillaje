"""
Prueba manual del reembolso contra sandbox de Wompi.
Uso: python test_sandbox_refund.py <wompi_transaction_id> <amount_in_cents>

Ejemplo: python test_sandbox_refund.py abc123 5000000
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backTiendaMaquillaje.settings")
django.setup()

from apps.payments.wompi import WompiService


def test_refund(transaction_id: str, amount_in_cents: int):
    wompi = WompiService()

    print(f"\n{'='*50}")
    print(f"Consultando transacción: {transaction_id}")
    print(f"{'='*50}")

    txn = wompi.get_transaction(transaction_id)
    if not txn:
        print("❌ Transacción no encontrada")
        return

    print(f"✅ Transacción encontrada:")
    print(f"   Status:    {txn.get('status')}")
    print(f"   Referencia: {txn.get('reference')}")
    print(f"   Monto:     {txn.get('amount_in_cents')} centavos")

    if txn.get("status") != "APPROVED":
        print(f"❌ No se puede reembolsar — estado: {txn.get('status')}")
        return

    print(f"\nSolicitando reembolso de {amount_in_cents} centavos...")
    result = wompi.refund_transaction(transaction_id, amount_in_cents)

    if result:
        print(f"✅ Reembolso procesado:")
        print(f"   ID:     {result.get('id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Monto:  {result.get('amount_in_cents')} centavos")
    else:
        print("❌ Error al procesar el reembolso en Wompi")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python test_sandbox_refund.py <transaction_id> <amount_in_cents>")
        sys.exit(1)

    test_refund(sys.argv[1], int(sys.argv[2]))