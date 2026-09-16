"""Assertion helpers for ``@maya_test`` node-validation code.

Injected into the Methods namespace (like ``maya_command`` / ``maya_demo`` /
``maya_test``) so an authored test can assert WITHOUT any import:

    @maya_test(label="output doubles the input", digits=3)
    def test_double(self):
        cmds.setAttr(self.name + ".inValue", 2.0)
        assert_close(cmds.getAttr(self.name + ".outValue"), 4.0)

A test PASSES by returning normally and FAILS by raising ``TestFailure`` (an
``AssertionError`` subclass). ``assert_close`` compares floats / flat sequences
of floats to a decimal-place tolerance -- the point of the whole feature: a C++
compile may differ from the Python source in the last few ulps, so "equal to
``digits`` decimal places" (default 4) is the parity bar, not bit-exactness.

The tolerance for a bare ``assert_close(a, b)`` is the current *test-scoped*
default, which ``run_node_test`` sets from ``@maya_test(digits=N)`` for the
duration of the call (thread-local, restored afterwards). An explicit
``assert_close(a, b, digits=K)`` always wins.

Maya-free + Qt-free on purpose (unit-testable; usable from the parity harness).
"""

from __future__ import annotations

import threading

__all__ = [
    "TestFailure",
    "assert_true",
    "assert_equal",
    "assert_close",
    "max_abs_diff",
    "default_digits",
    "set_default_digits",
    "HELPERS",
]


class TestFailure(AssertionError):
    """Raised by the assert helpers when a ``@maya_test`` check fails."""


_FALLBACK_DIGITS = 4
_scope           = threading.local()


def default_digits() -> int:
    """The current test-scoped default decimal-place tolerance."""
    return getattr(_scope, "digits", None) or _FALLBACK_DIGITS


def set_default_digits(digits):
    """Set (or clear, with ``None``) the test-scoped default tolerance. Returns
    the PREVIOUS value so a caller can restore it. Used by ``run_node_test`` to
    scope ``@maya_test(digits=N)`` around a single test invocation."""
    prev          = getattr(_scope, "digits", None)
    _scope.digits = digits
    return prev


def _flatten(v):
    """Flatten scalars / nested sequences of numbers to a flat list of floats.
    A plain scalar becomes ``[float(v)]``. Non-numeric leaves raise
    ``TestFailure`` (a comparison against a non-number is a test authoring bug)."""
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out.extend(_flatten(x))
        return out
    try:
        return [float(v)]
    except (TypeError, ValueError):
        raise TestFailure("value %r is not a number (or sequence of numbers)" % (v,))


def max_abs_diff(a, b) -> float:
    """Max absolute element-wise difference between two scalars / equal-length
    flat-or-nested numeric sequences. Raises ``TestFailure`` on a length
    mismatch."""
    fa, fb = _flatten(a), _flatten(b)
    if len(fa) != len(fb):
        raise TestFailure(
            "length mismatch: %d vs %d" % (len(fa), len(fb)))
    if not fa:
        return 0.0
    return max(abs(x - y) for x, y in zip(fa, fb))


def assert_true(cond, msg=None):
    """Fail unless ``cond`` is truthy."""
    if not cond:
        raise TestFailure(msg or "expected a truthy value, got %r" % (cond,))


def assert_equal(got, expected, msg=None):
    """Fail unless ``got == expected`` (exact). Use for ints / strings / bools /
    topology counts -- NOT for computed floats (use :func:`assert_close`)."""
    if got != expected:
        raise TestFailure(
            msg or "expected %r, got %r" % (expected, got))


def assert_close(got, expected, digits=None, msg=None):
    """Fail unless every element of ``got`` matches ``expected`` to ``digits``
    decimal places (``abs(a-b) <= 0.5 * 10**-digits``). ``got``/``expected`` may
    be scalars or (nested) numeric sequences of equal flattened length.

    ``digits`` defaults to the current test-scoped default (see
    :func:`default_digits`) -- the ``@maya_test(digits=N)`` tolerance -- so a
    compile that differs only in the trailing ulps still passes."""
    d    = default_digits() if digits is None else digits
    tol  = 0.5 * (10.0 ** (-d))
    diff = max_abs_diff(got, expected)
    if diff > tol:
        raise TestFailure(
            msg or ("not equal to %d decimal places: max|diff|=%.3e > %.3e"
                    % (d, diff, tol)))


# The helper names injected into the Methods namespace by build_methods_namespace
# (so authored @maya_test code can call them with no import).
HELPERS = {
    "TestFailure":  TestFailure,
    "assert_true":  assert_true,
    "assert_equal": assert_equal,
    "assert_close": assert_close,
    "max_abs_diff": max_abs_diff,
}
