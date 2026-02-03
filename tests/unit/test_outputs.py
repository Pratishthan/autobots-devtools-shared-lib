# ABOUTME: Unit tests for output dataclass models.
# ABOUTME: Validates structure and instantiation of agent output models.

from bro_chat.models.outputs import (
    AttributeConstraints,
    EntityAttribute,
    EntityOutput,
    EntityRelationship,
    FeatureItem,
    FeaturesOutput,
    GlossaryTerm,
    JokeOutput,
    MathOutput,
    PrefaceOutput,
    ReferenceDocument,
)


def test_joke_output_structure():
    """JokeOutput should instantiate with joke and category."""
    joke = JokeOutput(joke="Why did the chicken cross the road?", category="classic")
    assert joke.joke == "Why did the chicken cross the road?"
    assert joke.category == "classic"


def test_math_output_structure():
    """MathOutput should instantiate with answer and explanation."""
    math = MathOutput(answer=42.0, explanation="The answer to everything")
    assert math.answer == 42.0
    assert math.explanation == "The answer to everything"


def test_preface_output_minimal():
    """PrefaceOutput should work with only required fields."""
    preface = PrefaceOutput(
        about_this_guide="This is a test guide", audience=["Developers"]
    )
    assert preface.about_this_guide == "This is a test guide"
    assert preface.audience == ["Developers"]
    assert preface.reference_documents == []
    assert preface.glossary == []


def test_preface_output_full():
    """PrefaceOutput should support all optional fields."""
    preface = PrefaceOutput(
        about_this_guide="Full guide description",
        audience=["Developers", "Product Managers"],
        reference_documents=[
            ReferenceDocument(
                name="API Spec",
                url="https://example.com/api",
                description="REST API specification",
            )
        ],
        glossary=[
            GlossaryTerm(term="API", definition="Application Programming Interface")
        ],
    )

    assert len(preface.reference_documents) == 1
    assert preface.reference_documents[0].name == "API Spec"
    assert preface.reference_documents[0].url == "https://example.com/api"

    assert len(preface.glossary) == 1
    assert preface.glossary[0].term == "API"


def test_features_output_structure():
    """FeaturesOutput should contain list of FeatureItem objects."""
    features = FeaturesOutput(
        features=[
            FeatureItem(
                name="User Login",
                description="User authentication",
                category="core",
                priority="must_have",
            ),
            FeatureItem(
                name="Password Reset",
                description="Reset forgotten passwords",
                category="security",
            ),
        ]
    )

    assert len(features.features) == 2
    assert features.features[0].name == "User Login"
    assert features.features[0].priority == "must_have"
    assert features.features[1].priority == "should_have"  # Default value


def test_feature_item_defaults():
    """FeatureItem should use default values for category and priority."""
    feature = FeatureItem(name="Test Feature", description="Test description")
    assert feature.category == "core"
    assert feature.priority == "should_have"


def test_entity_output_minimal():
    """EntityOutput should work with only required fields."""
    entity = EntityOutput(
        name="User",
        description="A system user",
        attributes=[
            EntityAttribute(name="id", type="uuid", required=True),
            EntityAttribute(name="email", type="email"),
        ],
    )

    assert entity.name == "User"
    assert entity.description == "A system user"
    assert len(entity.attributes) == 2
    assert entity.attributes[0].required is True
    assert entity.attributes[1].required is False  # Default
    assert entity.purpose is None
    assert entity.relationships == []
    assert entity.business_rules == []


def test_entity_output_full():
    """EntityOutput should support all optional fields."""
    entity = EntityOutput(
        name="Order",
        description="Customer order",
        purpose="Track customer purchases",
        attributes=[
            EntityAttribute(
                name="order_id",
                type="uuid",
                required=True,
                description="Unique order identifier",
            ),
            EntityAttribute(
                name="total",
                type="number",
                required=True,
                description="Order total amount",
                constraints=AttributeConstraints(minimum=0.0),
            ),
        ],
        relationships=[
            EntityRelationship(
                entity="Customer",
                type="many-to-one",
                required=True,
                description="The customer who placed the order",
            )
        ],
        business_rules=[
            "Total must be positive",
            "Orders cannot be deleted after shipping",
        ],
    )

    assert entity.purpose == "Track customer purchases"
    assert len(entity.relationships) == 1
    assert entity.relationships[0].entity == "Customer"
    assert entity.relationships[0].type == "many-to-one"
    assert len(entity.business_rules) == 2
    assert entity.attributes[1].constraints is not None
    assert entity.attributes[1].constraints.minimum == 0.0


def test_attribute_constraints():
    """AttributeConstraints should support various validation types."""
    constraints = AttributeConstraints(
        minLength=5,
        maxLength=100,
        minimum=0.0,
        maximum=1000.0,
        pattern="^[A-Z]+$",
        enum=["ACTIVE", "INACTIVE"],
    )

    assert constraints.minLength == 5
    assert constraints.maxLength == 100
    assert constraints.minimum == 0.0
    assert constraints.maximum == 1000.0
    assert constraints.pattern == "^[A-Z]+$"
    assert constraints.enum == ["ACTIVE", "INACTIVE"]


def test_reference_document_optional_fields():
    """ReferenceDocument should work with and without optional fields."""
    ref1 = ReferenceDocument(name="Doc 1")
    assert ref1.url is None
    assert ref1.description is None

    ref2 = ReferenceDocument(
        name="Doc 2", url="https://example.com", description="External doc"
    )
    assert ref2.url == "https://example.com"
    assert ref2.description == "External doc"
