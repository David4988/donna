# Protocol

`donna.schema.json` is **generated**. The source of truth is the Pydantic models in
`core/src/donna_core/protocol/messages.py`.

```bash
scripts/gen_protocol.sh      # regenerate schema + desktop/src/protocol/generated.ts
scripts/check_protocol.sh    # what CI runs: fails if the generated files are stale
```

Envelope (v1): `{"v": 1, "type": "...", "turn": "t_1" | null, "ts": "<ISO-8601>", "payload": {}}`

- Client → core: `session.hello` (must be first, carries the token), `user.text`, `user.cancel`
- Core → client: `session.ready`, `turn.started|completed|cancelled|failed`, `assistant.state`,
  `assistant.text`, `tool.request|result|error`, `error`

Adding a message type (e.g. `gesture.detected` later): add the payload + message model to
`messages.py`, add it to `ClientMessage` or `ServerMessage`, then run `scripts/gen_protocol.sh`.
