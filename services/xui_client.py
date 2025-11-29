import logging
import httpx
import uuid
import time
import json
from config import settings

logger = logging.getLogger("xui_client")


class XuiError(Exception):
    pass


async def xui_login(client: httpx.AsyncClient):
    resp = await client.post(
        "/login",
        data={"username": settings.XUI_USERNAME, "password": settings.XUI_PASSWORD},
        follow_redirects=True,
    )
    if resp.status_code != 200:
        raise XuiError(f"Failed to login: {resp.text}")


async def get_inbound(client: httpx.AsyncClient, inbound_id: int):
    resp = await client.get("/panel/api/inbounds/list")

    if resp.status_code != 200:
        raise XuiError(f"Failed to fetch inbounds: {resp.text}")

    for inbound in resp.json()["obj"]:
        if inbound["id"] == inbound_id:
            return inbound

    raise XuiError(f"Inbound {inbound_id} not found")


def get_base_host():
    url = settings.XUI_BASE_URL.replace("http://", "").replace("https://", "")
    return url.split(":")[0]


def build_vless(uid, host, port, tag, fake_id, pbk, sid):
    return (
        f"vless://{uid}@{host}:{port}"
        f"?type=xhttp"
        f"&encryption=none"
        f"&path=%2Fnews"
        f"&host=quad9.net"
        f"&mode=auto"
        f"&security=reality"
        f"&pbk={pbk}"
        f"&fp=chrome"
        f"&sni=google.com"
        f"&sid={sid}"
        f"&spx=%2F"
        f"#Kynix-VPN-{tag}-{fake_id}"
    )


async def create_xui_client(fake_id: int, expiry_ts: int, tag: str, inbound_id: int):
    async with httpx.AsyncClient(base_url=settings.XUI_BASE_URL) as client:

        # login
        await xui_login(client)

        # inbound info
        inbound = await get_inbound(client, inbound_id)

        stream_obj = json.loads(inbound["streamSettings"])
        reality = stream_obj["realitySettings"]

        pbk = reality["settings"]["publicKey"]
        sid = reality["shortIds"][0]

        host = get_base_host()
        port = inbound["port"]

        # client details
        uid = str(uuid.uuid4())
        subid = uuid.uuid4().hex[:16]
        email = f"{fake_id}"

        client_js = {
            "id": uid,
            "email": email,
            "enable": True,
            "expiryTime": expiry_ts,
            "limitIp": 0,
            "totalGB": 0,
            "tgId": 0,
            "reset": 0,
            "flow": "xtls-rprx-vision",
        }

        resp = await client.post(
            "/panel/api/inbounds/addClient",
            json={
                "id": inbound_id,
                "remark": "",
                "enable": True,
                "expiryTime": expiry_ts,
                "totalGB": 0,
                "client": client_js,  # клиент внутри ключа client
            },
        )

        if resp.status_code != 200:
            raise XuiError(f"addClient failed: {resp.text}")

        try:
            j = resp.json()
            if isinstance(j, dict) and not j.get("success", True):
                raise XuiError(f"addClient rejected: {resp.text}")
        except:
            pass

        vless = build_vless(uid, host, port, tag, fake_id, pbk, sid)

        return {
            "uuid": uid,
            "subId": subid,
            "email": email,
            "vless": vless,
        }


async def create_client_for_user(fake_id: int, days: int):
    expiry_ts = int(time.time() * 1000 + days * 86400 * 1000)
    inbound_plus = int(settings.XUI_INBOUND_ID)

    return await create_xui_client(
        fake_id=fake_id,
        expiry_ts=expiry_ts,
        tag="Plus",
        inbound_id=inbound_plus,
    )


async def create_client_inf(fake_id: int):
    inbound_inf = int(settings.XUI_INBOUND_ID_INF)

    return await create_xui_client(
        fake_id=fake_id,
        expiry_ts=0,
        tag="Inf",
        inbound_id=inbound_inf,
    )


async def delete_xui_client(email: str, inbound_id: int | None = None):
    inbound_id = inbound_id or int(settings.XUI_INBOUND_ID)

    async with httpx.AsyncClient(base_url=settings.XUI_BASE_URL) as client:
        await xui_login(client)
        inbound = await get_inbound(client, inbound_id)

        settings_obj = json.loads(inbound["settings"])
        clients = settings_obj.get("clients", [])

        client_to_delete = next(
            (c for c in clients if str(c.get("email")) == str(email)),
            None,
        )

        if client_to_delete is None:
            raise XuiError(f"Client {email} not found in inbound {inbound_id}")

        client_uuid = client_to_delete.get("id") or client_to_delete.get("uuid")

        resp = await client.post(
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}"
        )

        if resp.status_code != 200:
            raise XuiError(f"deleteClient failed: {resp.text}")

        try:
            j = resp.json()
            if isinstance(j, dict) and not j.get("success", True):
                raise XuiError(f"deleteClient rejected: {resp.text}")
        except:
            pass

        logger.info(
            "Deleted X-UI client email=%s uuid=%s inbound=%s",
            email,
            client_uuid,
            inbound_id,
        )
