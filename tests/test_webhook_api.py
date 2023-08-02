import pytest
import pytest_asyncio

import asyncio
import uvloop
from hypercorn.asyncio import serve
from hypercorn.config import Config

import aiopenapi3

from netbox_webhook.netbox import app, sign
from netbox_webhook.models import Event

#app.debug = True

@pytest.fixture(scope="session")
def config(unused_tcp_port_factory):
    c = Config()
    c.bind = [f"localhost:{unused_tcp_port_factory()}"]
    return c

@pytest.fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def client(event_loop, server):
    url = f"http://{server.bind[0]}/openapi.json"
    from aiopenapi3.debug import DescriptionDocumentDumper
    class XHookSignature(aiopenapi3.plugin.Message):
        def sending(self, ctx: "Message.Context") -> "Message.Context":
            ctx.headers["X-Hook-Signature"] = sign(ctx.sending)
            return ctx
    plugins = [XHookSignature()]
    if False:
        plugins.append(DescriptionDocumentDumper("netbox-webhook-schema.yaml"))
    api = await aiopenapi3.OpenAPI.load_async(url, plugins=plugins)
    return api

@pytest_asyncio.fixture(scope="session")
async def server(event_loop, config):
    policy = asyncio.get_event_loop_policy()
    uvloop.install()
    try:
        sd = asyncio.Event()
        task = event_loop.create_task(serve(app, config, shutdown_trigger=sd.wait))
        yield config
    finally:
        sd.set()
        await task
    asyncio.set_event_loop_policy(policy)

@pytest.fixture
def event(client):
    import datetime
    import uuid
    _IPAddressEvent = client.components.schemas["IPAddressEvent"].get_type()
    _IPAddress = client.components.schemas["IPAddress"].get_type()
    _IPAddressRequest = client.components.schemas["IPAddressRequest"].get_type()
    _Snapshot = client.components.schemas["IPAddressEvent"].properties["snapshots"].get_type()
    args = dict(id=0, url="/", display="address", family=dict(value=4, label="IPv4"), address="127.0.0.1", nat_outside=[], status=dict(value="active", label="Active"),
                role=None)
    addr = _IPAddress(dns_name="new", **args)
    args["status"] = "active"
    args["role"] = ""
    pre = _IPAddressRequest(dns_name="old", **args)
    post = _IPAddressRequest(dns_name="old", **args)

    data = _IPAddressEvent(event="created",
                          timestamp=datetime.datetime.now(),
                          username="user01",
                          request_id=uuid.uuid4(),
                          data=addr,
                          snapshots=_Snapshot(prechange=pre, postchange=post)
                          )
    return data

@pytest.mark.asyncio
async def test_webhook_api(event_loop, client, event):

    assert client.components.schemas["IPAddressEvent"].get_type().model_validate(event.model_dump(mode="json")).model_dump() == event.model_dump()

    Event.model_validate(event.model_dump(mode="json"))

    req = client.createRequest(("/webhook", "post"))
    r = await req(data=event)
    assert r is None
    r = await client._.webhook(data=event)
    assert r is None