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

## Sprout hardware evidence

Validated commit `77cacda` on Sprout with `plamp-web` running:

- Direct report against the old unsolicited-report firmware took 136 ms. A
  malformed stale fragment was logged, then a complete report was returned.
- Firmware apply took 1.75 s including copy, reset, USB rediscovery, `r`, and a
  validated report. The HTTP apply response carried report sequence 3.
- With demand-driven firmware, direct report took 157 ms and a one-second pulse
  response took 153 ms. A later report showed the pulse overlay removed and the
  base schedules still authoritative.
- Direct camera capture took 3.85 s including the configured 1.5 s autofocus
  delay. Web camera capture took 2.41 s through the same camera lock.
- Four concurrent direct report processes all returned complete reports in
  292 ms total. They serialized through the filesystem lock without a daemon or
  permanent serial owner.
- A web `r` transaction immediately published report sequence 5 even though
  background polling was configured for 100 seconds. Service health remained OK.
