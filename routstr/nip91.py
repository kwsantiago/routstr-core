#!/usr/bin/env python3
"""
NIP-91: Routstr Provider Discoverability Implementation
Automatically announces this Routstr proxy instance to Nostr relays.
"""

import asyncio
import hashlib
import json
import os
import time
from typing import Any, cast

import secp256k1
import websockets

from .core import get_logger
from .payment.models import MODELS

logger = get_logger(__name__)


def get_app_version() -> str | None:
    try:
        from .core.main import __version__ as imported_version

        return imported_version
    except Exception:
        return None


def _schnorr_sign_event_id(
    private_key: secp256k1.PrivateKey, event_id_hex: str
) -> bytes:
    """Return 64-byte Schnorr signature over the 32-byte event id."""
    msg32 = bytes.fromhex(event_id_hex)

    # Try common API variants exposed by python-secp256k1 bindings
    method = getattr(private_key, "schnorr_sign", None)
    if callable(method):
        try:
            sig = method(msg32)
            if isinstance(sig, bytes) and len(sig) == 64:
                return sig
        except TypeError:
            pass
        try:
            sig = method(msg32, None, True)
            if isinstance(sig, bytes) and len(sig) == 64:
                return sig
        except TypeError:
            pass

    method32 = getattr(private_key, "schnorr_sign32", None)
    if callable(method32):
        sig = method32(msg32)
        if isinstance(sig, bytes) and len(sig) == 64:
            return sig

    raise RuntimeError("Schnorr signing not available in secp256k1 binding")


def nsec_to_keypair(nsec: str) -> tuple[str, str] | None:
    """
    Convert a Nostr private key (nsec) to a keypair (privkey_hex, pubkey_hex).

    Args:
        nsec: Nostr private key in nsec format or hex format

    Returns:
        Tuple of (private_key_hex, public_key_hex) or None if invalid
    """
    try:
        # Handle nsec format
        if nsec.startswith("nsec"):
            # Simple bech32 decode - for production use a proper library
            # For now, we'll assume hex format is passed
            logger.warning("nsec format not yet implemented, please use hex format")
            return None

        # Assume hex format
        if len(nsec) != 64:
            logger.error(f"Invalid private key length: {len(nsec)}")
            return None

        private_key = secp256k1.PrivateKey(bytes.fromhex(nsec))
        pubkey_obj = cast(secp256k1.PublicKey, private_key.pubkey)
        public_key = pubkey_obj.serialize(compressed=True)[
            1:
        ]  # Remove 0x02/0x03 prefix

        return (nsec, public_key.hex())
    except Exception as e:
        logger.error(f"Failed to convert nsec to keypair: {e}")
        return None


def create_nip91_event(
    private_key_hex: str,
    provider_id: str,
    endpoint_urls: list[str],
    supported_models: list[str],
    mint_url: str | None = None,
    version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a NIP-91 compliant provider announcement event (kind:38421).

    Args:
        private_key_hex: 32-byte hex private key for signing
        provider_id: Unique identifier for this provider (d tag)
        endpoint_urls: List of URLs to connect to the provider
        supported_models: List of supported AI model IDs
        mint_url: Optional ecash mint URL for payments
        version: Provider software version
        metadata: Optional metadata dictionary (name, picture, about, etc.)

    Returns:
        Complete signed nostr event ready for publishing
    """
    # Convert hex private key to secp256k1 PrivateKey object
    private_key = secp256k1.PrivateKey(bytes.fromhex(private_key_hex))
    pubkey_obj = cast(secp256k1.PublicKey, private_key.pubkey)
    public_key = pubkey_obj.serialize(compressed=True)[1:]  # Remove 0x02/0x03 prefix

    # Build tags according to NIP-91
    tags = [
        ["d", provider_id],  # Unique identifier
    ]

    # Add URLs
    for url in endpoint_urls:
        tags.append(["u", url])

    # Add models as a single tag with multiple values
    # if supported_models:
    #     tags.append(["models"] + supported_models)

    # Add optional tags
    if mint_url:
        tags.append(["mint", mint_url])
    if version:
        tags.append(["version", version])

    # Add model capabilities if detailed info available
    # for model in MODELS:
    #     if model.id in supported_models:
    #         capabilities = []

    #         # Add max_tokens from context_length
    #         if model.context_length:
    #             capabilities.append(f"max_tokens:{model.context_length}")

    #         # Check if model supports vision (simplified check)
    #         if any(modal in ["image"] for modal in model.architecture.input_modalities):
    #             capabilities.append("vision:true")
    #         else:
    #             capabilities.append("vision:false")

    #         # Check if model supports tools (simplified - most modern models do)
    #         if "gpt" in model.id or "claude" in model.id or "llama" in model.id:
    #             capabilities.append("tools:true")
    #         else:
    #             capabilities.append("tools:false")

    #         if capabilities:
    #             tags.append(["model-cap", model.id, ",".join(capabilities)])

    # Content is optional metadata as JSON string
    content = ""
    if metadata:
        content = json.dumps(metadata, separators=(",", ":"))

    # Create the event structure
    created_at = int(time.time())
    event_data = [
        0,  # Reserved field
        public_key.hex(),  # Public key as hex
        created_at,  # Unix timestamp
        38421,  # Kind for NIP-91 Provider Announcements
        tags,  # Tags array
        content,  # Content (metadata)
    ]

    # Serialize event data for hashing
    event_json = json.dumps(event_data, separators=(",", ":"), ensure_ascii=False)

    # Calculate event ID (SHA256 hash)
    event_id = hashlib.sha256(event_json.encode("utf-8")).hexdigest()

    # Sign the event ID using Schnorr (BIP-340)
    sig_hex = _schnorr_sign_event_id(private_key, event_id).hex()

    # Create the final event
    event = {
        "id": event_id,
        "pubkey": public_key.hex(),
        "created_at": created_at,
        "kind": 38421,
        "tags": tags,
        "content": content,
        "sig": sig_hex,
    }

    return event


def _get_tag_values(event: dict[str, Any], key: str) -> list[str]:
    tags = event.get("tags", [])
    values: list[str] = []
    for tag in tags:
        if isinstance(tag, list) and tag and tag[0] == key and len(tag) >= 2:
            values.append(tag[1])
    return values


def _get_single_tag_value(event: dict[str, Any], key: str) -> str | None:
    values = _get_tag_values(event, key)
    return values[0] if values else None


def _parse_content_json(content: str) -> dict[str, Any]:
    if not content:
        return {}
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def events_semantically_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("kind") != b.get("kind"):
        return False

    if _get_single_tag_value(a, "d") != _get_single_tag_value(b, "d"):
        return False

    urls_a = set(_get_tag_values(a, "u"))
    urls_b = set(_get_tag_values(b, "u"))
    if urls_a != urls_b:
        return False

    if _get_single_tag_value(a, "mint") != _get_single_tag_value(b, "mint"):
        return False

    if _get_single_tag_value(a, "version") != _get_single_tag_value(b, "version"):
        return False

    content_a = _parse_content_json(cast(str, a.get("content", "")))
    content_b = _parse_content_json(cast(str, b.get("content", "")))
    if content_a != content_b:
        return False

    return True


async def query_nip91_events(
    relay_url: str,
    pubkey: str,
    provider_id: str | None = None,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """
    Query a Nostr relay for NIP-91 provider announcements (kind:38421).

    Args:
        relay_url: WebSocket URL of the nostr relay
        pubkey: Public key to filter by
        timeout: Connection timeout in seconds

    Returns:
        List of NIP-91 events from the given pubkey
    """
    events = []

    # Build filter for NIP-91 events from specific pubkey
    filter_obj: dict[str, Any] = {
        "kinds": [38421],
        "authors": [pubkey],
        "limit": 10,
    }
    if provider_id:
        filter_obj["#d"] = [provider_id]

    sub_id = f"nip91_{int(time.time())}"
    req_message = json.dumps(["REQ", sub_id, filter_obj])

    try:
        async with websockets.connect(relay_url, open_timeout=timeout) as websocket:
            logger.debug(f"Querying {relay_url} for existing NIP-91 events")
            await websocket.send(req_message)

            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5)
                    data = json.loads(message)

                    if data[0] == "EVENT" and data[1] == sub_id:
                        event = data[2]
                        logger.debug(f"Found existing NIP-91 event: {event['id']}")
                        events.append(event)
                    elif data[0] == "EOSE" and data[1] == sub_id:
                        logger.debug("Received EOSE message")
                        break
                    elif data[0] == "NOTICE":
                        logger.warning(f"Relay notice: {data[1]}")

                except asyncio.TimeoutError:
                    logger.debug("Timeout waiting for relay response")
                    break
                except json.JSONDecodeError:
                    logger.debug("Failed to decode relay message as JSON")
                    continue

            await websocket.send(json.dumps(["CLOSE", sub_id]))

    except Exception as e:
        logger.error(f"Failed to query relay {relay_url}: {e}")

    return events


def discover_onion_url_from_tor(base_dir: str = "/var/lib/tor") -> str | None:
    """Discover onion URL by reading Tor hidden service hostname files.

    Tries common paths first, then scans recursively for any 'hostname' file.
    Returns an http URL like 'http://<host>.onion' if found.
    """
    common_candidates = [
        os.path.join(base_dir, "hs", "router", "hostname"),
        os.path.join(base_dir, "hs", "ROUTER", "hostname"),
        os.path.join(base_dir, "hidden_service", "hostname"),
    ]

    for candidate in common_candidates:
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                host = f.readline().strip()
            if host and host.endswith(".onion"):
                return f"http://{host}"
        except Exception:
            pass

    try:
        for root, _dirs, files in os.walk(base_dir):
            if "hostname" in files:
                path = os.path.join(root, "hostname")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        host = f.readline().strip()
                    if host and host.endswith(".onion"):
                        return f"http://{host}"
                except Exception:
                    continue
    except Exception:
        pass

    return None


async def _determine_provider_id(public_key_hex: str, relay_urls: list[str]) -> str:
    explicit = os.getenv("PROVIDER_ID") or os.getenv("NIP91_PROVIDER_ID")
    if explicit:
        logger.info(f"Using configured provider_id from env: {explicit}")
        return explicit

    latest_event: dict[str, Any] | None = None
    latest_ts = -1
    for relay_url in relay_urls:
        try:
            events = await query_nip91_events(relay_url, public_key_hex, None)
            for ev in events:
                ts = int(ev.get("created_at", 0))
                if ts > latest_ts:
                    latest_event = ev
                    latest_ts = ts
        except Exception:
            continue

    existing_d = _get_single_tag_value(latest_event, "d") if latest_event else None
    if existing_d:
        logger.info(f"Reusing existing provider_id from relay: {existing_d}")
        return existing_d

    fallback = public_key_hex[:12]
    logger.info(f"No existing provider_id found; using fallback: {fallback}")
    return fallback


async def publish_to_relay(
    relay_url: str,
    event: dict[str, Any],
    timeout: int = 30,
) -> bool:
    """
    Publish a NIP-91 event to a nostr relay.

    Args:
        relay_url: WebSocket URL of the nostr relay
        event: Complete signed nostr event to publish
        timeout: Connection timeout in seconds

    Returns:
        True if successfully published, False otherwise
    """
    try:
        async with websockets.connect(relay_url, open_timeout=timeout) as websocket:
            # Send EVENT message
            event_message = json.dumps(["EVENT", event])
            await websocket.send(event_message)
            logger.debug(f"Sent NIP-91 event {event['id']} to {relay_url}")

            # Wait for OK response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=50)
                data = json.loads(response)
                logger.debug(f"Relay response: {data}")

                if data[0] == "OK" and data[1] == event["id"]:
                    if data[2]:  # True means accepted
                        logger.info(f"Event accepted by {relay_url}")
                        return True
                    else:
                        logger.warning(f"Event rejected by {relay_url}")
                        return False
                elif data[0] == "NOTICE":
                    logger.warning(f"Relay notice from {relay_url}: {data[1]}")
                    return False
                else:
                    logger.debug(f"Unexpected response from {relay_url}: {data}")
                    return False

            except asyncio.TimeoutError:
                logger.warning(f"No response from {relay_url} within timeout")
                return False

    except Exception as e:
        logger.error(f"Failed to publish to {relay_url}: {e}")
        return False


async def announce_provider() -> None:
    """
    Background task to announce this Routstr provider to Nostr relays.
    Checks for existing announcements and creates new ones if needed.
    """
    # Check for NSEC in environment (use NSEC only)
    nsec = os.getenv("NSEC")
    if not nsec:
        logger.info("Nostr private key not found (NSEC), skipping NIP-91 announcement")
        return

    # Convert NSEC to keypair
    keypair = nsec_to_keypair(nsec)
    if not keypair:
        logger.error("Failed to parse NSEC, skipping NIP-91 announcement")
        return

    private_key_hex, public_key_hex = keypair
    logger.info(f"Using Nostr pubkey: {public_key_hex}")

    # Configure relays first (RELAYS only)
    relay_urls_env = os.getenv("RELAYS") or ""
    logger.debug(f"Configured relays: {relay_urls_env}")
    relay_urls = [url.strip() for url in relay_urls_env.split(",") if url.strip()]
    if not relay_urls:
        relay_urls = [
            "wss://relay.nostr.band",
            "wss://relay.damus.io",
            "wss://nos.lol",
        ]

    # Determine a stable provider_id
    provider_id = await _determine_provider_id(public_key_hex, relay_urls)
    logger.info(f"Using provider_id: {provider_id}")

    # Core settings only (no ROUTSTR_* vars)
    base_url = os.getenv("HTTP_URL")
    onion_url = os.getenv("ONION_URL")
    if not onion_url:
        discovered = discover_onion_url_from_tor()
        if discovered:
            onion_url = discovered
            logger.info(f"Discovered onion URL via Tor volume: {onion_url}")
    provider_name = os.getenv("NAME", "Routstr Proxy")
    provider_about = os.getenv("DESCRIPTION", "Privacy-preserving AI proxy via Nostr")
    # Mint URL optional: first CASHU_MINTS entry if available
    cashu_mints = [
        m.strip() for m in os.getenv("CASHU_MINTS", "").split(",") if m.strip()
    ]
    mint_url = cashu_mints[0] if cashu_mints else None

    # Build endpoint URLs (skip defaults like localhost)
    endpoint_urls: list[str] = []
    if base_url and base_url.strip() and base_url.strip() != "http://localhost:8000":
        endpoint_urls.append(base_url.strip())
    if onion_url and onion_url.strip():
        ou = onion_url.strip()
        if ou.endswith(".onion") and not (
            ou.startswith("http://") or ou.startswith("https://")
        ):
            ou = f"http://{ou}"
        endpoint_urls.append(ou)

    if not endpoint_urls:
        logger.warning(
            "No valid endpoints configured (HTTP_URL/ONION_URL). Skipping NIP-91 publish."
        )
        return

    # Get supported models
    supported_models = [model.id for model in MODELS]
    if not supported_models:
        logger.warning("No models loaded, will announce with empty model list")
        supported_models = []

    # Build metadata
    metadata = {
        "name": provider_name,
        "about": provider_about,
    }

    # Create the candidate event that we would publish
    version_str = get_app_version()
    candidate_event = create_nip91_event(
        private_key_hex=private_key_hex,
        provider_id=provider_id,
        endpoint_urls=endpoint_urls,
        supported_models=supported_models,
        mint_url=mint_url,
        version=version_str,
        metadata=metadata,
    )

    # Fetch existing events for this provider_id
    existing_events: list[dict[str, Any]] = []
    for relay_url in relay_urls:
        events = await query_nip91_events(relay_url, public_key_hex, provider_id)
        existing_events.extend(events)

    # Decide whether to publish: publish if none exist or any differ from candidate
    found_any = len(existing_events) > 0
    all_match = found_any and all(
        events_semantically_equal(ev, candidate_event) for ev in existing_events
    )

    if not all_match:
        logger.debug(
            "No matching NIP-91 announcement found or differences detected; publishing update"
        )
        success_count = 0
        for relay_url in relay_urls:
            if await publish_to_relay(relay_url, candidate_event):
                success_count += 1
        logger.info(
            f"Published NIP-91 announcement to {success_count}/{len(relay_urls)} relays"
        )
    else:
        logger.debug(
            "Matching NIP-91 announcement already present; skipping publish on startup"
        )

    # Re-announce periodically (every 24 hours)
    announcement_interval = int(
        os.getenv("NIP91_ANNOUNCEMENT_INTERVAL", str(24 * 60 * 60))
    )

    while True:
        try:
            await asyncio.sleep(announcement_interval)

            # Build fresh candidate event for comparison
            version_str = get_app_version()
            candidate_event = create_nip91_event(
                private_key_hex=private_key_hex,
                provider_id=provider_id,
                endpoint_urls=endpoint_urls,
                supported_models=[model.id for model in MODELS],
                mint_url=mint_url,
                version=version_str,
                metadata=metadata,
            )

            # Fetch existing events for this provider_id
            existing_events = []
            for relay_url in relay_urls:
                events = await query_nip91_events(
                    relay_url, public_key_hex, provider_id
                )
                existing_events.extend(events)

            found_any = len(existing_events) > 0
            all_match = found_any and all(
                events_semantically_equal(ev, candidate_event) for ev in existing_events
            )

            if all_match:
                logger.debug(
                    "Matching NIP-91 announcement already present; skipping periodic re-announce"
                )
                continue

            logger.debug(
                f"Re-announcing provider due to differences or absence: {candidate_event['id']}"
            )
            for relay_url in relay_urls:
                await publish_to_relay(relay_url, candidate_event)

        except asyncio.CancelledError:
            logger.info("NIP-91 announcement task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in NIP-91 announcement loop: {e}")
            # Continue running despite errors
