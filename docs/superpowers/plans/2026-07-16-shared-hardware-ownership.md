# Shared Hardware Ownership

1. Generalize the locked Pico report transaction into a `PicoClient` whose
   operation owns one lock and may rediscover the tty between exchanges.
2. Make generated scheduler firmware report only in response to `r` or a
   command that needs a response; schedule transitions stay silent.
3. Change the web monitor into a periodic client: open, request, publish, and
   close. Commands use the same client; flashing keeps its lock through reset,
   rediscovery, and the first valid report.
4. Keep `report_every` readable for configuration compatibility, but interpret
   it on the host as the collector period and stop baking it into firmware.
5. Verify transport framing, firmware behavior, service polling, command
   responses, and flashing reconnection before running the full suite.
6. Next on the same rolling branch, move camera capture behind the equivalent
   shared per-camera lock so direct CLI capture does not depend on the service.
