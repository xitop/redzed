.. currentmodule:: redzed

===================
Circuit examination
===================

Finding components
==================

- Search by name:
    Use :meth:`Circuit.resolve_name` to get a :class:`Block` or :class:`Formula`
    object by its name. :class:`Trigger` object do not have names.

- Get all objects of given type:
    Use :meth:`Circuit.get_items`. For example ``circuit.get_items(redzed.Memory)``
    returns all :class:`!Memory` blocks.

    This is the only way to get access to circuit's :class:`!Triggers`. However,
    there isn't anything to check or control on :class:`!Triggers`.


Inspecting Formulas and logical Blocks
======================================

The shown :class:`!Block` methods and attributes are available
on :class:`!Formulas` as well. :class:`!Blocks` also support
alternative methods described in the next section.

- Get name and comment:
    Read the corresponding block attributes:
    :attr:`Block.name`, :attr:`Block.comment`

- Get the current output:
    Call :meth:`Block.get`. See also: :meth:`Block.is_undef`.


Inspecting Blocks
=================

- Get name and comment:
    Use the :ref:`_get_names` monitoring event: ``block.event('_get_names')``.

- Get the current output:
    Use the :ref:`_get_output` monitoring event: ``block.event('_get_output')``.

- Get application data:
    If an application has stored :ref:`additional data <9. Application data>`
    to a block, it can be read from :attr:`Block.x_anyname` or :attr:`Block.X_ANYNAME`.
    Substitute ``'anyname'`` by a real name.

- Get the :ref:`internal state <Internal state and output>`:
    This functionality is provided by :meth:`Block.rz_export_state`,
    but it is recommended to use :ref:`_get_state` monitoring event:
    ``block.event('_get_state')``.


Inspecting the circuit
======================

- Get the circuit runner's state:
    Use :meth:`Circuit.get_state()`.


Version information
===================

.. attribute:: __version__
  :type: str

  ``edzed`` version as a string, e.g. "25.12.10"

.. attribute:: __version_info__
  :type: tuple[int]

  ``edzed`` version as a tuple of three numbers, e.g. ``(25, 12, 10)``.
  The version numbers are derived from the release date: year-2000, month, day.
