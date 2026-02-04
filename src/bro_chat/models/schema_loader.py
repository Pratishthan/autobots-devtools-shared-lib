# ABOUTME: Runtime Pydantic model generation from JSON schemas.
# ABOUTME: Provides single source of truth - models generated from schemas/ directory.

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

# Cache for generated models
_MODEL_CACHE: dict[str, type[BaseModel]] = {}


def _get_python_type(schema_prop: dict[str, Any], context: dict[str, Any]) -> Any:
    """Convert JSON schema type to Python type.

    Args:
        schema_prop: JSON schema property definition.
        context: Context for nested model creation (contains 'models' dict).

    Returns:
        Python type annotation.
    """
    prop_type = schema_prop.get("type")

    if prop_type == "string":
        # Check for enum
        if "enum" in schema_prop:
            from enum import Enum

            enum_name = f"Enum_{id(schema_prop)}"
            # Create enum with string values
            enum_dict = {f"V{i}": val for i, val in enumerate(schema_prop["enum"])}
            enum_class = Enum(enum_name, enum_dict, type=str)  # type: ignore[call-overload]
            return enum_class
        return str
    elif prop_type == "integer":
        return int
    elif prop_type == "number":
        return float
    elif prop_type == "boolean":
        return bool
    elif prop_type == "array":
        items_schema = schema_prop.get("items", {})
        item_type = _get_python_type(items_schema, context)
        return list[item_type]  # type: ignore[valid-type]
    elif prop_type == "object":
        # Create nested model
        nested_name = f"Model_{id(schema_prop)}"
        if nested_name not in context.get("models", {}):
            nested_model = _create_model_from_schema(schema_prop, nested_name, context)
            context.setdefault("models", {})[nested_name] = nested_model
        return context["models"][nested_name]
    else:
        return Any


def _create_model_from_schema(
    schema: dict[str, Any], model_name: str, context: dict[str, Any]
) -> type[BaseModel]:
    """Create a Pydantic model from a JSON schema object definition.

    Args:
        schema: JSON schema object definition.
        model_name: Name for the model class.
        context: Context for nested model creation.

    Returns:
        Pydantic model class.
    """
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    field_definitions: dict[str, tuple[Any, Any]] = {}

    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required

        # Get Python type
        python_type = _get_python_type(prop_schema, context)

        # Build Field with constraints
        field_kwargs: dict[str, Any] = {}
        if "description" in prop_schema:
            field_kwargs["description"] = prop_schema["description"]
        if "minLength" in prop_schema:
            field_kwargs["min_length"] = prop_schema["minLength"]
        if "maxLength" in prop_schema:
            field_kwargs["max_length"] = prop_schema["maxLength"]
        if "minimum" in prop_schema:
            field_kwargs["ge"] = prop_schema["minimum"]
        if "maximum" in prop_schema:
            field_kwargs["le"] = prop_schema["maximum"]
        if "pattern" in prop_schema:
            field_kwargs["pattern"] = prop_schema["pattern"]
        if "minItems" in prop_schema:
            field_kwargs["min_length"] = prop_schema["minItems"]

        # Handle default values
        if "default" in prop_schema:
            field_definitions[prop_name] = (
                python_type,
                Field(default=prop_schema["default"], **field_kwargs),
            )
        elif not is_required:
            # Optional field
            field_definitions[prop_name] = (
                python_type | None,  # type: ignore[assignment,operator]
                Field(default=None, **field_kwargs),
            )
        else:
            # Required field
            field_definitions[prop_name] = (python_type, Field(**field_kwargs))

    return create_model(model_name, **field_definitions)  # type: ignore[return-value]


def get_model_for_schema(schema_path: str) -> type[BaseModel]:
    """Get or create Pydantic model for a JSON schema.

    Models are cached for performance.

    Args:
        schema_path: Path to schema relative to schemas/ directory
                    (e.g., "vision-agent/01-preface.json").

    Returns:
        Pydantic model class for the schema.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
        ValueError: If schema is invalid.
    """
    # Check cache first
    if schema_path in _MODEL_CACHE:
        return _MODEL_CACHE[schema_path]

    # Load JSON schema
    schema_file = Path("schemas") / schema_path
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    try:
        with open(schema_file) as f:
            json_schema = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file {schema_file}: {e}") from e

    # Validate schema structure
    if json_schema.get("type") != "object":
        raise ValueError(f"Schema {schema_path} must be an object type")

    properties = json_schema.get("properties", {})
    if not properties:
        raise ValueError(f"Schema {schema_path} has no properties")

    # Create model
    model_name = Path(schema_path).stem.replace("-", "_")
    model_name = "".join(word.capitalize() for word in model_name.split("_")) + "Output"

    context: dict[str, Any] = {"models": {}}
    try:
        model_class = _create_model_from_schema(json_schema, model_name, context)
        # Cache it
        _MODEL_CACHE[schema_path] = model_class
        logger.info(f"Created Pydantic model {model_name} for schema {schema_path}")
        return model_class
    except Exception as e:
        raise ValueError(f"Failed to create model for schema {schema_path}: {e}") from e
