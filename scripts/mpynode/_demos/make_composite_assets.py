"""Author the File Composite template's overlay images at 1024x1024.

These three shapes used to be orphan binaries checked into the template folder
with no source: 512x400 / 300x512 / 450x450, aliased, and each a DIFFERENT
non-square size. The viewport compositor normalises every layer to the largest
one, so those odd sizes were rescaled at display time -- and a circle authored
on a 300x512 canvas is only round AFTER that stretch, which is a fragile way to
draw a circle.

Authoring all three square and at the grid's own 1024 removes the rescale
entirely: the demo stack becomes four same-size layers.

The fourth layer, ``grid_bg.png``, is NOT generated here -- it is the shipped
``data/test_grid.png``. The old 480x360 copy was byte-for-byte that image
nearest-downsampled, so there is nothing to author, only a resolution to stop
throwing away.

Run:  mayapy scripts/mpynode/_demos/make_composite_assets.py
"""
from __future__ import annotations

import os
import sys

SIZE = 1024
SS   = 4  # supersample factor, then downsample -> antialiased edges

# The originals' colours, taken as the modal opaque pixel of each image being
# replaced (45627 / 32903 / 14910 opaque texels respectively).
RED   = (220, 40, 40)
GREEN = (40, 190, 70)
BLUE  = (50, 90, 230)


def _out_dir():
    root = os.environ.get("MPYNODE_ROOT")
    if not root:
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        root = os.path.dirname(root)
    return os.path.join(root, "scripts", "mpynode", "_demos", "data")


def build():
    from PIL import Image, ImageDraw

    n   = SIZE * SS
    out = _out_dir()
    if not os.path.isdir(out):
        raise SystemExit("no assets dir: %s" % out)

    made = []

    # --- red square: upper-left block, matching the original's placement -----
    # Extent is pinned by build_file_composite's probe grid, which samples one
    # UV per layer to prove each one actually lands. UV v runs bottom-up, so in
    # IMAGE space those probes are red (0.1875, 0.5625) and green (0.5625,
    # 0.4375). This square must cover the first and miss the second -- hence a
    # bottom edge past 0.5625 and a right edge short of it. (Overlapping the
    # green probe would not break the gate, since green composites ON TOP, but
    # it would stop the probes isolating one layer each.)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d  = ImageDraw.Draw(im)
    d.rectangle([int(0.06 * n), int(0.10 * n), int(0.55 * n), int(0.59 * n)],
                fill=RED + (255,))
    made.append(("red_square.png", im))

    # --- green circle: a TRUE circle now, centred a little above middle ------
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d  = ImageDraw.Draw(im)
    r  = int(0.23 * n)
    cx, cy = int(0.52 * n), int(0.42 * n)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN + (255,))
    made.append(("green_circle.png", im))

    # --- blue triangle: apex DOWN, lower-right, as in the original -----------
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d  = ImageDraw.Draw(im)
    d.polygon([(int(0.30 * n), int(0.55 * n)),
               (int(0.86 * n), int(0.62 * n)),
               (int(0.55 * n), int(0.97 * n))], fill=BLUE + (255,))
    made.append(("blue_triangle.png", im))

    for name, img in made:
        img  = img.resize((SIZE, SIZE), Image.LANCZOS)
        path = os.path.join(out, name)
        img.save(path)
        print("wrote %s  %dx%d" % (path, SIZE, SIZE))


if __name__ == "__main__":
    sys.exit(build())
