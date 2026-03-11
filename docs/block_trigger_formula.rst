.. currentmodule:: redzed

==========================
Blocks, Triggers, Formulas
==========================


Three types of circuit components
=================================

There are two essential types:

- **Logic blocks** - or simply blocks - have outputs and react to received events.
- **Triggers** are functions activated by output changes. They can send events or perform other actions.

and one helper:

- **Formulas** are functions computing values from outputs of other blocks and formulas.

There are many types of :ref:`logic blocks <Logic blocks>` serving different purposes.
Included is a collection of predefined blocks for general use.
It is possible to define own blocks as well.

On the other hand, there is only one :ref:`Trigger <Triggers>` type
and only one :ref:`Formula <Formulas>` type. These components are bound
to a function and all customization is done inside that function.

Blocks and Formulas have a unique name and an output. Triggers do not have
a name nor an output.


Logic blocks
============

Logic block's signature looks like this:

.. class:: ExampleBlock(name: str, *, comment: str = "", initial=redzed.UNDEF, ...)
  :noindex:

This is only an introductory overview of logic blocks.
For a complete API for developers see the :ref:`Block API`.
Individual block types may require other arguments.
Refer to respective documentation for details.


Setting the name
----------------

.. note:: The same naming rules apply also to formulas.

**Parameters**: **name** (str), **comment** (str)

The mandatory argument *name* can be used as a reference to a particular block.
It must be a `valid identifier [↗] <https://docs.python.org/3/reference/lexical_analysis.html#identifiers>`_
as defined in the Python language. Recommended is a meaningful combination of A-Z, a-z, 0-9
and an underscore that starts with a letter. Avoid Python keyword names as this
complicates referencing such blocks from formulas and triggers.
Names prefixed by an underscore are reserved for internal use.

The *name* must be unique. Such name could be generated if necessary:

.. function:: unique_name(prefix: str = 'auto') -> str

  Create a component name that is not in use.
  The returned name consists of the given *prefix* and some generated suffix.
  The *prefix* alone must be a valid name.

The optional *comment* may be any arbitrary text.

The name and the comment are included in the string representation ``str(block)``
and also saved as attributes.


Internal state and output
-------------------------

Each block outputs a value that is derived in some way from block's
internal state. The internal state consists of all data a logic block maintains
in order to correctly perform the task it was designed for.
The internal state can be affected by:

- received :ref:`events <Events>`:

  - forwarded from external sources
  - sent from triggers

- block's own activity:

  - timers
  - readouts of sensors and gauges

- time and date

The current output value is returned by :meth:`Block.get`.
Before initialization is the output set to a sentinel value named :const:`UNDEF`.
The first valid output is obtained from initializers. See the next section.


Initial values
--------------

**Parameter**: **initial** (Initializer|Sequence[Initializer]) - block initializer(s)

Some blocks do not accept the *initial* argument, because their internal state
is not adjustable (e.g. determined by current date or time).

If *initial* is accepted, it specifies an initializer or a :abbr:`sequence (a list or tuple)`
of initializers. Block initializers are objects producing an initialization value
and submitting it to the block. There are just few :ref:`types of initializers <Block initializers>`,
but their combinations cover all possible scenarios.

The purpose of block initialization is to set the block's state and replace the
:const:`UNDEF` on its output with a real output value. While the block is not initialized,
the specified initializers are invoked one by one in given order to produce an initialization
value and that value is then submitted to the block. If an initializer succeeds,
the process stops.


Triggers
========

.. class:: Trigger(func: Callable[..., object])
  :final:

  A circuit component monitoring and acting upon output changes in referenced
  circuit blocks or formulas (commonly named "sources").

  A ``Trigger`` does not have a name nor an output. It's the only such circuit component type.

  Output changes in sources referenced by the function *func* trigger
  a function call with current output values as function's arguments.
  The first function call will take place when none of the arguments is :const:`UNDEF`.
  The :ref:`sources are auto-detected <Function parameters in Triggers and Formulas>`
  from the function's signature. The return value of the function
  will be ignored. An exception raised in the function will abort
  the :ref:`runner <Circuit runner>`.

  The main purpose of a triggered function is to perform some action if certain conditions
  are met, e.g. to send an event to other block(s), often to an output block.

.. decorator:: trigger

  Create a :class:`Trigger` for the decorated function.
  The function itself is unchanged.

---

The two ways to define a trigger are equivalent.
The class allows to write one-liners::

  redzed.Trigger(lambda source: dest_blk.event('put', source))

and the decorator is preferred for everything that does not fit into one line::

  @redzed.trigger
  def _cond_trigger(source):
      if enable_blk.get():
          redzed.send_event('dest', 'put', source)


Formulas
========

Formulas are like blocks with computed output value. Similar to logic blocks,
formulas are given name and comment and their output can be queried.

There are two ways to define a formula.


.. class:: Formula(name: str|None = None, *, func: Callable, comment: str|None = None)
  :final:

  Compute a value.

  Formulas follow the same :ref:`naming rules <Setting the name>` as logic blocks,
  except that *name* and *comment* are not mandatory. If omitted, they will
  be taken from the *func*\'s name and docstring as documented in :deco:`formula`.

  All parameters of the function *func*
  :ref:`refer to outputs <Function parameters in Triggers and Formulas>`
  of other circuit blocks or formulas. When any of them changes, the :class:`!Formula`
  block calls the function and the returned value becomes Formula's output value.

  During the circuit initialization, if any of the arguments is still :const:`UNDEF`,
  the function is not called and the Formula's output remains also set to :const:`UNDEF`.
  Any exception raised in *func* will abort the :ref:`runner <Circuit runner>`.

  The function *func* must be a "pure function". This means its output (return value)
  must be fully determined only by its input (arguments) and there should be no side
  effects to the circuit.


.. decorator:: formula

  Create a :class:`Formula` with the name and comment taken from the decorated function.
  The function itself is unchanged.

  The *comment* will be taken from the first docstring text line.
  The formula *name* will be the same as the function name. However,
  if the function name starts with an underscore, this leading underscore
  is stripped from the formula's name. We *encourage* the use of a leading
  underscore, because it prevents
  :abbr:`name shadowing (hiding a variable in outer scope with the same name)`
  when the formula is referenced in a :class:`Trigger`.



  Example (formula)
  -----------------

  In this example is the output function triggered every time any of the inputs
  ``v1`` or ``v2`` changes. It may print the same output value several times in a row::

    import redzed as rz

    rz.Memory("v1", comment="value #1", initial=False)
    rz.Memory("v2", comment="value #2", initial=False)

    @rz.trigger
    def output(v1, v2):
        print(f"Output is {v1 and v2}")

  In this modified example a formula computes the output value.
  The :func:`!output` function is triggered only when this computed
  value changes. It won't print the same value twice::

    rz.Memory("v1", comment="value #1", initial=False)
    rz.Memory("v2", comment="value #2", initial=False)

    @rz.formula
    def _v1_v2(v1, v2):
        return v1 and v2

    @rz.trigger
    def output(v1_v2):
        print(f"Output is {v1_v2}")


Function parameters in Triggers and Formulas
============================================

Circuit elements :class:`Trigger` and :class:`Formula` are associated
with an external function. As a general rule, all parameters of that
function refer to :abbr:`sources (blocks or formulas)` with the same name.
This rule implies that the function must not use :abbr:`variadic arguments
(\*args or \*\*kwargs)` nor positional-only arguments.

Example::

  mem1 = rz.Memory("inputA", initial=False)
  mem2 = rz.Memory("inputB", initial=False)

  @rz.formula
  def _and2(inputA, inputB):
      return inputA and inputB

The source blocks (here ``inputA`` and ``inputB``) can be created before
or after the definition of the Formula or the Trigger referencing them.


Other reference types
---------------------

If a block or formula cannot be simply referenced by a matching name, use a default
value for a parameter. The default can be either block's name (string)
or block's object. The example below shows both cases.

.. caution::
  \(1) Avoid this feature if possible, because it makes function definitions
  quite confusing. \(2) You might need to re-order the arguments, because Python
  does not allow parameter without a default to follow parameter with a default.

::

  mem1 = rz.Memory("class", initial=False)
  mem2 = rz.Memory(rz.unique_name(), initial=False)

  # "class" is a Python keyword
  @rz.formula
  def _and2(x='class', y=mem2):
      return x and y


Access to the previous output
-----------------------------

A special mode is available in which the :meth:`Block.get` (or :meth:`Formula.get`
which is identical) is called with the *with_previous* option set to :const:`True`.
Tuples of output values ``(current, previous)`` are then passed to the external
function instead of just the current value.

This feature supports use cases where it is necessary to compare the output with the
previous output value. The difference is often called delta (for numeric values)
or a rising/falling edge (for logical values).

Triggers and Formulas can enable this mode by including argument ``_with_previous=True``
(note the leading underscore) in the function definition, preferably at the end of argument list.
The opposite setting ``_with_previous=False`` disables it. This is also the default.

When enabled, all function arguments are affected. Please note that the function
will be called only when any of the *current* output values changes. The previous
values are not monitored. They are just passed to the function for convenience.

Example::

  rz.Memory("state", validator=bool, initial=...)

  @rz.trigger
  def _state_trigger(state, _with_previous=True):
      cur, prev = state
      if prev is rz.UNDEF:
          # initial value, nothing to compare with
          return
      if cur and not prev:
          pass   # just turned on
      if not cur and prev:
          pass   # just turned off
