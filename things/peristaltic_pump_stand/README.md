# Peristaltic pump stand

This is a small U-stand for one or more peristaltic pumps. The horizontal
plate has a 29 mm motor opening and an M3 mounting pair on the same centre
line, initially measured at 48.5 mm apart. Two end panels lift the plate 55 mm
above the table; their tabs locate into slots in the plate.

Generate the printable pieces separately:

```bash
plamp cad generate peristaltic_pump_stand --set plate
plamp cad generate peristaltic_pump_stand --set legs
```

The default is two pump stations at 62 mm centre-to-centre. Change the count
or `pump_spacing` from the command line when the pump layout changes:

```bash
plamp cad generate peristaltic_pump_stand --set plate \
  --define 'pump_count=2' --define 'pump_spacing=62'
```

The 29 mm motor opening and 48.5 mm M3 spacing are initial measurements.
Print a short plate fit check before committing to a long production plate.
The two 5.5 mm M5 table-mounting holes sit in round ears, centred on the
plate centreline just outside the end-panel legs.

For a visual check only:

```bash
plamp cad generate peristaltic_pump_stand --set assembly
```
