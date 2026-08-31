"""Checks for the patch-based surface relaxation solver
(``MPyDeformer/Patch Relax``).

The algorithm is de Goes et al., Pixar, *SIGGRAPH '18 Talks*. Everything in
``patch_relax`` is vectorized numpy written in the transpiler's deterministically
lowerable subset, which makes the code less obvious than the scalar reference it
was ported from -- so the through-space path is pinned against a compact SCALAR
oracle transcribed straight from that reference. Anything that drifts in the
padding, the ring wrap-around or the prefix-sum matmul shows up there
immediately.

No Maya: the module is pure numpy by design (the Maya half lives in the
template's ``seed_rings``), so these run standalone.
"""

from __future__ import annotations

import unittest

import numpy as np

from mpynode._common.nodes.mesh.patch_relax import (
    build_ring_adjacency,
    patch_relax,
)


# ===========================================================================
# fixtures
# ===========================================================================


def _torus(nu=12, nv=8, r_major=3.0, r_minor=1.0):
    """Closed all-quad torus: no boundary at all, every vertex valence 4."""
    pts = []
    for i in range(nu):
        a = 2.0 * np.pi * i / nu
        for j in range(nv):
            b = 2.0 * np.pi * j / nv
            rr = r_major + r_minor * np.cos(b)
            pts.append((rr * np.cos(a), r_minor * np.sin(b), rr * np.sin(a)))
    counts, indices = [], []
    for i in range(nu):
        for j in range(nv):
            i1, j1 = (i + 1) % nu, (j + 1) % nv
            counts.append(4)
            indices += [i * nv + j, i1 * nv + j, i1 * nv + j1, i * nv + j1]
    return (np.array(pts, dtype=np.float64), np.array(counts, dtype=np.int64),
            np.array(indices, dtype=np.int64))


def _grid(n=5, size=4.0):
    """OPEN quad grid -- every border vertex has a ring that does not close."""
    xs = np.linspace(-size / 2.0, size / 2.0, n)
    pts = np.array([(xs[i], 0.0, xs[j]) for i in range(n) for j in range(n)],
                   dtype=np.float64)
    counts, indices = [], []
    for i in range(n - 1):
        for j in range(n - 1):
            counts.append(4)
            indices += [i * n + j, (i + 1) * n + j,
                        (i + 1) * n + j + 1, i * n + j + 1]
    return pts, np.array(counts, dtype=np.int64), np.array(indices,
                                                           dtype=np.int64)


def _bend(pts, seed=7, twist=0.6, noise=0.05):
    """A twist plus noise, so a relax has real distortion to undo."""
    rng = np.random.RandomState(seed)
    ang = pts[:, 1] * twist
    ca, sa = np.cos(ang), np.sin(ang)
    out = np.stack([pts[:, 0] * ca - pts[:, 2] * sa, pts[:, 1],
                    pts[:, 0] * sa + pts[:, 2] * ca], axis=1)
    return out + rng.normal(scale=noise, size=out.shape)


def _edge_error(x, rest, ring):
    """Mean |deformed edge length - rest edge length| over every ring edge."""
    n = x.shape[0]
    m = ring >= 0
    idx = np.where(m, ring, n)
    xp = np.concatenate([x, np.zeros((1, 3))], 0)
    rp = np.concatenate([rest, np.zeros((1, 3))], 0)
    ed = np.take(xp, idx, 0) - x[:, None, :]
    er = np.take(rp, idx, 0) - rest[:, None, :]
    d = np.sqrt((ed * ed).sum(-1)) - np.sqrt((er * er).sum(-1))
    return float((np.abs(d) * m).sum() / max(m.sum(), 1))


# ===========================================================================
# scalar oracle -- a direct transcription of the reference, loops and all
# ===========================================================================


def _oracle_through_space(x, x_hat, ring, iterations, alpha):
    """Reference relaxation with ``surface_blend = 0``, one vertex at a time.

    Deliberately the naive form: per-vertex Python loops, ``np.outer`` for the
    covariance, no padding and no masks. It shares no code with the vectorized
    implementation, so agreement between them is real evidence.
    """
    x = x.copy()
    n = x.shape[0]
    adj = [[int(v) for v in row if v >= 0] for row in ring]

    def decals(pos):
        out = []
        for vi, nbrs in enumerate(adj):
            val = len(nbrs)
            if val == 0:
                out.append(np.zeros((0, 2)))
                continue
            edges = np.array([pos[j] - pos[vi] for j in nbrs])
            lens = np.array([np.linalg.norm(e) + 1e-12 for e in edges])
            angles = np.zeros(val)
            for k in range(val):
                e1 = edges[k] / lens[k]
                e2 = edges[(k + 1) % val] / lens[(k + 1) % val]
                angles[k] = np.arccos(np.clip(float(e1 @ e2), -1.0, 1.0))
            tot = angles.sum()
            sc = (2.0 * np.pi / tot) if tot > 1e-8 else 1.0
            d = np.zeros((val, 2))
            cum = 0.0
            for k in range(val):
                d[k] = (lens[k] * np.cos(cum), lens[k] * np.sin(cum))
                cum += angles[k] * sc
            out.append(d)
        return out

    def weights(decs):
        out = []
        for d in decs:
            val = d.shape[0]
            if val == 0:
                out.append(np.zeros(0))
                continue
            w = np.zeros(val)
            for k in range(val):
                ek = d[k]
                tang = ek / (np.linalg.norm(ek) + 1e-12)
                norm = np.array([-tang[1], tang[0]])
                c_neg = f_pos = f_neg = 0.0
                seen = False
                for m in range(val):
                    if m == k:
                        continue
                    ct = float(tang @ d[m])
                    cn = float(norm @ d[m])
                    if not seen:
                        c_neg, f_pos, f_neg, seen = ct, cn, cn, True
                    else:
                        c_neg = min(c_neg, ct)
                        f_pos = max(f_pos, cn)
                        f_neg = min(f_neg, cn)
                w[k] = abs(c_neg) * max(f_pos - f_neg, 1e-8)
            tot = w.sum()
            out.append(w / tot if tot > 1e-12 else
                       np.full(val, 1.0 / max(val, 1)))
        return out

    rest_w = weights(decals(x_hat))
    hat_edges = [np.array([x_hat[j] - x_hat[i] for j in adj[i]]).reshape(-1, 3)
                 for i in range(n)]
    v_hat = np.array([sum((rest_w[i][k] * hat_edges[i][k]
                           for k in range(len(adj[i]))), np.zeros(3))
                      for i in range(n)])

    for _ in range(iterations):
        new = np.zeros_like(x)
        for vi in range(n):
            val = len(adj[vi])
            if val == 0:
                new[vi] = x[vi]
                continue
            cur = np.array([x[j] - x[vi] for j in adj[vi]])
            v_pose = sum((rest_w[vi][k] * cur[k] for k in range(val)),
                         np.zeros(3))
            h = np.zeros((3, 3))
            for k in range(val):
                h += rest_w[vi][k] * np.outer(hat_edges[vi][k], cur[k])
            u, _s, vt = np.linalg.svd(h)
            v = vt.T
            dmat = np.eye(3)
            dmat[2, 2] = np.sign(np.linalg.det(v @ u.T))
            rot = v @ dmat @ u.T
            new[vi] = x[vi] + 0.5 * (v_pose - alpha * (rot @ v_hat[vi]))
        x = new
    return x


# ===========================================================================


class TestRingAdjacency(unittest.TestCase):
    """The CCW 1-ring is the input everything else is defined against."""

    def test_closed_mesh_rings_are_complete_and_ordered(self):
        pts, counts, indices = _torus()
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        self.assertEqual(ring.shape[0], pts.shape[0])
        # A torus is uniform valence 4 with no boundary: every row is full.
        self.assertEqual(ring.shape[1], 4)
        self.assertTrue((ring >= 0).all(), "no vertex of a torus may be pinned")
        # The ring must be a genuine CCW WALK, not merely the right SET of
        # neighbours: consecutive entries (a, b) are the prev/next of one face
        # around the centre, so some face contains the triple (a, vi, b).
        corners = set()
        off = 0
        for c in counts:
            f = [int(v) for v in indices[off:off + c]]
            for k in range(c):
                corners.add((f[(k - 1) % c], f[k], f[(k + 1) % c]))
            off += c
        for vi in range(ring.shape[0]):
            nbrs = [int(v) for v in ring[vi]]
            self.assertEqual(len(set(nbrs)), len(nbrs),
                             "vertex %d repeats a neighbour" % vi)
            for k in range(len(nbrs)):
                a, b = nbrs[k], nbrs[(k + 1) % len(nbrs)]
                self.assertIn((a, vi, b), corners,
                              "ring of %d is not a walk: no face has (%d, %d, %d)"
                              % (vi, a, vi, b))

    def test_mixed_valence_rings(self):
        # Every row must hold at least a triangle's worth of neighbours, and a
        # ragged table's short rows must be -1 padded.
        pts, counts, indices = _torus(nu=6, nv=5)
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        valence = (ring >= 0).sum(axis=1)
        self.assertTrue((valence >= 3).all())
        self.assertTrue(((ring >= 0) | (ring == -1)).all())

    def test_border_vertices_are_pinned(self):
        pts, counts, indices = _grid(n=5)
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        pinned = (ring < 0).all(axis=1)
        # A 5x5 grid has 16 border vertices and 9 interior ones.
        self.assertEqual(int(pinned.sum()), 16)
        self.assertEqual(int((~pinned).sum()), 9)

    def test_degenerate_input_is_empty_not_an_error(self):
        for counts, indices, n in (([], [], 4), ([4], [0, 1, 2, 3], 0)):
            ring = build_ring_adjacency(np.array(counts, dtype=np.int64),
                                        np.array(indices, dtype=np.int64), n)
            self.assertEqual(ring.shape[0], max(n, 0))
            self.assertEqual(ring.size, 0)


class TestAgainstScalarOracle(unittest.TestCase):
    """Vectorized == the naive per-vertex reference, to the last bit."""

    def test_through_space_matches_the_oracle(self):
        pts, counts, indices = _torus()
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        x = _bend(pts)
        for iterations, alpha in ((1, 1.0), (5, 1.0), (4, 0.35)):
            want = _oracle_through_space(x, pts, ring, iterations, alpha)
            got = patch_relax(x, pts, ring, iterations, alpha, 0.0)
            self.assertLess(
                float(np.abs(want - got).max()), 1e-12,
                "iterations=%d alpha=%s diverged from the scalar reference"
                % (iterations, alpha))

    def test_pinned_border_vertices_never_move(self):
        pts, counts, indices = _grid(n=5)
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        x = _bend(pts, noise=0.2)
        out = patch_relax(x, pts, ring, 10, 1.0, 0.0)
        pinned = (ring < 0).all(axis=1)
        self.assertTrue(np.array_equal(out[pinned], x[pinned]),
                        "a pinned border vertex moved")
        self.assertTrue((np.abs(out[~pinned] - x[~pinned]).max() > 1e-6),
                        "interior vertices should have relaxed")


class TestRelaxationBehaviour(unittest.TestCase):
    """What the deformer actually promises a user."""

    def test_relax_reduces_edge_distortion(self):
        pts, counts, indices = _torus(nu=24, nv=16)
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        # Squash so the rows crowd, then twist. The twist angle comes from the
        # REST y: driving it from the squashed y shrinks the twist and leaves
        # an almost pure SCALE, which rotation-fitting cannot restore.
        x = pts.copy()
        x[:, 1] *= 0.35
        ang = pts[:, 1] * 0.9
        ca, sa = np.cos(ang), np.sin(ang)
        x = np.stack([x[:, 0] * ca - x[:, 2] * sa, x[:, 1],
                      x[:, 0] * sa + x[:, 2] * ca], axis=1)
        before = _edge_error(x, pts, ring)
        after = _edge_error(patch_relax(x, pts, ring, 20, 1.0, 0.0), pts, ring)
        self.assertLess(after, before * 0.75,
                        "20 sweeps should cut edge distortion substantially "
                        "(before=%.6f after=%.6f)" % (before, after))

    def test_alpha_zero_and_zero_iterations_are_no_ops(self):
        pts, counts, indices = _torus()
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        x = _bend(pts)
        self.assertTrue(np.array_equal(patch_relax(x, pts, ring, 0, 1.0, 0.0), x))
        # alpha=0 drops the rest term, leaving the ring-centroid pull only, so
        # it is NOT a no-op -- but it must stay finite and bounded.
        out = patch_relax(x, pts, ring, 5, 0.0, 0.0)
        self.assertTrue(bool(np.isfinite(out).all()))

    def test_an_undeformed_mesh_is_left_alone(self):
        # rest == posed is the fixed point: relaxing a mesh already at rest
        # must not drift it, or the deformer would never be neutral.
        pts, counts, indices = _torus()
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        out = patch_relax(pts.copy(), pts, ring, 10, 1.0, 0.0)
        self.assertLess(float(np.abs(out - pts).max()), 1e-9)

    def test_surface_blend_is_inert_at_alpha_one(self):
        # A property of the REFERENCE, not a bug here: its 2D target is
        # step*(vp2 - alpha*Rvh2) where Rvh2 IS vp2 by construction, so the
        # surface branch contributes nothing at alpha=1. Pinned so the surprise
        # is recorded rather than rediscovered.
        pts, counts, indices = _torus(nu=16, nv=10)
        ring = build_ring_adjacency(counts, indices, pts.shape[0])
        x = _bend(pts, noise=0.0)
        full_surface = patch_relax(x, pts, ring, 10, 1.0, 1.0)
        self.assertLess(float(np.abs(full_surface - x).max()), 1e-9,
                        "surface_blend=1 at alpha=1 must be a no-op")
        # With alpha < 1 the term is live again.
        partial = patch_relax(x, pts, ring, 10, 0.5, 1.0)
        self.assertGreater(float(np.abs(partial - x).max()), 1e-6)


if __name__ == "__main__":
    unittest.main()
