import datetime
import json
import random
import uuid
import hmac

import pytest
from pydantic import TypeAdapter
from fastapi.testclient import TestClient

from netbox_webhook.netbox import app
from netbox_webhook.models import api, IPAddressEvent
from netbox_webhook.netbox import sign
client = TestClient(app)

def test_client_static():
    msg = b'''{"event": "updated", "timestamp": "2023-07-26 06:29:04.020685+00:00", "model": "ipaddress", "username": "admin",
     "request_id": "79fd00b5-90e1-41a0-b3a6-c039c241a1c2",
     "data": {"id": 1, "url": "/api/ipam/ip-addresses/1/", "display": "10.0.0.1/32",
              "family": {"value": 4, "label": "IPv4"}, "address": "10.0.0.1/32", "vrf": null, "tenant": null,
              "status": {"value": "active", "label": "Active"}, "role": null, "assigned_object_type": null,
              "assigned_object_id": null, "assigned_object": null, "nat_inside": null, "nat_outside": [],
              "dns_name": "foffy1234", "description": "", "comments": "", "tags": [], "custom_fields": {},
              "created": "2023-07-26T06:02:42.514582Z", "last_updated": "2023-07-26T06:29:03.975344Z"}, "snapshots": {
        "prechange": {"created": "2023-07-26T06:02:42.514Z", "last_updated": "2023-07-26T06:28:17.959Z",
                      "description": "", "comments": "", "address": "10.0.0.1/32", "vrf": null, "tenant": null,
                      "status": "active", "role": "", "assigned_object_type": null, "assigned_object_id": null,
                      "nat_inside": null, "dns_name": "foffy123", "custom_fields": {}, "tags": []},
        "postchange": {"created": "2023-07-26T06:02:42.514Z", "last_updated": "2023-07-26T06:29:03.975Z",
                       "description": "", "comments": "", "address": "10.0.0.1/32", "vrf": null, "tenant": null,
                       "status": "active", "role": "", "assigned_object_type": null, "assigned_object_id": null,
                       "nat_inside": null, "dns_name": "foffy1234", "custom_fields": {}, "tags": []}}}'''

    response = client.post("/webhook", content=msg, headers={"X-Hook-Signature":sign(msg)})
#    assert response.status_code == 204

    if response.status_code != 204:
        print(msg)
        print(json.dumps(response.json(), indent=4))


def test_client_webhook():

    _IPAddress = api.components.schemas["IPAddress"].get_type()
    _IPAddressRequest = api.components.schemas["IPAddressRequest"].get_type()
    args = dict(id=0, url="/", display="address", family=dict(value=4, label="IPv4"), address="127.0.0.1",nat_outside=[],
                status=dict(value="active", label="Active"),
                role=None)
    addr = _IPAddress(dns_name="new", **args)
    args["status"] = "active"
    args["role"] = ""
    pre = _IPAddressRequest(dns_name="old", **args)
    post = _IPAddressRequest(dns_name="new", **args)
    data = IPAddressEvent(event="created",
                          timestamp=datetime.datetime.now(),
                          username="user01",
                          request_id=uuid.uuid4(),
                          data = addr,
                          snapshots = IPAddressEvent.Snapshot(prechange=pre, postchange=post)
                          )
    msg = data.model_dump(mode="json")
    msg = json.dumps(msg, indent=4).encode()


    response = client.post("/webhook", content=msg, headers={"X-Hook-Signature":sign(msg)})
    assert response.status_code == 204

    if response.status_code != 204:
        print(msg)
        print(json.dumps(response.json(), indent=4))


    data.event = "updated"
    msg = data.model_dump(mode="json")
    msg = json.dumps(msg, indent=4).encode()

    response = client.post("/webhook", content=msg, headers={"X-Hook-Signature":sign(msg)})

    assert response.status_code == 204
    if response.status_code != 204:
        print(msg)
        print(json.dumps(response.json(), indent=4))

    response = client.post("/webhook", content=msg, headers={"X-Hook-Signature": "signature"})
    assert response.status_code == 400 and response.json()["detail"].startswith("Invalid message signature")

