# smm_api.py
# 1xpanel.com SMM panel API bilan ishlash (nakrutka xizmatlari).
# Berilgan PHP misolining Python (requests) ko'rinishi.
import requests
from config import SMM_API_KEY, SMM_API_URL


def _call(data: dict):
    payload = {"key": SMM_API_KEY, **data}
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=20)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_services():
    """Panelning barcha xizmatlari ro'yxatini qaytaradi."""
    return _call({"action": "services"})


def get_balance():
    """Panel hisobingizdagi balansni qaytaradi."""
    return _call({"action": "balance"})


def place_order(service_id: int, link: str, quantity: int):
    """Panelga yangi buyurtma joylashtiradi."""
    return _call({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity,
    })


def get_order_status(order_id: int):
    """Buyurtma holatini (qancha bajarilgani) qaytaradi."""
    return _call({"action": "status", "order": order_id})
