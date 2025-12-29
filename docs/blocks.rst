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

**Parameter**: **initial** (Initializer | Sequence[Initializer]) - block initializer(s)

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

There are two equivalent ways to define a trigger. The decorator is preferred for its convenience.

.. decorator:: triggered

  Create a :class:`Trigger` for the decorated function.
  The function itself is unchanged.

.. class:: Trigger(func: Callable[..., Any])
  :final:

  A circuit component monitoring and acting upon output changes in referenced blocks
  or formulas.

  A ``Trigger`` does not have a name nor an output and it is the only such circuit component.

  Output changes in blocks and formulas referenced by the function *func* trigger
  a function call with current output values as function's arguments.
  The first function call will take place when none of the arguments is :const:`UNDEF`.
  The :ref:`references to circuit blocks or formulas <Function parameters in Triggers and Formulas>`
  are auto-detected from the function's signature. The return value of the function
  will be ignored. An exception raised in the function will abort
  the :ref:`runner <Circuit runner>`.

  The main purpose of a triggered function is to perform some action if certain conditions
  are met, e.g. to send an event to other block(s), often to an output block.


Formulas
========

There are two equivalent ways to define a formula.

.. decorator:: formula(name: str, comment: str = "")

  Create a :class:`Formula` with the given :ref:`name and comment <Setting the name>`
  and with the decorated function. The function itself is unchanged.

.. class:: Formula(name: str, *, func: Callable, comment: str = "")
  :final:

  Compute a value. Many circuits do not need this helper.

  Formulas follow the same :ref:`naming rules <Setting the name>` as logic blocks.

  All parameters of the function *func*
  :ref:`refer to circuit blocks or formulas <Function parameters in Triggers and Formulas>`.
  When any of them changes, the :class:`!Formula` block calls the function and the returned
  value becomes Formula's output value.

  During the circuit initialization, if any of the arguments is still :const:`UNDEF`,
  the function is not called and the Formula's output remains also set to :const:`UNDEF`.
  Any exception raised in *func* will abort the the :ref:`runner <Circuit runner>`.

  The function *func* must be a "pure function". This means its output (return value)
  must be fully determined only by its input (arguments) and there should be no side
  effects to the circuit.


  Example (formula)
  -----------------

  In this example is the output function triggered every time any of the inputs
  ``v1`` or ``v2`` changes. It may print the same output value several times in a row::

    redzed.Memory("v1", comment="value #1", initial=False)
    redzed.Memory("v2", comment="value #2", initial=False)

    @redzed.triggered
    def output(v1, v2):
        print(f"Output is {v1 and v2}")

  In this modified example a formula computes the output value.
  The :func:`!output` function is triggered only when this computed
  value changes. It won't print the same value twice::

    redzed.Memory("v1", comment="value #1", initial=False)
    redzed.Memory("v2", comment="value #2", initial=False)

    @redzed.Formula("v1_v2")
    def logical_and(v1, v2):
        return v1 and v2

    @redzed.triggered
    def output(v1_v2):
        print(f"Output is {v1_v2}")


Function parameters in Triggers and Formulas
============================================

Circuit elements :class:`Trigger` and :class:`Formula` are associated
with an external function. As a general rule, all parameters of that
function refer to blocks or formulas with the same name. This rule implies that
the function must not use :abbr:`variadic arguments (\*args or \*\*kwargs)`
nor positional-only arguments.

Example::

  mem1 = redzed.Memory("inputA", initial=False)
  mem2 = redzed.Memory("inputB", initial=False)

  @redzed.formula("logical_and")
  def _and2(inputA, inputB):
      return inputA and inputB

The referenced blocks (here ``inputA`` and ``inputB``) can be created before
or after the definition of the Formula or the Trigger referencing them.

If a block or formula needs to be referenced by a different name, use a default
value for a parameter. The default can be either the block's name (string)
or the block's object. The following example shows both cases:

.. caution::
  The function definition may look confusing when this feature is used.

::

  mem1 = redzed.Memory("class", initial=False)
  mem2 = redzed.Memory(redzed.unique_name(), initial=False)

  # "class" is a Python keyword
  @redzed.formula("logical_and")
  def _and2(x='class', y=mem2):
      return x and y
