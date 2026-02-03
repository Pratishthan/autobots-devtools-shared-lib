# ABOUTME: Dataclass models for structured agent outputs.
# ABOUTME: Used with response_format parameter in create_agent().

from dataclasses import dataclass, field


@dataclass
class JokeOutput:
    """Structured output for joke_agent."""

    joke: str  # The joke text
    category: str  # Category: pun, wordplay, observational, etc.


@dataclass
class MathOutput:
    """Structured output for math_agent."""

    answer: float  # The numerical answer
    explanation: str  # Step-by-step explanation


# Vision agent outputs (matching schemas/vision-agent/*.json)


@dataclass
class ReferenceDocument:
    """Single reference document in the preface."""

    name: str  # Document name or title
    url: str | None = None  # Link to the document
    description: str | None = None  # Brief description of relevance


@dataclass
class GlossaryTerm:
    """Single term in the glossary."""

    term: str  # Term or abbreviation
    definition: str  # Definition of the term


@dataclass
class PrefaceOutput:
    """Structured output for preface_agent (01-preface.json)."""

    about_this_guide: str  # Description of what this document contains (min 20 chars)
    audience: list[str]  # List of intended audience types (min 1 item)
    reference_documents: list[ReferenceDocument] = field(
        default_factory=list
    )  # Related docs
    glossary: list[GlossaryTerm] = field(default_factory=list)  # Term definitions


@dataclass
class FeatureItem:
    """Single feature in the features list."""

    name: str  # Feature name (3-100 chars)
    description: str  # Feature description (min 10 chars)
    # One of: core, integration, admin, reporting, security, other
    category: str = "core"
    priority: str = "should_have"  # must_have, should_have, nice_to_have


@dataclass
class GettingStartedOutput:
    """Structured output for getting_started_agent (02-getting-started.json)."""

    overview: str  # High-level overview of the component (min 50 chars)
    vision: str  # Long-term vision and aspirations (min 50 chars)
    success_metrics: list[str] = field(default_factory=list)  # Key success metrics


@dataclass
class FeaturesOutput:
    """Structured output for features_agent (03-01-list-of-features.json)."""

    features: list[FeatureItem]  # List of features (min 1 item)


@dataclass
class AttributeConstraints:
    """Validation constraints for an entity attribute."""

    minLength: int | None = None
    maxLength: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    enum: list[str] | None = None


@dataclass
class EntityAttribute:
    """Single attribute in an entity."""

    name: str  # Attribute name
    # Data type: string, number, boolean, date, datetime, object, array,
    # uuid, email, url
    type: str
    required: bool = False  # Whether this attribute is required
    description: str | None = None  # What this attribute represents
    constraints: AttributeConstraints | None = None  # Validation constraints


@dataclass
class EntityRelationship:
    """Relationship to another entity."""

    entity: str  # Related entity name
    type: str  # Relationship cardinality: one-to-one, one-to-many, many-to-many
    required: bool = False  # Whether this relationship is required
    description: str | None = None  # Description of the relationship


@dataclass
class EntityOutput:
    """Structured output for entity agents (05-entity.json)."""

    name: str  # Entity name in PascalCase or kebab-case (2-100 chars)
    description: str  # What this entity represents (min 10 chars)
    attributes: list[EntityAttribute]  # Entity attributes/fields (min 1 item)
    purpose: str | None = None  # Why this entity exists in the system
    relationships: list[EntityRelationship] = field(
        default_factory=list
    )  # Relationships to other entities
    business_rules: list[str] = field(
        default_factory=list
    )  # Business rules and constraints
