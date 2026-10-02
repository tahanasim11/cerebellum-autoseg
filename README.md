# Cerebellum AutoSeg

Automatic **draft cerebellum masks** for brain MRI (`.nii` / `.nii.gz`), ready to review and correct in **ITK-SNAP**. Built for Windows users with no coding experience: you only double-click files.

It uses **SynthSeg-robust 2.0**, a published deep learning model that works on any MRI contrast (T1, T2, FLAIR and others) and resolution, and runs on a normal laptop processor. No graphics card is needed.

**Your scans never leave your computer.** The setup downloads software once; after that everything runs locally and offline.

## Requirements

- Windows 10 or 11 (64-bit)
- 8 GB of memory or more (16 GB recommended)
- About 3 GB of free disk space
- Internet for the one-time setup
- [ITK-SNAP](http://www.itksnap.org) for reviewing the masks

## How to download and start

1. On this page, click the green **Code** button, then **Download ZIP**.
2. In your Downloads folder, **right-click the ZIP > Properties**, tick **Unblock** at the bottom (if shown), and click **OK**. This stops Windows from warning about every file.
3. Right-click the ZIP > **Extract All...** and choose where to put it (for example, Documents).
4. Open the extracted folder and double-click **`START HERE - Guide.html`**. It walks you through everything.

## What is inside

| File | What it does |
|---|---|
| `1_SETUP (run once).bat` | Installs everything into `%LOCALAPPDATA%\CerebSeg`. No admin rights needed. Takes 5 to 20 minutes. |
| `2_RUN on my scans.bat` | Pick one or more MRI scans. Saves `<scan>_cerebellum_auto.nii.gz` next to each one and can open it in ITK-SNAP. |
| `3_COMPARE with my manual segmentation.bat` | Compares the draft with a manual segmentation (Dice, volume, surface distances) and saves a color-coded difference map. |
| `START HERE - Guide.html` | Step-by-step guide, review tips and troubleshooting. |
| `tools/` | The Python code behind the buttons. |

## How it works

1. Each scan is resampled to a 1 mm cube centred on the head (160 mm, or 128 mm on computers with less than 11 GB of memory).
2. SynthSeg-robust 2.0 labels the brain; the cube is re-centred on the cerebellum if needed.
3. The left and right cerebellar cortex and white matter labels (7, 8, 46, 47) are merged into one label and mapped back onto the original scan grid, so the mask lines up exactly in ITK-SNAP.

The cerebellum here means cerebellar cortex plus white matter. It excludes the brainstem and the fourth ventricle.

## Important

- **Research use only.** Not for clinical decisions.
- The masks are **drafts**. Review and correct every one before using it in an analysis.
- Expect more corrections in very young children and in abnormal anatomy.

## Credits and citations

This kit downloads, at setup time:

- the [SynthSeg](https://github.com/BBillot/SynthSeg) code (Apache 2.0 license), pinned to a fixed version;
- the SynthSeg-robust 2.0 model weights from the official FreeSurfer server, checked against a SHA256 checksum.

If you use it in a publication, please cite:

- Billot B, Greve DN, Puonti O, et al. SynthSeg: Segmentation of brain MRI scans of any contrast and resolution without retraining. *Medical Image Analysis*. 2023;86:102789.
- Billot B, Magdamo C, Cheng Y, Arnold SE, Das S, Iglesias JE. Robust machine learning segmentation for large-scale analysis of heterogeneous clinical brain MRI datasets. *PNAS*. 2023;120(9):e2216399120.
