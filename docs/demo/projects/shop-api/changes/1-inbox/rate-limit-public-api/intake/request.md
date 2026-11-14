# Rate limit the public API

A partner's script hammered `/v1/products` last Friday. Add a per-key rate limit and answer 429 with a `Retry-After` header.
