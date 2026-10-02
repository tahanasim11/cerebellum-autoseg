"""Cerebellum AutoSeg: a rough cerebellum mask for review in ITK-SNAP.

How it works
  1. Your MRI is resampled to a 1 mm cube centred on the head.
  2. SynthSeg-robust 2.0 (Billot et al., PNAS 2023) labels the whole brain on CPU.
  3. If the cerebellum touches the edge of that cube, the cube is re-centred on the
     cerebellum and SynthSeg runs again.
  4. The four cerebellum labels (left/right cortex and white matter) are merged into
     one label (value 1) and resampled back onto your ORIGINAL scan grid, so the file
     lines up voxel-for-voxel in ITK-SNAP.

Output, saved next to each scan:  <scan name>_cerebellum_auto.nii.gz
Everything runs on this computer. Nothing is uploaded.
"""
import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

CEREBELLUM_LABELS = (7, 8, 46, 47)  # FreeSurfer labels: L/R cerebellum white matter + cortex


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def choose_box_size():
    """Pick the analysis cube (mm) from the computer's memory.

    Measured peak memory: about 4 GB for a 128 mm cube and 6 GB for a 160 mm cube.
    The cube is always re-centred on the cerebellum if needed, and in testing the two
    sizes gave near-identical masks (Dice 0.996), so 160 mm is plenty.
    """
    try:
        import psutil
        gb = psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        gb = 16.0
    size = 160 if gb >= 11.0 else 128
    return size, gb


def head_center_world(img):
    """Rough centre of the head in scanner (world) coordinates."""
    data = np.asanyarray(img.dataobj).astype(np.float32)
    step = max(1, int(round(3.0 / max(min(img.header.get_zooms()[:3]), 0.1))))
    small = data[::step, ::step, ::step]
    pos = small[small > 0]
    if pos.size == 0:
        idx = (np.array(data.shape) - 1) / 2.0
        return nib.affines.apply_affine(img.affine, idx)
    thr = 0.15 * np.percentile(pos, 99)
    mask = small > thr
    mask = ndimage.binary_opening(mask, iterations=1)
    lab, n = ndimage.label(mask)
    if n > 0:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = lab == (int(np.argmax(sizes)) + 1)
    com = np.array(ndimage.center_of_mass(mask)) * step
    return nib.affines.apply_affine(img.affine, com)


def cube_grid(center_world, size):
    """1 mm RAS grid of shape size^3 centred on a world coordinate."""
    aff = np.eye(4)
    aff[:3, 3] = np.asarray(center_world) - (size - 1) / 2.0
    return (size, size, size), aff


def run_synthseg(in_path, out_path, size, threads, log_path):
    cmd = [sys.executable, common.PREDICT_SCRIPT, "--i", in_path, "--o", out_path,
           "--robust", "--cpu", "--threads", str(threads), "--crop", str(size)]
    env = dict(os.environ, TF_CPP_MIN_LOG_LEVEL="3", PYTHONWARNINGS="ignore")
    with open(log_path, "a", encoding="utf-8", errors="replace") as log:
        log.write("\n\n$ " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    if proc.returncode != 0 or not os.path.exists(out_path):
        tail = ""
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                tail = "".join(f.readlines()[-15:])
        except Exception:
            pass
        hint = ""
        if proc.returncode in (-9, 137, 3221225477, -1073741819, 3221226505) or "alloc" in tail.lower():
            hint = ("\nThis usually means the computer ran out of memory. Close other programs "
                    "(browsers, Teams, Outlook) and try again.")
        raise RuntimeError("SynthSeg did not finish (exit code %s).%s\nLast lines of the log:\n%s"
                           % (proc.returncode, hint, tail))


def touches_edge(mask, margin=2):
    return bool(mask[:margin].any() or mask[-margin:].any() or
                mask[:, :margin].any() or mask[:, -margin:].any() or
                mask[:, :, :margin].any() or mask[:, :, -margin:].any())


def largest_component(mask):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3, 3)))
    if n <= 1:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (int(np.argmax(sizes)) + 1)


def segment_one(path, size, threads, log_path):
    """Return (mask on original grid, info dict)."""
    info = {"warnings": []}
    img, warn = common.load_3d(path)
    if warn:
        info["warnings"].append(warn)
    if common.looks_like_segmentation(img):
        raise ValueError("This file looks like a segmentation (only a few label values), not an MRI. "
                         "Pick the MRI scan itself.")

    os.makedirs(common.WORK_DIR, exist_ok=True)
    stem = common.strip_nifti_ext(path)
    tmp_in = os.path.join(common.WORK_DIR, stem + "_cube.nii.gz")
    tmp_out = os.path.join(common.WORK_DIR, stem + "_synthseg.nii.gz")

    center = head_center_world(img)
    mask_1mm, seg_img = None, None
    for attempt in (1, 2):
        shape, aff = cube_grid(center, size)
        cube = resample_from_to(img, (shape, aff), order=1, mode="constant", cval=0.0)
        cube = nib.Nifti1Image(np.asanyarray(cube.dataobj).astype(np.float32), aff)
        nib.save(cube, tmp_in)
        for f in (tmp_out,):
            if os.path.exists(f):
                os.remove(f)
        t0 = time.time()
        print("   SynthSeg pass %d is running (usually 1 to 5 minutes)..." % attempt, flush=True)
        run_synthseg(tmp_in, tmp_out, size, threads, log_path)
        print("   pass %d done in %.1f min" % (attempt, (time.time() - t0) / 60.0), flush=True)

        seg_img = nib.load(tmp_out)
        seg = np.asanyarray(seg_img.dataobj)
        mask_1mm = np.isin(seg, CEREBELLUM_LABELS)
        if not mask_1mm.any():
            raise RuntimeError("SynthSeg did not find any cerebellum in this scan. "
                               "Check that it is a brain MRI that includes the posterior fossa.")
        if not touches_edge(mask_1mm):
            break
        # re-centre the cube on the cerebellum and try once more
        com = np.array(ndimage.center_of_mass(mask_1mm))
        new_center = nib.affines.apply_affine(seg_img.affine, com)
        if attempt == 1 and np.linalg.norm(new_center - center) > 3:
            center = new_center
            continue
        info["warnings"].append("The cerebellum reaches the edge of the scan or analysis box; "
                                "check the edges carefully.")
        break
    info["passes"] = attempt

    # clean up and bring back to the ORIGINAL grid with smooth (linear) interpolation
    mask_1mm = largest_component(mask_1mm)
    mask_img = nib.Nifti1Image(mask_1mm.astype(np.float32), seg_img.affine)
    back = resample_from_to(mask_img, img, order=1, mode="constant", cval=0.0)
    mask = np.asanyarray(back.dataobj) >= 0.5
    if mask.any():
        mask = largest_component(mask)
    vox_ml = float(np.prod(img.header.get_zooms()[:3])) / 1000.0
    info["volume_ml"] = float(mask.sum()) * vox_ml
    info["image"] = img

    for f in (tmp_in, tmp_out):
        try:
            os.remove(f)
        except OSError:
            pass
    return mask, info


def append_log(csv_path, row):
    new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date_time", "scan", "auto_mask_file", "auto_cerebellum_volume_mL",
                        "analysis_box_mm", "passes", "minutes", "notes"])
        w.writerow(row)


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Rough cerebellum mask for ITK-SNAP review.")
    ap.add_argument("scans", nargs="*", help="MRI files (.nii or .nii.gz). Leave empty to pick with a window.")
    ap.add_argument("--box", type=int, default=None, help="Analysis cube size in mm (128, 160 or 192).")
    ap.add_argument("--no-open", action="store_true", help="Do not offer to open ITK-SNAP.")
    args = ap.parse_args()

    common.banner("Cerebellum AutoSeg  (SynthSeg-robust 2.0, runs on this computer only)")
    if not os.path.exists(common.PREDICT_SCRIPT):
        print("Setup has not finished yet. Double-click '1_SETUP (run once).bat' first.")
        return 1

    scans = [s for s in args.scans if s]
    if not scans:
        print("A window will open. Select one or more MRI scans (.nii.gz).")
        print("Tip: hold Ctrl to select several scans at once.\n")
        scans = common.pick_files("Select the MRI scan(s) to segment", multiple=True)
    scans = [s for s in scans if os.path.isfile(s)]
    if not scans:
        print("No scan selected. Nothing to do.")
        return 1

    size, gb = choose_box_size()
    if args.box:
        size = args.box
    threads = max(1, (os.cpu_count() or 2))
    print("Computer memory: %.0f GB  ->  analysis box %d mm,  %d CPU threads" % (gb, size, threads))
    if size < 160:
        print("NOTE: this computer has little memory, so a smaller box is used. The box is "
              "still centred on the cerebellum, but close other programs while it runs.")
    print("Each scan usually takes 1 to 10 minutes. Leave this window open.")

    os.makedirs(common.LOG_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(common.LOG_DIR, "synthseg_%s.log" % stamp)

    done = []
    for i, path in enumerate(scans, 1):
        name = os.path.basename(path)
        common.banner("Scan %d of %d:  %s" % (i, len(scans), name))
        t0 = time.time()
        try:
            mask, info = segment_one(path, size, threads, log_path)
        except Exception as e:  # keep going with the next scan
            print("   FAILED: %s" % e)
            print("   (Technical log: %s)" % log_path)
            continue
        out_path = common.unique_path(os.path.join(os.path.dirname(path),
                                                   common.strip_nifti_ext(path) + "_cerebellum_auto.nii.gz"))
        common.save_like(mask, info["image"], out_path)
        minutes = (time.time() - t0) / 60.0
        print("   Saved: %s" % out_path)
        print("   Auto cerebellum volume (before your corrections): %.1f mL" % info["volume_ml"])
        for w in info["warnings"]:
            print("   WARNING: " + w)
        append_log(os.path.join(os.path.dirname(path), "CerebellumAutoSeg_log.csv"),
                   [datetime.datetime.now().isoformat(timespec="seconds"), name,
                    os.path.basename(out_path), "%.2f" % info["volume_ml"], size, info["passes"],
                    "%.1f" % minutes, " | ".join(info["warnings"])])
        done.append((path, out_path))

    common.banner("Finished: %d of %d scan(s) segmented" % (len(done), len(scans)))
    if done and not args.no_open:
        if len(done) == 1:
            if common.ask_yes_no("Open the scan and its new mask in ITK-SNAP now?"):
                common.open_in_itksnap(*done[0])
        else:
            print("To review, open each scan in ITK-SNAP and load its *_cerebellum_auto.nii.gz file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
