# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | yes       |
| < 1.1   | no        |

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue.

- Email: adityakumar14072003@gmail.com
- Or use GitHub's private vulnerability reporting on this repository

Include the affected endpoint, how to reproduce the issue and the impact you
believe it has. You can expect an acknowledgement within a few days and a
fix or mitigation plan once the report is confirmed.

## What is in scope

- Authentication bypass or privilege escalation
- Cross-tenant access to another user's links or analytics
- Injection into the database, the Redis queue or the rendered templates
- Denial of service through the rate limiter or the redirect path
- Leaking secrets, tokens or other users' data

## Security measures already in place

- **Passwords** are hashed with bcrypt; plaintext is never stored or logged.
- **JWTs** are signed with HS256 and verified with the algorithm pinned
  server-side, so a token cannot choose its own verification algorithm.
- **Secrets** have no usable defaults in production: the process refuses to
  start while `SECRET_KEY` or `JWT_SECRET_KEY` still hold their placeholder
  values, and `ENVIRONMENT=production` enforces it.
- **CORS** uses an explicit origin allowlist. There is no wildcard origin
  combined with credentials.
- **Rate limiting** is enforced per client IP with an atomic Redis counter
  and falls back to an in-process limiter when Redis is unavailable.
- **Input validation** rejects custom aliases that are too long, contain
  illegal characters or shadow an application route.
- **Ownership** is enforced on every link and analytics query, so one user
  cannot read or modify another user's data.
- **Analytics failures never break a redirect**: a failed click write is
  rolled back and logged, not surfaced to the visitor.
- **Dependencies** are pinned and audited in CI with `pip-audit`.
