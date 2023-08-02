import hmac
import logging
from typing import Annotated
from fastapi import FastAPI, Header, Response, Body, HTTPException

from . import models

APP_NAME = "dnstools.netbox.webhook"
#WEBHOOK_SECRET = ''.join([chr(random.randint(0,255)) for i in range(32)])
WEBHOOK_SECRET = "secret!"

log = logging.getLogger(APP_NAME)
log.setLevel(logging.INFO)

app = FastAPI(
    title="NetBox Webhook Listener",
    description="using the NetBox OpenAPI3 Description Document to create the Models which are used in the Webhook",
    version="1.0",
    servers=[{"url": "/", "description": "Default, relative server"}],
#    debug=True,
)

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import json
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    log.exception(exc)
    print(json.dumps(exc.body, indent=4))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


def sign(body):
    digest = hmac.new(
        key=WEBHOOK_SECRET.encode(),
        msg=body,
        digestmod="sha512"
    )
    return digest.hexdigest()

@app.post("/webhook", response_model=None, status_code=204, operation_id="webhook",
          responses={"400":{"model": models.Error}})
async def webhook(
    _data: Annotated[models.Event, Body()],
    request: Request,
    response: Response,
    content_length: int = Header(None),
    x_hook_signature: str = Header(None)
) -> None:

    response.status_code = 204
    if content_length > 1_000_000:
        # To prevent memory allocation attacks
        log.error(f"Content too long ({content_length})")
        raise HTTPException(status_code=400, detail=f"Content too long ({content_length})")

    if x_hook_signature:
        body = await request.body()
        if not hmac.compare_digest((digest:=sign(body)), x_hook_signature):
            log.error("Invalid message signature")
            raise HTTPException(status_code=400, detail=f"Invalid message signature {digest}")
        log.info("Message signature checked ok")
    elif app.debug:
        log.info("No message signature to check - debug mode")
    else:
        raise HTTPException(status_code=400, detail=f"Missing message signature")

    log.info(f"Event received: {_data}")
    if isinstance(_data.root, models.IPAddressEvent):
        print(json.dumps(json.loads(body), indent=4))
        m: models.IPAddressEvent = _data.root

        _add = _del = None

        if m.event == "created":
            _add = m.data.dns_name
        elif m.event == "updated":
            if (s:=m.snapshots):
                s: models._Snapshots
                if s.prechange and s.postchange:
                    if s.prechange.dns_name != s.postchange.dns_name:
                        _add = s.postchange.dns_name
                        _del = s.prechange.dns_name
        elif m.event == "deleted":
            if (s:=m.snapshots):
                s: models._Snapshots
                if s.prechange:
                    _del = s.prechange.dns_name
        elif m.event.startswith("job_"):
            return
        else:
            raise ValueError(m.event)

        if not any([_add, _del]):
            print("no changes")

        if _add:
            print(f"add name {_add}")

        if _del:
            print(f"del name {_del}")
    elif isinstance(_data.root, (models.NameServerEvent, models.ViewEvent, models.ZoneEvent, models.RecordEvent)):
        print(_data)
    else:
        raise TypeError(_data.model)

