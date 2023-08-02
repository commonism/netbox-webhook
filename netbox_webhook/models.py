import datetime
import uuid
from pathlib import Path
from typing import Annotated, Union, TypeVar, Generic, Literal, ClassVar
import sys

from aiopenapi3 import OpenAPI, FileSystemLoader
from pydantic import BaseModel, Field, RootModel, ConfigDict, create_model


class Error(BaseModel):
    """
    used by HTTPException
    """
    model_config = ConfigDict(allow="forbid")
    detail: str

def createAPI(*names) -> OpenAPI:
    """
    to speed up things, we use some aiopenapi3 plugins to limit the loading process to the schemas required
    removing all paths
    """
    from aiopenapi3.plugin import Init, Document

    class SchemaSelector(Init):
        """
        remove the schemas we do not need models for
        """

        def __init__(self, *schemas):
            super().__init__()
            self.schemas = schemas

        def schema(self, ctx: "Init.Context") -> "Init.Context":
            ctx.schema = {k: ctx.schema[k] for k in (set(self.schemas) & set(ctx.schema.keys()))}
            return ctx

    class RemovePaths(Document):
        def parsed(self, ctx: "Document.Context") -> "Document.Context":
            """
            emtpy the paths - not needed
            """
            ctx.document["paths"] = {}
            return ctx

    # from aiopenapi3.debug import DescriptionDocumentDumper
    # DescriptionDocumentDumper("api-schema.yaml")
    selector = SchemaSelector(*(list(names) + [f"{name}Request" for name in names])) # + [f"Writable{name}Request" for name in names]))
    # dns.yaml = localhost:8000/api/schema/
    api = OpenAPI.load_file("/", Path("full.yaml"), loader=FileSystemLoader(Path("tests/data")), plugins=[selector, RemovePaths()])
    return api

NAMES = ["IPAddress",
#         "NameServer", "Zone", "View", "Record"
         ]
api = createAPI(*NAMES)

EventTypeT = TypeVar("EventType")
EventTypeRequestT = TypeVar("EventTypeRequest")

class _Snapshots(BaseModel, Generic[EventTypeRequestT]):
    prechange: EventTypeRequestT | None
    postchange: EventTypeRequestT | None


class _Event(BaseModel, Generic[EventTypeT, EventTypeRequestT]):
    """
    generic base class for events
    """
    Snapshot: ClassVar = _Snapshots[EventTypeRequestT]
    """
    required to have the Generic class definition available for use
    will be overwritten in the …Event
    """

    model_config = ConfigDict(extra="forbid")
    event: Literal["created","updated","deleted"]
    timestamp: datetime.datetime
    username: str
    request_id: uuid.UUID
    model: str
    data: EventTypeT
    snapshots: Snapshot[EventTypeRequestT]



def createEvent(name: str, model: str) -> _Event[EventTypeT, EventTypeRequestT]:
    """
    mimic

    class _IPAddressEvent(_Event[api.components.schemas["IPAddress"].get_type()]):
        Snapshot: ClassVar = _Snapshot[api.components.schemas["IPAddress"].get_type()]
        model: Literal["ipaddress"] = "ipaddress"

    :param name: name of class
    :param model: name of netbox model identifier
    """
    Event = api.components.schemas[f"{name}"].get_type()
    EventRequest = api.components.schemas[f"{name}Request"].get_type()
    m = create_model(f"{name}Event",
                     __base__=(_Event[Event, EventRequest],),
                     model=(Literal[model], model),
                     Snapshot=(ClassVar, _Snapshots[EventRequest]))
    return m


def createEvents(*names):
    events = list()
    for name in names:
        e = createEvent(name, name.lower())
        setattr(sys.modules[__name__], f"{name}Event", e)
        events.append(e)
    return tuple(events)

class Event(RootModel[Annotated[Union[createEvents(*NAMES)], Field(discriminator="model")]]):
    def __getattr__(self, item):
        return getattr(self.root, item)

