# Redzed

Redzed is an asyncio-based library for building small automated systems,
i.e. systems that control outputs according to input values,
system’s internal state, date and time. Redzed was written in Python.
It is free and open source.

Included are pre-defined logic blocks for general use. There are memory cells,
timers, programmable finite-state machines, outputs and many more.
Blocks have outputs and react to events. Blocks are complemented by triggers
running user-supplied functions when certain outputs change. Triggered functions
evaluate outputs, make decisions and can send events to other blocks.

The mutual interaction of blocks and triggers allows to build modular
automated systems of small to middle complexity.

What is not included:
The application code must connect the system with outside world.

## Documentation

Please read the [online documentation](https://redzed.readthedocs.io/en/latest/)
for more information.

### Note:

Redzed is intended to replace Edzed (an older library from the same author).
It has the same capabilities, but is based on simpler concepts and that's why
it is easier to learn and to use.
