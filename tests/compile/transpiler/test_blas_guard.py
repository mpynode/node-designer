"""OpenBLAS single-thread guard (Point 1).

Threaded OpenBLAS LAPACK (np.linalg.*) corrupts thread-local state on Maya's
parallel Evaluation Manager worker threads, segfaulting the session. The
guard caps numpy's bundled OpenBLAS to one thread at plugin load. It must be a
safe no-op on builds with no bundled OpenBLAS (e.g. Accelerate-backed numpy).
"""

from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


class TestBlasGuard(unittest.TestCase):
    def test_limit_is_safe_and_idempotent(self):
        from mpynode._common.util import blas_guard

        # Must not raise, even called twice.
        blas_guard.limit_blas_threads(1)
        blas_guard.limit_blas_threads(1)

    def test_caps_openblas_to_one_when_present(self):
        from mpynode._common.util import blas_guard

        blas_guard.limit_blas_threads(1)
        cur = blas_guard.current_blas_threads()
        # None == this numpy has no bundled OpenBLAS (Accelerate/MKL) -> nothing
        # to cap, guard is a no-op. Otherwise it must now read back as 1.
        if cur is not None:
            self.assertEqual(cur, 1)

    def test_returns_status_string_or_none(self):
        from mpynode._common.util import blas_guard

        status = blas_guard.limit_blas_threads(1)
        self.assertTrue(status is None or isinstance(status, str))


if __name__ == "__main__":
    unittest.main()
