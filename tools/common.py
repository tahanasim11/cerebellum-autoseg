"""Shared helpers for the Cerebellum AutoSeg kit.

Everything here runs locally. No scan is ever uploaded anywhere.
"""
import glob
import os
import subprocess
import sys

import numpy as np
import nibabel as nib

HOME = os.environ.get("CSEG_HOME") or os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "CerebSeg")
SYNTHSEG_DIR = os.path.join(HOME, "SynthSeg")
PREDICT_SCRIPT = os.path.join(SYNTHSEG_DIR, "scripts", "commands", "SynthSeg_predict.py")
LOG_DIR = os.path.join(HOME, "logs")
WORK_DIR = os.path.join(HOME, "work")

NIFTI_TYPES = [("MRI / NIfTI files", "*.nii.gz *.nii"), ("All files", "*.*")]


def banner(text):
    line = "=" * 70
    print("\n" + line + "\n  " + text + "\n" + line)


def strip_nifti_ext(path):
    name = os.path.basename(path)
    for ext in (".nii.gz", ".nii"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return os.path.splitext(name)[0]


def pick_files(title, multiple=True, initialdir=None):
    """Open a normal Windows file picker. Falls back to typing a path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if multiple:
            paths = filedialog.askopenfilenames(title=title, filetypes=NIFTI_TYPES,
                                                initialdir=initialdir)
            paths = list(paths)
        else:
            p = filedialog.askopenfilename(title=title, filetypes=NIFTI_TYPES,
                                           initialdir=initialdir)
            paths = [p] if p else []
        root.destroy()
        return paths
    except Exception:
        print(title)
        p = input("Paste the full path of the file and press Enter: ").strip().strip('"')
        return [p] if p else []


def ask_yes_no(question, default_yes=True):
    suffix = " [Y/n]: " if default_yes else " [y/N]: "
    try:
        ans = input(question + suffix).strip().lower()
    except EOFError:
        return default_yes
    if not ans:
        return default_yes
    return ans.startswith("y")


def load_3d(path):
    """Load a NIfTI image and make sure it is a single 3D volume."""
    img = nib.load(path)
    shape = img.shape
    if len(shape) == 3:
        return img, None
    if len(shape) == 4 and shape[3] == 1:
        return img.slicer[:, :, :, 0], None
    if len(shape) == 4:
        return img.slicer[:, :, :, 0], ("This file holds %d volumes; only the first one was used." % shape[3])
    raise ValueError("Expected a 3D MRI volume but the file has shape %s." % (shape,))


def looks_like_segmentation(img):
    """True if the image looks like a label map instead of an MRI."""
    data = np.asanyarray(img.dataobj)
    if not np.issubdtype(data.dtype, np.integer):
        if not np.allclose(data[::4, ::4, ::4], np.round(data[::4, ::4, ::4])):
            return False
    sample = data[::2, ::2, ::2]
    return np.unique(sample).size <= 12


def binary_mask(img):
    data = np.asanyarray(img.dataobj)
    return data > 0.5


def save_like(mask, ref_img, path):
    """Save a uint8 label map on exactly the same grid/header as the reference image."""
    out = nib.Nifti1Image(mask.astype(np.uint8), ref_img.affine)
    try:
        q, qcode = ref_img.header.get_qform(coded=True)
        s, scode = ref_img.header.get_sform(coded=True)
        if q is not None:
            out.set_qform(q, code=int(qcode))
        if s is not None:
            out.set_sform(s, code=int(scode))
    except Exception:
        pass
    out.header.set_xyzt_units(*ref_img.header.get_xyzt_units())
    out.set_data_dtype(np.uint8)
    nib.save(out, path)
    return path


def unique_path(path):
    """Never overwrite an existing file: add _2, _3, ... if needed."""
    if not os.path.exists(path):
        return path
    base = path[:-7] if path.endswith(".nii.gz") else os.path.splitext(path)[0]
    ext = ".nii.gz" if path.endswith(".nii.gz") else os.path.splitext(path)[1]
    i = 2
    while os.path.exists("%s_%d%s" % (base, i, ext)):
        i += 1
    return "%s_%d%s" % (base, i, ext)


def find_itksnap():
    pats = [
        r"C:\Program Files\ITK-SNAP*\bin\ITK-SNAP.exe",
        r"C:\Program Files (x86)\ITK-SNAP*\bin\ITK-SNAP.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ITK-SNAP*", "bin", "ITK-SNAP.exe"),
    ]
    hits = []
    for p in pats:
        hits.extend(glob.glob(p))
    return sorted(hits)[-1] if hits else None


def open_in_itksnap(image_path, seg_path):
    exe = find_itksnap()
    if not exe:
        print("ITK-SNAP was not found in the usual install folder, so open it yourself:")
        print("  File > Open Main Image  ->  " + image_path)
        print("  Segmentation > Open Segmentation  ->  " + seg_path)
        return False
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([exe, "-g", image_path, "-s", seg_path], creationflags=flags)
    print("Opening ITK-SNAP...")
    return True
