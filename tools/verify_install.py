"""Checks that the one-time setup worked. Called automatically by 1_SETUP."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

EXPECTED = {
    "synthseg_robust_2.0.h5": "7bc30bf5c3d204f20c4a6cb5a283aedbcab6af1de927cda783f59b67d19cb01c",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ok = True
    print("  Checking the SynthSeg code...")
    if not os.path.exists(common.PREDICT_SCRIPT):
        print("    MISSING: " + common.PREDICT_SCRIPT)
        ok = False

    print("  Checking the model file (this takes a few seconds)...")
    for name, expected in EXPECTED.items():
        p = os.path.join(common.SYNTHSEG_DIR, "models", name)
        if not os.path.exists(p):
            print("    MISSING: " + name)
            ok = False
        elif sha256(p) != expected:
            print("    DAMAGED download, deleting it so the next setup run downloads it again: " + name)
            os.remove(p)
            ok = False

    print("  Checking the Python libraries...")
    try:
        import numpy, scipy, nibabel, psutil  # noqa: F401
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        import tensorflow as tf
        x = tf.ones((1, 8, 8, 8, 1))
        k = tf.ones((3, 3, 3, 1, 2))
        tf.nn.conv3d(x, k, strides=[1, 1, 1, 1, 1], padding="SAME")
        print("    TensorFlow %s works." % tf.__version__)
    except Exception as e:
        ok = False
        print("    PROBLEM: %s" % e)
        if "DLL" in str(e):
            print("    This usually means the 'Microsoft Visual C++ Redistributable (x64)' is missing.")
            print("    Ask IT to install it from https://aka.ms/vs/17/release/vc_redist.x64.exe")

    if ok:
        try:
            sys.path.insert(0, common.SYNTHSEG_DIR)
            from SynthSeg.predict_synthseg import predict  # noqa: F401
        except Exception as e:
            ok = False
            print("    PROBLEM loading SynthSeg: %s" % e)

    try:
        import tkinter  # noqa: F401
    except Exception:
        print("    Note: the file-picker window is unavailable. You can drag scans onto "
              "'2_RUN on my scans.bat' instead.")

    try:
        import psutil
        gb = psutil.virtual_memory().total / 1024 ** 3
        print("  This computer has %.0f GB of memory%s." %
              (gb, "" if gb >= 11 else " (low: close other programs while segmenting)"))
    except Exception:
        pass

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
