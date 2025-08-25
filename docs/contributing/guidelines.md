# Contribution Guidelines

Thank you for considering contributing to Routstr Core! This document provides guidelines and standards for contributing to the project.

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Expected Behavior

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what's best for the community
- Show empathy towards other contributors

## Getting Started

### First Time Contributors

1. **Find an Issue**
   - Look for issues labeled `good first issue`
   - Check `help wanted` labels
   - Ask in discussions if unsure

2. **Claim the Issue**
   - Comment on the issue to claim it
   - Wait for maintainer acknowledgment
   - Ask questions if needed

3. **Fork and Branch**
   ```bash
   git clone https://github.com/YOUR_USERNAME/routstr-core.git
   cd routstr-core
   git checkout -b feat/your-feature-name
   ```

## Code Standards

### Python Style Guide

We follow modern Python practices with strict type checking:

#### Type Annotations

Always use complete type hints:

```python
# ✅ Good - Complete type hints
async def process_payment(
    token: str,
    amount: int,
    mint_url: str | None = None
) -> PaymentResult:
    """Process an eCash payment."""
    pass

# ❌ Bad - Missing or incomplete types
async def process_payment(token, amount, mint_url=None):
    pass
```

#### Modern Python Features

Use Python 3.11+ syntax:

```python
# ✅ Good - Modern union types
def handle_value(data: str | int | None) -> dict[str, Any]:
    pass

# ❌ Bad - Old-style typing
from typing import Union, Dict, Optional
def handle_value(data: Optional[Union[str, int]]) -> Dict[str, Any]:
    pass
```

#### Error Handling

Be explicit with exceptions:

```python
# ✅ Good - Specific exceptions with context
class InsufficientBalanceError(RoustrError):
    """Raised when balance is insufficient for operation."""
    
    def __init__(self, required: int, available: int):
        super().__init__(
            f"Insufficient balance: required {required}, available {available}"
        )
        self.required = required
        self.available = available

# ❌ Bad - Generic exceptions
raise Exception("Not enough balance")
```

### Async/Await Patterns

All I/O operations must be async:

```python
# ✅ Good - Async all the way
async def fetch_user_data(user_id: int) -> UserData:
    async with get_db() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one()

# ❌ Bad - Blocking I/O
def fetch_user_data(user_id: int) -> UserData:
    with get_db() as session:
        return session.query(User).filter_by(id=user_id).first()
```

### Documentation Standards

#### Module Documentation

```python
"""Payment processing module.

This module handles all payment-related operations including:
- Token validation and redemption
- Balance management
- Cost calculation
- Transaction logging
"""
```

#### Function Documentation

```python
async def redeem_token(
    token: str,
    mint_url: str | None = None,
    *,
    verify: bool = True
) -> RedemptionResult:
    """Redeem a Cashu eCash token.
    
    Args:
        token: Base64-encoded Cashu token
        mint_url: Optional mint URL override
        verify: Whether to verify token with mint
        
    Returns:
        RedemptionResult containing amount and token details
        
    Raises:
        TokenInvalidError: If token format is invalid
        TokenExpiredError: If token has expired
        MintConnectionError: If mint is unreachable
        
    Example:
        >>> result = await redeem_token("cashuAey...")
        >>> print(f"Redeemed {result.amount} sats")
    """
```

### Comments

Only add comments for non-obvious logic:

```python
# ✅ Good - Explains complex business logic
# Apply exponential backoff with jitter to prevent thundering herd
# when multiple clients retry simultaneously
delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

# ❌ Bad - States the obvious
# Increment the counter by 1
counter += 1
```

## Testing Requirements

### Test Coverage

- New features must include tests
- Maintain >80% code coverage
- Test edge cases and error conditions

### Test Structure

```python
class TestFeatureName:
    """Test suite for FeatureName functionality."""
    
    async def test_happy_path(self):
        """Test normal operation succeeds."""
        # Arrange
        input_data = create_test_data()
        
        # Act
        result = await function_under_test(input_data)
        
        # Assert
        assert result.success is True
        assert result.value == expected_value
    
    async def test_error_condition(self):
        """Test appropriate error is raised."""
        with pytest.raises(SpecificError) as exc_info:
            await function_under_test(invalid_data)
        
        assert "descriptive message" in str(exc_info.value)
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions or fixes
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### Examples

```bash
# Feature
feat(payment): add support for multi-mint tokens

Implement token validation across multiple trusted mints.
This allows users to pay with tokens from any configured mint.

Closes #123

# Bug fix
fix(proxy): handle streaming timeouts correctly

Previously, long-running streaming requests would timeout after 30s.
This change implements proper timeout handling for streams.

# Documentation
docs(api): update authentication examples

Add examples for bearer token authentication and
update curl commands to match current API.
```

## Pull Request Process

### Before Submitting

1. **Run Quality Checks**
   ```bash
   make format      # Auto-format code
   make lint        # Check style
   make type-check  # Verify types
   make test        # Run all tests
   ```

2. **Update Documentation**
   - Add/update docstrings
   - Update README if needed
   - Add to changelog

3. **Verify Changes**
   - Only include relevant changes
   - No commented code
   - No debug prints
   - No temporary files

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
```

### Review Process

1. **Automated Checks**
   - CI/CD must pass
   - Coverage maintained
   - No linting errors

2. **Peer Review**
   - At least one approval required
   - Address all feedback
   - Resolve all conversations

3. **Final Steps**
   - Squash commits if needed
   - Update branch with main
   - Maintainer merges

## Code Organization

### File Naming

```python
# Use lowercase with underscores
payment_processor.py   # ✅ Good
PaymentProcessor.py    # ❌ Bad
payment-processor.py   # ❌ Bad
```

### Import Organization

```python
# Standard library imports
import asyncio
import json
from datetime import datetime
from typing import Any

# Third-party imports
import httpx
from fastapi import FastAPI, Depends
from sqlmodel import Session, select

# Local imports
from .auth import validate_token
from .models import User, Transaction
from .utils import calculate_hash
```

### Constants

```python
# Module-level constants in UPPER_CASE
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
SUPPORTED_MODELS = ["gpt-3.5-turbo", "gpt-4"]

# Class constants
class PaymentProcessor:
    MIN_AMOUNT = 1
    MAX_AMOUNT = 1_000_000
```

## Best Practices

### Security

1. **Never commit secrets**
   ```python
   # ❌ Bad
   API_KEY = "sk-1234567890"
   
   # ✅ Good
   API_KEY = os.environ.get("API_KEY")
   ```

2. **Validate all inputs**
   ```python
   from pydantic import BaseModel, validator
   
   class PaymentRequest(BaseModel):
       amount: int
       token: str
       
       @validator("amount")
       def validate_amount(cls, v):
           if v <= 0:
               raise ValueError("Amount must be positive")
           return v
   ```

3. **Use constant-time comparisons**
   ```python
   import secrets
   
   # For sensitive comparisons
   if secrets.compare_digest(provided_hash, expected_hash):
       # Authenticated
   ```

### Performance

1. **Use async for I/O**
   ```python
   # Concurrent operations
   results = await asyncio.gather(
       fetch_user(user_id),
       fetch_balance(user_id),
       fetch_transactions(user_id)
   )
   ```

2. **Implement caching**
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=1000)
   def get_model_pricing(model_id: str) -> dict:
       return MODELS.get(model_id, DEFAULT_PRICING)
   ```

3. **Use generators for large data**
   ```python
   async def stream_transactions() -> AsyncGenerator[Transaction, None]:
       async for transaction in get_transactions():
           yield transaction
   ```

### Error Handling

1. **Be specific**
   ```python
   try:
       result = await risky_operation()
   except NetworkError:
       # Handle network issues
       logger.error("Network error during operation")
       raise
   except ValueError as e:
       # Handle value errors
       logger.warning(f"Invalid value: {e}")
       return default_value
   ```

2. **Provide context**
   ```python
   class PaymentError(RoustrError):
       def __init__(self, token: str, reason: str):
           super().__init__(f"Payment failed for token {token[:8]}: {reason}")
           self.token = token
           self.reason = reason
   ```

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking API changes
- MINOR: New features, backwards compatible
- PATCH: Bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run full test suite
4. Create git tag
5. Push tag to trigger release

## Getting Help

### Resources

- [Development Setup](setup.md)
- [Architecture Overview](architecture.md)
- [Testing Guide](testing.md)
- [Database Guide](database.md)

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and ideas
- **Pull Requests**: Code contributions

### Response Times

- Issues: 2-3 business days
- PRs: 2-3 business days
- Security issues: <24 hours

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Routstr Core! 🎉