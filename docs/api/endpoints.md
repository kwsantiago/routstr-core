# API Endpoints

Complete reference for all available endpoints in Routstr Core.

## Chat Completions

### Create Chat Completion

Generate a model response for a conversation.

```http
POST /v1/chat/completions
```

**Request Body:**

```json
{
  "model": "gpt-3.5-turbo",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Hello!"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 150,
  "stream": false
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model ID to use |
| `messages` | array | Yes | - | Conversation messages |
| `temperature` | number | No | 1.0 | Sampling temperature (0-2) |
| `max_tokens` | integer | No | Unlimited | Maximum tokens to generate |
| `stream` | boolean | No | false | Stream response |
| `top_p` | number | No | 1.0 | Nucleus sampling |
| `n` | integer | No | 1 | Number of completions |
| `stop` | string/array | No | null | Stop sequences |
| `presence_penalty` | number | No | 0 | Presence penalty (-2 to 2) |
| `frequency_penalty` | number | No | 0 | Frequency penalty (-2 to 2) |
| `logit_bias` | object | No | null | Token bias |
| `user` | string | No | null | End-user identifier |

**Response:**

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-3.5-turbo",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I assist you today?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 10,
    "total_tokens": 19
  }
}
```

### Streaming Response

When `stream: true`:

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

## Completions

### Create Completion

Generate text completion (legacy endpoint).

```http
POST /v1/completions
```

**Request Body:**

```json
{
  "model": "gpt-3.5-turbo-instruct",
  "prompt": "Once upon a time",
  "max_tokens": 50,
  "temperature": 0.7
}
```

**Response:**

```json
{
  "id": "cmpl-123",
  "object": "text_completion",
  "created": 1677652288,
  "model": "gpt-3.5-turbo-instruct",
  "choices": [{
    "text": " in a faraway land, there lived a brave knight...",
    "index": 0,
    "logprobs": null,
    "finish_reason": "length"
  }],
  "usage": {
    "prompt_tokens": 4,
    "completion_tokens": 50,
    "total_tokens": 54
  }
}
```

## Embeddings

### Create Embeddings

Generate vector representations of text.

```http
POST /v1/embeddings
```

**Request Body:**

```json
{
  "model": "text-embedding-3-small",
  "input": "The quick brown fox jumps over the lazy dog",
  "encoding_format": "float"
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Embedding model ID |
| `input` | string/array | Yes | - | Text(s) to embed |
| `encoding_format` | string | No | "float" | Format: "float" or "base64" |
| `dimensions` | integer | No | Model default | Output dimensions |

**Response:**

```json
{
  "object": "list",
  "data": [{
    "object": "embedding",
    "index": 0,
    "embedding": [0.0023064255, -0.009327292, ...] 
  }],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 9,
    "total_tokens": 9
  }
}
```

## Images

### Create Image

Generate images from text prompts.

```http
POST /v1/images/generations
```

**Request Body:**

```json
{
  "model": "dall-e-3",
  "prompt": "A white siamese cat wearing a space helmet",
  "n": 1,
  "size": "1024x1024",
  "quality": "standard"
}
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model: dall-e-2, dall-e-3 |
| `prompt` | string | Yes | - | Text description |
| `n` | integer | No | 1 | Number of images |
| `size` | string | No | "1024x1024" | Image dimensions |
| `quality` | string | No | "standard" | Quality: standard, hd |
| `style` | string | No | "vivid" | Style: vivid, natural |
| `response_format` | string | No | "url" | Format: url, b64_json |

**Response:**

```json
{
  "created": 1677652288,
  "data": [{
    "url": "https://generated-image-url.com/image.png",
    "revised_prompt": "A white Siamese cat wearing a detailed space helmet..."
  }]
}
```

## Audio

### Create Transcription

Convert audio to text.

```http
POST /v1/audio/transcriptions
Content-Type: multipart/form-data
```

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Audio file (mp3, mp4, mpeg, mpga, m4a, wav, webm) |
| `model` | string | Yes | Model ID (whisper-1) |
| `language` | string | No | Language code (ISO-639-1) |
| `prompt` | string | No | Context prompt |
| `response_format` | string | No | Format: json, text, srt, verbose_json, vtt |
| `temperature` | number | No | Sampling temperature |

**Response:**

```json
{
  "text": "Hello, this is the transcribed audio content."
}
```

### Create Translation

Translate audio to English.

```http
POST /v1/audio/translations
Content-Type: multipart/form-data
```

Same parameters as transcription, but always translates to English.

## Models

### List Models

Get available models and pricing.

```http
GET /v1/models
```

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-3.5-turbo",
      "object": "model",
      "created": 1677652288,
      "owned_by": "openai",
      "pricing": {
        "prompt": 0.0015,
        "completion": 0.002,
        "prompt_sats_per_1k": 3,
        "completion_sats_per_1k": 4
      }
    },
    {
      "id": "gpt-4",
      "object": "model",
      "created": 1677652288,
      "owned_by": "openai",
      "pricing": {
        "prompt": 0.03,
        "completion": 0.06,
        "prompt_sats_per_1k": 60,
        "completion_sats_per_1k": 120
      }
    }
  ]
}
```

### Get Model

Get details for a specific model.

```http
GET /v1/models/{model_id}
```

**Response:**

```json
{
  "id": "gpt-3.5-turbo",
  "object": "model",
  "created": 1677652288,
  "owned_by": "openai",
  "permission": [{
    "allow_create_engine": false,
    "allow_sampling": true,
    "allow_logprobs": true,
    "allow_search_indices": false,
    "allow_view": true,
    "allow_fine_tuning": false
  }],
  "root": "gpt-3.5-turbo",
  "parent": null,
  "pricing": {
    "prompt": 0.0015,
    "completion": 0.002,
    "image": 0,
    "request": 0
  }
}
```

## Wallet Management

### Create API Key

Create a new API key with eCash deposit.

```http
POST /v1/wallet/create
```

**Request Body:**

```json
{
  "cashu_token": "cashuAeyJ0b2tlbiI6W3...",
  "name": "My API Key",
  "expires_at": "2024-12-31T23:59:59Z",
  "refund_npub": "npub1..."
}
```

**Response:**

```json
{
  "api_key": "rstr_1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p",
  "balance": 10000,
  "created_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-12-31T23:59:59Z"
}
```

### Check Balance

Get current balance and usage stats.

```http
GET /v1/wallet/balance
Authorization: Bearer {api_key}
```

**Response:**

```json
{
  "balance": 8546,
  "total_deposited": 10000,
  "total_spent": 1454,
  "last_used": "2024-01-01T12:34:56Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Top Up Balance

Add funds to existing API key.

```http
POST /v1/wallet/topup
Authorization: Bearer {api_key}
```

**Request Body:**

```json
{
  "cashu_token": "cashuAeyJ0b2tlbiI6W3..."
}
```

**Response:**

```json
{
  "old_balance": 8546,
  "added_amount": 5000,
  "new_balance": 13546
}
```

### Withdraw Balance

Generate eCash token from balance.

```http
POST /v1/wallet/withdraw
Authorization: Bearer {api_key}
```

**Request Body:**

```json
{
  "amount": 5000,
  "mint_url": "https://mint.minibits.cash/Bitcoin"
}
```

**Response:**

```json
{
  "cashu_token": "cashuAeyJ0b2tlbiI6W3...",
  "amount": 5000,
  "mint_url": "https://mint.minibits.cash/Bitcoin"
}
```

## Node Information

### Get Node Info

Get public information about the Routstr node.

```http
GET /v1/info
```

**Response:**

```json
{
  "name": "Lightning AI Gateway",
  "description": "Fast AI API access with Bitcoin payments",
  "version": "0.1.1b",
  "npub": "npub1abc...",
  "mints": [
    "https://mint.minibits.cash/Bitcoin",
    "https://testnut.cashu.space"
  ],
  "http_url": "https://api.lightning-ai.com",
  "onion_url": "http://lightningai.onion",
  "models": {
    "gpt-3.5-turbo": {
      "name": "GPT-3.5 Turbo",
      "pricing": {
        "prompt": 0.0015,
        "completion": 0.002
      }
    }
  }
}
```

## Discovery

### List Providers

Discover Routstr providers from Nostr relays.

```http
GET /v1/providers
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `relay` | string | Specific relay URL |
| `limit` | integer | Maximum results |

**Response:**

```json
{
  "providers": [
    {
      "name": "Fast AI Node",
      "npub": "npub1xyz...",
      "url": "https://fast-ai.com",
      "description": "Low latency AI API access",
      "models": ["gpt-3.5-turbo", "gpt-4"],
      "pricing": {
        "gpt-3.5-turbo": {
          "prompt_sats_per_1k": 3,
          "completion_sats_per_1k": 4
        }
      }
    }
  ]
}
```

## Admin Endpoints

### Admin Dashboard

Access the web-based admin interface.

```http
GET /admin/
```

Requires password authentication via web form.

### Admin API

Protected endpoints for node management.

```http
POST /admin/api/withdraw
X-Admin-Password: {admin_password}
```

**Request Body:**

```json
{
  "api_key": "rstr_123...",
  "amount": 5000
}
```

## Health & Status

### Health Check

Monitor service health.

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.1b",
  "timestamp": "2024-01-01T00:00:00Z",
  "checks": {
    "database": "ok",
    "upstream": "ok",
    "mint": "ok"
  }
}
```

### Metrics

Get service metrics.

```http
GET /metrics
```

Returns Prometheus-compatible metrics.

## Deprecated Endpoints

### Legacy Balance Check

```http
GET /v1/balance
Authorization: Bearer {api_key}
```

⚠️ **Deprecated**: Use `/v1/wallet/balance` instead.

## Rate Limits

All endpoints are subject to rate limiting:

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| AI Generation | 100/min | 1 minute |
| Wallet Operations | 10/min | 1 minute |
| Info/Discovery | 60/min | 1 minute |

Rate limit information is included in response headers.

## Next Steps

- [Errors](errors.md) - Error handling reference
- [Authentication](authentication.md) - Auth details
- [Examples](../user-guide/using-api.md) - Code examples