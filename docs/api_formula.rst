.. currentmodule:: redzed

**--- INFORMATION FOR DEVELOPERS ---**

===========
Formula API
===========

Circuit blocks rarely access the :class:`Formula` API. It is mainly
used for inspecting its output value. Provided methods match those
present in the :ref:`Block API`.

.. class:: Formula(name: str, *, func: Callable, comment: str = "")
  :final:
  :noindex:

  A circuit component created by :deco:`formula` and documented here: :class:`Formula`.

  .. method:: get() -> Any

    Get the current output value. Return :const:`UNDEF` if the formula
    hasn't been evaluated yet. It means that at least one of the outputs
    referenced by *func* arguments (outputs) is :const:`UNDEF`.

  .. method:: get_previous() -> Any

    Get the previous output value. Return :const:`UNDEF` if the formula
    did not have two values (current and previous) yet.

  .. method:: is_initialized() -> bool

    Check if the output differs from :const:`UNDEF`,
    i.e. if the formula has been evaluated.

  .. attribute:: circuit
    :type: Circuit

    A link to the circuit the formula belongs to.
