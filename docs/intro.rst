.. currentmodule:: redzed

=================
Welcome to Redzed
=================

What it can do?
===============

Redzed is a Python asyncio-based library for building automated systems,
i.e. applications that control outputs according to input values,
system’s internal state, date and time. It is free and open source.

The logic of the automated system is defined by a so-called **circuit**
consisting of circuit components. This modularity allows to modify
the logic easily. Several components for general use are already included
making the development more productive.

A circuit contains two major types of components:

1. **Logic blocks** (or just blocks) with outputs. Logic blocks process
   incoming events and adjust their outputs according to their specific function.
2. **Triggers** activated by output changes. Triggered functions evaluate outputs
   of logic blocks, make decisions and can send events to other blocks.

The mutual interaction of blocks and triggers allows to build
automated systems of small to middle complexity. The system represented
by its circuit is made operational using Redzed's **runner**.

Being a library means there is no function out of the box.
In order to create an application, the developer needs to design a circuit
and to connect its inputs with data sources and its outputs
with controlled devices.


Example programs
================

This tiny program prints "ding/dong" (the bell sound) in 1 second pace::

  import asyncio
  import redzed

  redzed.Timer('clk', comment="clock generator", t_period=1.0)

  @redzed.triggered
  def output_print(clk):
      print('     ..dong!' if clk else ' ding..')

  if __name__ == '__main__':
      print('Press ctrl-C to stop\n')
      try:
          asyncio.run(redzed.run())
      except KeyboardInterrupt:
          # prevent a traceback being printed
          raise SystemExit(" Exit on ctrl-c") from None


The circuit consists of one :class:`Timer` type logical block
named ``'clk'`` and one :class:`Trigger` reacting to Timer's output changes.
The Trigger invokes the :func:`!output_print` function.

----

The second simple program simulates a thermostat. A mocked up sensor
is polled in regular intervals and the temperature readout is compared
with heating and cooling thresholds.

In this circuit there are: two blocks (:class:`DataPoll`, :class:`OutputFunc`),
one :class:`Trigger` and few custom functions (for input, evaluation, output)::

  import asyncio
  import random
  import redzed

  def measure_temperature():
      """Fake room thermometer (Celsius scale)."""
      t = random.uniform(18.0, 26.0)
      print(f"\nT={t:.1f}")
      return t

  temp = redzed.DataPoll(
     'temp', comment='thermometer', func=measure_temperature, interval=1.2)

  @redzed.triggered
  def compare(temp):
      if temp < 22.0:
          heater.event('put', True)
      elif temp > 24.0:
          heater.event('put', False)
      else:
          print(" OK")

  def output(evalue):
      if evalue:
          print(" below 22 °C, heating")
      else:
          print(" above 24 °C, COOLING")

  heater = redzed.OutputFunc('heater', func=output)

  if __name__ == '__main__':
      print('Press ctrl-C to stop\n')
      try:
          asyncio.run(redzed.run())
      except KeyboardInterrupt:
          # prevent a traceback being printed
          raise SystemExit(" Exit on ctrl-c") from None
