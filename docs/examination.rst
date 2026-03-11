.. currentmodule:: redzed

===================
Circuit examination
===================

Finding components
==================

- Search by name:
    Use :meth:`Circuit.resolve_name` to get a :class:`Block` or :class:`Formula`
    object by its name. :class:`Trigger` objects do not have names.

- Get all objects of given type:
    Use :meth:`Circuit.get_items`. For example ``circuit.get_items(redzed.Memory)``
    returns all :class:`!Memory` blocks.

    This is the only way to get access to circuit's triggers. However,
    there isn't anything to check or control on :class:`Trigger` objects.

- List all circuit components:
    As noted above, triggers are usually ignored and "all components"
    usually means::

      circuit = redzed.get_circuit()
      components = list(circuit.get_items(redzed.Block)) \
            + list(circuit.get_items(redzed.Formula))


Inspecting Formulas and logical Blocks
======================================

The shown :class:`!Block` methods and attributes are available
on :class:`!Formulas` as well. :class:`!Blocks` also support
alternative methods described in the next section.

- Get name and comment:
    Read the corresponding block attributes:
    :attr:`Block.name`, :attr:`Block.comment`

- Get the current output:
    Call :meth:`Block.get`. See also: :meth:`Block.is_initialized`.


Inspecting Blocks
=================

- Get name, comment, output:
    Use the :ref:`_get_info` monitoring event: ``block.event('_get_info')``.

- Get application data:
    If an application has stored :ref:`additional data <9. Application data>`
    to a block, it can be read from :attr:`Block.x_anyname` or :attr:`Block.X_ANYNAME`.
    Substitute ``'anyname'`` by a real name.

- Get the :ref:`internal state <Internal state and output>`:
    This functionality is provided by :meth:`Block.rz_export_state`,
    but it is recommended to use :ref:`_get_state`: ``block.event('_get_state')``.

- Check the configuration (selected block types only):
    Use the :ref:`_get_config` monitoring event: ``block.event('_get_config')``.


Inspecting the circuit
======================

- Get the circuit runner's state:
    Use :meth:`Circuit.get_state()`.


Inspecting the persistent storage
=================================

- Get the storage during runtime:
    Use :meth:`Circuit.get_persistent_storage()`.

- You might want to inspect the file where the data is stored
  when the application is not running:

  - JSON files contain human readable text. Use a text editor.
  - Pickle files are binary files. Display the contents from
    the command line::

      python -m pickle filename.pkl   # do this only with data you trust!


Version information
===================

.. attribute:: __version__
  :type: str

  ``edzed`` version as a string, e.g. ``"26.3.13"``.

.. attribute:: __version_info__
  :type: tuple[int]

  ``edzed`` version as a tuple of three numbers, e.g. ``(26, 3, 13)``.
  The version numbers are derived from the release date: year-2000, month, day.
