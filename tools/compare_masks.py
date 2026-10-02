"""Compare the automatic cerebellum mask with your own manual segmentation.

Reports Dice, volumes and surface distances, and saves a colour-coded difference map
you can open in ITK-SNAP:
    label 1 (red)   = both agree
    label 2 (green) = only in the AUTO mask  (auto added this)
    label 3 (blue)  = only in your MANUAL mask (auto missed this)
Everything runs on this computer. Nothing is uploaded.
"""
import argparse
import csv
import datetime
import glob
import os
import sys

import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

LABEL_FILE_TEXT = """################################################
# ITK-SnAP Label Description File
# File format:
# IDX   -R-  -G-  -B-  -A--  VIS MSH  LABEL
# Fields:
#    IDX:   Zero-based index
#    -R-:   Red color component (0..255)
#    -G-:   Green color component (0..255)
#    -B-:   Blue color component (0..255)
#    -A-:   Label transparency (0.00 .. 1.00)
#    VIS:   Label visibility (0 or 1)
#    MSH:   Label mesh visibility (0 or 1)
#  LABEL:   Label description
################################################
    0     0    0    0        0  0  0    "Clear Label"
    1   255    0    0        1  1  1    "Agree (auto and manual)"
    2     0  255    0        1  1  1    "Auto only (extra)"
    3     0    0  255        1  1  1    "Manual only (missed by auto)"
"""


def surface_distances(a, b, spacing):
    """Distances (mm) from the surface of a to the surface of b, and back."""
    def surface(m):
        return m & ~ndimage.binary_erosion(m, structure=np.ones((3, 3, 3)))
    sa, sb = surface(a), surface(b)
    dt_b = ndimage.distance_transform_edt(~sb, sampling=spacing)
    dt_a = ndimage.distance_transform_edt(~sa, sampling=spacing)
    return np.concatenate([dt_b[sa], dt_a[sb]])


def main():
    ap = argparse.ArgumentParser(description="Compare auto vs manual cerebellum masks.")
    ap.add_argument("--scan", help="The MRI scan")
    ap.add_argument("--manual", help="Your manual segmentation")
    ap.add_argument("--auto", help="The *_cerebellum_auto.nii.gz file")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    common.banner("Compare AUTO cerebellum mask with your MANUAL segmentation")

    scan = args.scan
    if not scan:
        print("Window 1 of 2: select the MRI SCAN that you already segmented by hand.")
        picked = common.pick_files("1 of 2: select the MRI scan", multiple=False)
        scan = picked[0] if picked else None
    if not scan or not os.path.isfile(scan):
        print("No scan selected.")
        return 1
    folder = os.path.dirname(scan)
    stem = common.strip_nifti_ext(scan)

    auto = args.auto
    if not auto:
        hits = sorted(glob.glob(os.path.join(folder, stem + "_cerebellum_auto*.nii*")),
                      key=os.path.getmtime)
        if hits:
            auto = hits[-1]
            print("Found the auto mask: " + os.path.basename(auto))
        else:
            print("No auto mask found next to the scan. Run '2_RUN on my scans.bat' on this scan "
                  "first, or pick the auto mask now.")
            picked = common.pick_files("Select the AUTO mask (*_cerebellum_auto.nii.gz)",
                                       multiple=False, initialdir=folder)
            auto = picked[0] if picked else None
    manual = args.manual
    if not manual:
        print("Window 2 of 2: select YOUR MANUAL segmentation of that scan.")
        picked = common.pick_files("2 of 2: select YOUR manual segmentation", multiple=False,
                                   initialdir=folder)
        manual = picked[0] if picked else None
    if not auto or not manual:
        print("Both an auto mask and a manual segmentation are needed.")
        return 1

    scan_img, _ = common.load_3d(scan)
    auto_img, _ = common.load_3d(auto)
    man_img, _ = common.load_3d(manual)

    man_data = np.asanyarray(man_img.dataobj)
    labels_present = [int(v) for v in np.unique(man_data) if v != 0]
    if len(labels_present) > 1:
        print("Note: your manual file contains several labels %s. All non-zero labels are "
              "treated as cerebellum." % labels_present)

    # put everything on the auto mask grid (which is the scan grid)
    if man_img.shape != auto_img.shape or not np.allclose(man_img.affine, auto_img.affine, atol=1e-3):
        print("The manual segmentation is on a different grid; resampling it to match.")
        man_img = resample_from_to(nib.Nifti1Image((man_data > 0).astype(np.uint8), man_img.affine),
                                   auto_img, order=0)
    a = common.binary_mask(auto_img)
    m = common.binary_mask(man_img)
    if not m.any():
        print("The manual segmentation is empty.")
        return 1

    spacing = tuple(float(z) for z in auto_img.header.get_zooms()[:3])
    vox_ml = float(np.prod(spacing)) / 1000.0
    inter = (a & m).sum()
    dice = 2.0 * inter / (a.sum() + m.sum())
    jacc = inter / float((a | m).sum())
    va, vm = a.sum() * vox_ml, m.sum() * vox_ml
    d = surface_distances(a, m, spacing) if a.any() else np.array([np.nan])
    msd, hd95 = float(np.mean(d)), float(np.percentile(d, 95))

    common.banner("Results")
    print("  Dice overlap ............ %.3f   (1.000 = identical; above 0.90 is very good)" % dice)
    print("  Jaccard ................. %.3f" % jacc)
    print("  Manual volume ........... %.1f mL" % vm)
    print("  Auto volume ............. %.1f mL   (%+.1f%% vs manual)" % (va, 100.0 * (va - vm) / vm))
    print("  Mean surface distance ... %.2f mm" % msd)
    print("  95%% Hausdorff distance .. %.2f mm" % hd95)
    print("  Auto added (extra) ...... %.1f mL" % ((a & ~m).sum() * vox_ml))
    print("  Auto missed ............. %.1f mL" % ((m & ~a).sum() * vox_ml))

    diff = np.zeros(a.shape, np.uint8)
    diff[a & m] = 1
    diff[a & ~m] = 2
    diff[m & ~a] = 3
    out = common.unique_path(os.path.join(folder, stem + "_auto_vs_manual_difference.nii.gz"))
    common.save_like(diff, auto_img, out)
    label_txt = os.path.join(folder, "difference_map_labels.txt")
    with open(label_txt, "w", encoding="utf-8") as f:
        f.write(LABEL_FILE_TEXT)
    print("\nSaved difference map: " + out)
    print("  red = both agree   green = auto added   blue = auto missed")

    csv_path = os.path.join(folder, "CerebellumAutoSeg_comparisons.csv")
    new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date_time", "scan", "manual_file", "auto_file", "dice", "jaccard",
                        "manual_mL", "auto_mL", "mean_surface_dist_mm", "hd95_mm"])
        w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), os.path.basename(scan),
                    os.path.basename(manual), os.path.basename(auto), "%.4f" % dice, "%.4f" % jacc,
                    "%.2f" % vm, "%.2f" % va, "%.2f" % msd, "%.2f" % hd95])
    print("Results also added to: " + csv_path)

    if not args.no_open and common.ask_yes_no("\nOpen the scan with the difference map in ITK-SNAP?"):
        common.open_in_itksnap(scan, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
