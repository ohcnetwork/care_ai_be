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
    "array": list,
    "object": dict,
}


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

    fields: dict[str, tuple[Any, Any]] = {}
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        py_type = _resolve_type(prop)
        if name in required:
            fields[name] = (py_type, Field(..., description=prop.get("description")))
        else:
            fields[name] = (py_type | None, Field(None, description=prop.get("description")))

    return create_model("AskResponse", **fields)


def _resolve_type(prop: dict) -> Any:
    t = prop.get("type")
    if t == "array":
        items = prop.get("items", {})
        item_type = _resolve_type(items) if items else Any
        return list[item_type]
    return _TYPE_MAP.get(t, Any)
