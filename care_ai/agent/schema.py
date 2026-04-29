from itertools import count
from typing import Any

import jsonschema
from pydantic import BaseModel, Field, create_model


class InvalidResponseSchema(ValueError):
    """Raised when the FE-supplied response_schema is not a valid JSON Schema object."""


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}

_model_seq = count(1)


def validate_response_schema(schema: dict) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise InvalidResponseSchema(str(exc)) from exc
    if schema.get("type") != "object":
        raise InvalidResponseSchema("response_schema must have type=object at the root")


def json_schema_to_pydantic(schema: dict | None) -> type[BaseModel] | None:
    """Build a pydantic model from a JSON Schema for use as Agents SDK output_type."""
    if schema is None:
        return None
    validate_response_schema(schema)
    return _build_object_model(schema, name="AskResponse")


def _build_object_model(schema: dict, name: str) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    required = set(schema.get("required", []))
    for prop_name, prop in schema.get("properties", {}).items():
        py_type = _resolve_type(prop, parent_name=f"{name}_{prop_name}")
        description = prop.get("description")
        if prop_name in required:
            fields[prop_name] = (py_type, Field(..., description=description))
        else:
            fields[prop_name] = (py_type | None, Field(None, description=description))
    return create_model(name, **fields)


def _resolve_type(prop: dict, parent_name: str = "Item") -> Any:
    t = prop.get("type")
    if t == "object":
        return _build_object_model(prop, name=f"{parent_name}_{next(_model_seq)}")
    if t == "array":
        items = prop.get("items", {})
        item_type = _resolve_type(items, parent_name=parent_name) if items else Any
        return list[item_type]
    return _TYPE_MAP.get(t, Any)
