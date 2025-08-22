"""Test to verify reserved balance never goes negative."""

import asyncio

import pytest
from httpx import AsyncClient

from routstr.core.db import ApiKey, create_session


@pytest.mark.asyncio
async def test_reserved_balance_never_negative(test_client: AsyncClient) -> None:
    """Test that reserved balance never goes negative under various conditions."""

    # Create a test API key with limited balance
    async with create_session() as session:
        test_key = ApiKey(
            hashed_key="test_reserved_balance_key",
            balance=1000,  # 1 sat
            reserved_balance=0,
        )
        session.add(test_key)
        await session.commit()

    bearer_token = "sk-test_reserved_balance_key"
    headers = {"Authorization": f"Bearer {bearer_token}"}

    # Test 1: Make a request that will fail upstream
    # This should reserve funds and then revert them
    await test_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "invalid-model-that-will-fail",
            "messages": [{"role": "user", "content": "test"}],
        },
    )

    # Check reserved balance after failed request
    async with create_session() as session:
        key = await session.get(ApiKey, "test_reserved_balance_key")
        assert key is not None
        assert key.reserved_balance >= 0, (
            f"Reserved balance went negative: {key.reserved_balance}"
        )
        assert key.balance == 1000, (
            "Balance should remain unchanged after failed request"
        )

    # Test 2: Simulate concurrent failed requests
    # This tests the race condition protection
    async def make_failing_request() -> None:
        try:
            await test_client.post(
                "/v1/chat/completions",
                headers=headers,
                json={
                    "model": "invalid-model",
                    "messages": [{"role": "user", "content": "test"}],
                },
            )
        except Exception:
            pass  # Expected to fail

    # Run multiple concurrent requests
    await asyncio.gather(*[make_failing_request() for _ in range(5)])

    # Check final state
    async with create_session() as session:
        key = await session.get(ApiKey, "test_reserved_balance_key")
        assert key is not None
        assert key.reserved_balance >= 0, (
            f"Reserved balance went negative after concurrent requests: {key.reserved_balance}"
        )
        print(f"Final state - Balance: {key.balance}, Reserved: {key.reserved_balance}")


@pytest.mark.asyncio
async def test_reserved_balance_with_successful_requests(
    test_client: AsyncClient,
) -> None:
    """Test reserved balance handling with successful requests."""

    # Create a test API key with more balance
    async with create_session() as session:
        test_key = ApiKey(
            hashed_key="test_successful_key",
            balance=100000,  # 100 sats
            reserved_balance=0,
        )
        session.add(test_key)
        await session.commit()

    bearer_token = "sk-test_successful_key"
    headers = {"Authorization": f"Bearer {bearer_token}"}

    # Make a valid request (assuming you have a mock or test endpoint)
    # This test might need adjustment based on your test setup
    await test_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o-mini",  # Or whatever model is available in test
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10,
        },
    )

    # Check that reserved balance was properly adjusted
    async with create_session() as session:
        key = await session.get(ApiKey, "test_successful_key")
        assert key is not None
        assert key.reserved_balance >= 0, (
            f"Reserved balance went negative: {key.reserved_balance}"
        )
        # After successful request, some balance should have been spent
        assert key.total_spent > 0, "No cost was recorded"
        assert key.balance < 100000, "Balance should decrease after successful request"
        print(
            f"After successful request - Balance: {key.balance}, Reserved: {key.reserved_balance}, Spent: {key.total_spent}"
        )


@pytest.mark.asyncio
async def test_insufficient_reserved_balance_for_revert() -> None:
    """Test that revert_pay_for_request properly handles insufficient reserved balance."""
    from routstr.auth import revert_pay_for_request

    async with create_session() as session:
        # Create key with zero reserved balance
        test_key = ApiKey(
            hashed_key="test_revert_key",
            balance=1000,
            reserved_balance=0,
        )
        session.add(test_key)
        await session.commit()

        # Try to revert more than available
        with pytest.raises(Exception):  # Should raise HTTPException
            await revert_pay_for_request(test_key, session, 100)

        # Verify reserved balance didn't go negative
        await session.refresh(test_key)
        assert test_key.reserved_balance == 0, (
            f"Reserved balance went negative: {test_key.reserved_balance}"
        )
