# ABOUTME: Formatting utilities for converting structured outputs to Markdown.
# ABOUTME: Designed for non-technical Product Owners viewing agent responses.

from typing import Any


def structured_to_markdown(data: dict[str, Any], title: str = "Response") -> str:
    """
    Convert a structured output dict to readable Markdown.

    Args:
        data: Structured response from agent (dict from dataclass)
        title: Section title for the markdown output

    Returns:
        Formatted markdown string
    """
    lines = [f"## {title}\n"]

    for key, value in data.items():
        # Convert snake_case to Title Case
        display_key = key.replace("_", " ").title()

        if isinstance(value, list):
            lines.append(f"**{display_key}:**\n")
            for item in value:
                if isinstance(item, dict):
                    # Nested object (e.g., FeatureItem)
                    lines.append(format_dict_item(item))
                else:
                    # Simple list item
                    lines.append(f"- {item}")
            lines.append("")  # Blank line

        elif isinstance(value, dict):
            # Nested object
            lines.append(f"**{display_key}:**\n")
            lines.append(format_dict_item(value))
            lines.append("")

        else:
            # Simple value (string, number, bool)
            lines.append(f"**{display_key}:** {value}\n")

    return "\n".join(lines)


def format_dict_item(item: dict[str, Any], indent: int = 0) -> str:
    """Format a dictionary item as indented key-value pairs."""
    lines = []
    prefix = "  " * indent

    for k, v in item.items():
        display_k = k.replace("_", " ").title()
        if isinstance(v, dict):
            lines.append(f"{prefix}- **{display_k}:**")
            lines.append(format_dict_item(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}- **{display_k}:** {', '.join(str(x) for x in v)}")
        else:
            lines.append(f"{prefix}- **{display_k}:** {v}")

    return "\n".join(lines)


def format_features_output(data: dict[str, Any]) -> str:
    """Specialized formatter for FeaturesOutput."""
    lines = ["## Features List\n"]

    features = data.get("features", [])
    for idx, feature in enumerate(features, 1):
        lines.append(f"### {idx}. {feature.get('name', 'Unnamed Feature')}")
        lines.append(f"{feature.get('description', '')}\n")
        lines.append(f"- **Category:** {feature.get('category', 'N/A')}")
        lines.append(f"- **Priority:** {feature.get('priority', 'should_have')}\n")

    return "\n".join(lines)


def format_preface_output(data: dict[str, Any]) -> str:
    """Specialized formatter for PrefaceOutput."""
    lines = ["## Preface\n"]

    lines.append(f"**About This Guide:**\n{data.get('about_this_guide', '')}\n")

    if audience := data.get("audience"):
        lines.append("**Intended Audience:**")
        for person in audience:
            lines.append(f"- {person}")
        lines.append("")

    if refs := data.get("reference_documents"):
        lines.append("**Reference Documents:**")
        for ref in refs:
            name = ref.get("name", "Unknown")
            url = ref.get("url", "")
            if url:
                lines.append(f"- [{name}]({url})")
            else:
                lines.append(f"- {name}")
        lines.append("")

    if glossary := data.get("glossary"):
        lines.append("**Glossary:**")
        for term in glossary:
            term_name = term.get("term", "")
            definition = term.get("definition", "")
            lines.append(f"- **{term_name}:** {definition}")
        lines.append("")

    return "\n".join(lines)


def format_getting_started_output(data: dict[str, Any]) -> str:
    """Specialized formatter for GettingStartedOutput."""
    lines = ["## Getting Started\n"]

    lines.append(f"**Overview:**\n{data.get('overview', '')}\n")
    lines.append(f"**Vision:**\n{data.get('vision', '')}\n")

    if metrics := data.get("success_metrics"):
        lines.append("**Success Metrics:**")
        for metric in metrics:
            lines.append(f"- {metric}")
        lines.append("")

    return "\n".join(lines)


def format_entity_output(data: dict[str, Any]) -> str:
    """Specialized formatter for EntityOutput."""
    lines = [f"## Entity: {data.get('name', 'Unnamed Entity')}\n"]

    lines.append(f"**Description:** {data.get('description', '')}\n")

    if purpose := data.get("purpose"):
        lines.append(f"**Purpose:** {purpose}\n")

    if attributes := data.get("attributes"):
        lines.append("### Attributes\n")
        for attr in attributes:
            attr_name = attr.get("name", "")
            attr_type = attr.get("type", "")
            required = " (required)" if attr.get("required") else ""
            lines.append(f"**{attr_name}** - `{attr_type}`{required}")

            if desc := attr.get("description"):
                lines.append(f"  - {desc}")

            if constraints := attr.get("constraints"):
                constraint_parts = []
                for k, v in constraints.items():
                    if v is not None:
                        constraint_parts.append(f"{k}: {v}")
                if constraint_parts:
                    lines.append(f"  - Constraints: {', '.join(constraint_parts)}")

            lines.append("")

    if relationships := data.get("relationships"):
        lines.append("### Relationships\n")
        for rel in relationships:
            entity = rel.get("entity", "")
            rel_type = rel.get("type", "")
            required = " (required)" if rel.get("required") else ""
            lines.append(f"**{entity}** - `{rel_type}`{required}")

            if desc := rel.get("description"):
                lines.append(f"  - {desc}")

            lines.append("")

    if rules := data.get("business_rules"):
        lines.append("### Business Rules\n")
        for rule in rules:
            lines.append(f"- {rule}")
        lines.append("")

    return "\n".join(lines)


# Mapping of output types to specialized formatters
OUTPUT_FORMATTERS = {
    "preface": format_preface_output,
    "getting_started": format_getting_started_output,
    "features": format_features_output,
    "entity": format_entity_output,
}


def format_structured_output(
    data: dict[str, Any], output_type: str | None = None
) -> str:
    """
    Format structured output for UI display.

    Args:
        data: Structured response dict
        output_type: Optional type hint (e.g., "features", "preface", "entity")

    Returns:
        Markdown-formatted string for display
    """
    # Use specialized formatter if available
    if output_type and output_type in OUTPUT_FORMATTERS:
        return OUTPUT_FORMATTERS[output_type](data)

    # Fall back to generic formatter
    return structured_to_markdown(data)
