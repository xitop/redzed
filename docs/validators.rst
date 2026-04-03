Data validation
---------------

Certain I/O blocks can validate received data using a validator. It is a function specified
with the *validator* argument. It takes one argument, the received value,
and either accepts it or rejects it. Data validation is optional,
but recommended especially for inputs processing data from external sources.

**Accept**: The validator shall return the validated value if the validation
was successful. The returned data may be modified (preprocessed),
but it cannot be :const:`UNDEF`.

**Reject**: Failed validation is signalized by returning :const:`UNDEF`
or by raising a :exc:`ValidationError` directly or by raising an exception
of type :exc:`ValueError`, :exc:`TypeError` or :exc:`ArithmeticError`
(which includes :exc:`ZeroDivisionError`). These three exceptions will be
wrapped into an :exc:`ValidationError`.
Exceptions of other types are considered validator function failures.

.. exception:: ValidationError

  Failed validation. :exc:`!ValidationError` is raised when an event rejects
  received data, because it did not pass the configured validator.
