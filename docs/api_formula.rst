.. currentmodule:: redzed

**--- INFORMATION FOR DEVELOPERS ---**

===========
Formula API
===========

The :class:`Formula` API focuses on the output value. Provided methods
match those present in the :ref:`Block API`.

.. class:: Formula(name: str, *, func: Callable, comment: str = "")
  :final:
  :noindex:

  A circuit component created by :deco:`formula` and documented here: :class:`Formula`.

  .. method:: get(*, with_previous: bool = False) -> object

    - when *with_previous* is :const:`False` (default):
        Get the current output value. Return :const:`UNDEF` if the formula
        hasn't been evaluated yet. It means that at least one of the outputs
        referenced by *func* arguments (outputs) is :const:`UNDEF`.
    - when *with_previous* is :const:`True`:
        Return a tuple ``(current_output, previous_output)``. The previous
        output is :const:`UNDEF` if the formula did not have two values
        (current and previous) yet.

  .. method:: is_initialized() -> bool

    Check if the output differs from :const:`UNDEF`,
    i.e. if the formula has been evaluated.

  .. attribute:: circuit
    :type: Circuit

    A link to the circuit the formula belongs to.


.. function:: redzed.get_output(name: str, with_previous: bool = False) -> object
  :noindex:

  Convenience function. Get the current output value of a formula
  (or block) given by its *name*.
