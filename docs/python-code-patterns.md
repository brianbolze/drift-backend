## Pydantic Schema Patterns

### Localized Fields Class

Each schema file defines its own `Fields` class for domain-specific field definitions. This keeps field documentation and validation co-located with the schemas that use them. Be sure to include at least one example in the field definitions, as it helps with the API documentation readability.

```python
# src/schemas/tenant.py --- just a reference example
from pydantic import Field
from .base import BaseSchema, UUIDStr, ISODateTime

class Fields:
    """Field definitions for Tenant schemas."""

    @staticmethod
    def id():
        return Field(
            ...,
            description="Unique identifier for the tenant",
            examples=["123e4567-e89b-12d3-a456-426614174000"],
        )

    @staticmethod
    def slug():
        return Field(
            ...,
            min_length=1,
            max_length=63,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
            description="URL-safe tenant identifier",
            examples=["acme-corp", "engineering-team"],
        )

    @staticmethod
    def name():
        return Field(
            ...,
            min_length=1,
            max_length=255,
            description="Display name for the tenant",
            examples=["Acme Corporation"],
        )

class Tenant(BaseSchema):
    """Tenant schema for API responses."""

    id: UUIDStr = Fields.id()
    slug: str = Fields.slug()
    name: str = Fields.name()
    # ... other fields

class TenantCreate(BaseSchema):
    """Schema for creating a new tenant."""

    name: str = Fields.name()
    slug: Optional[str] = Field(
        None,
        description="URL-safe identifier (auto-generated if not provided)",
        examples=["acme-corp", "engineering-team"],
    )
```

**Benefits:**

- DRY: Reuse field definitions across Create/Update/Response schemas
- Co-located: Fields and schemas in same file (no jumping around)
- Customizable: Each domain has its own descriptions/examples
- Better API docs: Automatic OpenAPI documentation with examples

### Base Schema Configuration

`BaseSchema` provides common Pydantic config without field inheritance:

```python
# src/schemas/base.py
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,  # ORM mode for SQLAlchemy
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )
```

**No field inheritance** - Each schema explicitly declares its fields for clarity.

### Custom Serialized Types

For consistent JSON serialization:

```python
# UUID serializes to string
UUIDStr = Annotated[UUID, PlainSerializer(lambda v: str(v), when_used="json")]

# DateTime serializes to ISO 8601
ISODateTime = Annotated[datetime, PlainSerializer(lambda v: v.isoformat(), when_used="json")]

# Usage
class Tenant(BaseSchema):
    id: UUIDStr  # Serializes as "123e4567-..." in JSON
    created_time: ISODateTime  # Serializes as "2024-01-15T10:30:00Z"
```

## Database Model Patterns

### Server-Side Defaults

```python
class Base(DeclarativeBase):
    id = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"))
    created_time = Column(DateTime(timezone=True), server_default=func.now())
```

### Property-Based Validation

```python
class User(Base):
    status: Mapped[UserStatus]
    email_verified: Mapped[bool]

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.email_verified
```