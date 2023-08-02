# netbook-webhook
A [FastAPI](https://github.com/tiangolo/fastapi) service using models created by [aiopenapi3](https://github.com/commonism/aiopenapi3) from the Netbox OpenAPI Description Document to create models for the webhook.  

## Requirements
Your Netbox [OpenAPI](tests/data/README.md) Description Document.

## Installation
Running the service on port 8053
Currently the HMAC512 secret is `secret!`.
```
python3 -m venv /tmp/nbwh
/tmp/nbwh/bin/pip install .
/tmp/nbwh/python3 -m uvicorn netbox_webhook.netbox:app --reload --port 8053 --host 0.0.0.0
```
