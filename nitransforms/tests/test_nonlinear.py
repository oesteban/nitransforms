# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Tests of nonlinear transforms."""

import os
import pytest

import numpy as np
import nibabel as nb
from nitransforms.resampling import apply
from nitransforms.base import TransformError
from nitransforms.io.base import TransformFileError
from nitransforms.nonlinear import (
    BSplineFieldTransform,
    DenseFieldTransform,
)
from nitransforms import io
from ..io.itk import ITKDisplacementsField


@pytest.mark.parametrize("size", [(20, 20, 20), (20, 20, 20, 3)])
def test_itk_disp_load(size):
    """Checks field sizes."""
    with pytest.raises(TransformFileError):
        ITKDisplacementsField.from_image(
            nb.Nifti1Image(np.zeros(size), np.eye(4), None)
        )


@pytest.mark.parametrize("size", [(20, 20, 20), (20, 20, 20, 2, 3), (20, 20, 20, 1, 4)])
def test_displacements_bad_sizes(size):
    """Checks field sizes."""
    with pytest.raises(TransformError):
        DenseFieldTransform(nb.Nifti1Image(np.zeros(size), np.eye(4), None))


def test_itk_disp_load_intent():
    """Checks whether the NIfTI intent is fixed."""
    with pytest.warns(UserWarning):
        field = ITKDisplacementsField.from_image(
            nb.Nifti1Image(np.zeros((20, 20, 20, 1, 3)), np.eye(4), None)
        )

    assert field.header.get_intent()[0] == "vector"


def test_displacements_init():
    identity1 = DenseFieldTransform(
        np.zeros((10, 10, 10, 3)),
        reference=nb.Nifti1Image(np.zeros((10, 10, 10, 3)), np.eye(4), None),
    )
    identity2 = DenseFieldTransform(
        reference=nb.Nifti1Image(np.zeros((10, 10, 10)), np.eye(4), None),
    )

    assert np.array_equal(identity1._field, identity2._field)
    assert np.array_equal(identity1._deltas, identity2._deltas)

    with pytest.raises(TransformError):
        DenseFieldTransform()
    with pytest.raises(TransformError):
        DenseFieldTransform(np.zeros((10, 10, 10, 3)))
    with pytest.raises(TransformError):
        DenseFieldTransform(
            np.zeros((10, 10, 10, 3)),
            reference=np.zeros((10, 10, 10, 3)),
        )


def test_bsplines_init():
    with pytest.raises(TransformError):
        BSplineFieldTransform(
            nb.Nifti1Image(np.zeros((10, 10, 10, 4)), np.eye(4), None),
            reference=nb.Nifti1Image(np.zeros((10, 10, 10)), np.eye(4), None),
        )


def test_bsplines_references(testdata_path):
    with pytest.raises(TransformError):
        BSplineFieldTransform(
            testdata_path / "someones_bspline_coefficients.nii.gz"
        ).to_field()

    with pytest.raises(TransformError):
        apply(
            BSplineFieldTransform(
                testdata_path / "someones_bspline_coefficients.nii.gz"
            ),
            testdata_path / "someones_anatomy.nii.gz",
        )

    apply(
        BSplineFieldTransform(testdata_path / "someones_bspline_coefficients.nii.gz"),
        testdata_path / "someones_anatomy.nii.gz",
        reference=testdata_path / "someones_anatomy.nii.gz",
    )


def test_bspline(tmp_path, testdata_path):
    """Cross-check B-Splines and deformation field."""
    os.chdir(str(tmp_path))

    img_name = testdata_path / "someones_anatomy.nii.gz"
    disp_name = testdata_path / "someones_displacement_field.nii.gz"
    bs_name = testdata_path / "someones_bspline_coefficients.nii.gz"

    bsplxfm = BSplineFieldTransform(bs_name, reference=img_name)
    dispxfm = DenseFieldTransform(disp_name)

    out_disp = apply(dispxfm, img_name)
    out_bspl = apply(bsplxfm, img_name)

    out_disp.to_filename("resampled_field.nii.gz")
    out_bspl.to_filename("resampled_bsplines.nii.gz")

    assert (
        np.sqrt(
            (out_disp.get_fdata(dtype="float32") - out_bspl.get_fdata(dtype="float32"))
            ** 2
        ).mean()
        < 0.2
    )


@pytest.mark.parametrize("is_deltas", [True, False])
def test_densefield_x5_roundtrip(tmp_path, is_deltas):
    """Ensure dense field transforms roundtrip via X5."""
    ref = nb.Nifti1Image(np.zeros((2, 2, 2), dtype="uint8"), np.eye(4))
    disp = nb.Nifti1Image(np.random.rand(2, 2, 2, 3).astype("float32"), np.eye(4))

    xfm = DenseFieldTransform(disp, is_deltas=is_deltas, reference=ref)

    node = xfm.to_x5(metadata={"GeneratedBy": "pytest"})
    assert node.type == "nonlinear"
    assert node.subtype == "densefield"
    assert node.representation == "displacements" if is_deltas else "deformations"
    assert node.domain.size == ref.shape
    assert node.metadata["GeneratedBy"] == "pytest"

    fname = tmp_path / "test.x5"
    io.x5.to_filename(fname, [node])

    xfm2 = DenseFieldTransform.from_filename(fname, fmt="X5")

    assert xfm2.reference.shape == ref.shape
    assert np.allclose(xfm2.reference.affine, ref.affine)
    assert xfm == xfm2


def test_bspline_to_x5(tmp_path):
    """Check BSpline transforms export to X5."""
    coeff = nb.Nifti1Image(np.zeros((2, 2, 2, 3), dtype="float32"), np.eye(4))
    ref = nb.Nifti1Image(np.zeros((2, 2, 2), dtype="uint8"), np.eye(4))

    xfm = BSplineFieldTransform(coeff, reference=ref)
    node = xfm.to_x5(metadata={"tool": "pytest"})
    assert node.type == "nonlinear"
    assert node.subtype == "bspline"
    assert node.representation == "coefficients"
    assert node.metadata["tool"] == "pytest"

    fname = tmp_path / "bspline.x5"
    io.x5.to_filename(fname, [node])

    xfm2 = BSplineFieldTransform.from_filename(fname, fmt="X5")
    assert np.allclose(xfm._coeffs, xfm2._coeffs)
    assert xfm2.reference.shape == ref.shape
    assert np.allclose(xfm2.reference.affine, ref.affine)


@pytest.mark.parametrize("is_deltas", [True, False])
def test_densefield_oob_resampling(is_deltas):
    """Ensure mapping outside the field returns input coordinates."""
    ref = nb.Nifti1Image(np.zeros((2, 2, 2), dtype="uint8"), np.eye(4))

    if is_deltas:
        field = nb.Nifti1Image(np.ones((2, 2, 2, 3), dtype="float32"), np.eye(4))
    else:
        grid = np.stack(
            np.meshgrid(*[np.arange(2) for _ in range(3)], indexing="ij"),
            axis=-1,
        ).astype("float32")
        field = nb.Nifti1Image(grid + 1.0, np.eye(4))

    xfm = DenseFieldTransform(field, is_deltas=is_deltas, reference=ref)

    points = np.array([[-1.0, -1.0, -1.0], [0.5, 0.5, 0.5], [3.0, 3.0, 3.0]])
    mapped = xfm.map(points)

    assert np.allclose(mapped[0], points[0])
    assert np.allclose(mapped[2], points[2])
    assert np.allclose(mapped[1], points[1] + 1)


def test_bspline_map_gridpoints():
    """BSpline mapping matches dense field on grid points."""
    ref = nb.Nifti1Image(np.zeros((5, 5, 5), dtype="uint8"), np.eye(4))
    coeff = nb.Nifti1Image(
        np.random.RandomState(0).rand(9, 9, 9, 3).astype("float32"), np.eye(4)
    )

    bspline = BSplineFieldTransform(coeff, reference=ref)
    dense = bspline.to_field()

    # Use a couple of voxel centers from the reference grid
    ijk = np.array([[1, 1, 1], [2, 3, 0]])
    pts = nb.affines.apply_affine(ref.affine, ijk)

    assert np.allclose(bspline.map(pts), dense.map(pts), atol=1e-6)


def test_bspline_map_manual():
    """BSpline interpolation agrees with manual computation."""
    ref = nb.Nifti1Image(np.zeros((5, 5, 5), dtype="uint8"), np.eye(4))
    rng = np.random.RandomState(0)
    coeff = nb.Nifti1Image(rng.rand(9, 9, 9, 3).astype("float32"), np.eye(4))

    bspline = BSplineFieldTransform(coeff, reference=ref)

    from nitransforms.base import _as_homogeneous
    from nitransforms.interp.bspline import _cubic_bspline

    def manual_map(x):
        ijk = (bspline._knots.inverse @ _as_homogeneous(x).squeeze())[:3]
        w_start = np.floor(ijk).astype(int) - 1
        w_end = w_start + 3
        w_start = np.maximum(w_start, 0)
        w_end = np.minimum(w_end, np.array(bspline._coeffs.shape[:3]) - 1)

        window = []
        for i in range(w_start[0], w_end[0] + 1):
            for j in range(w_start[1], w_end[1] + 1):
                for k in range(w_start[2], w_end[2] + 1):
                    window.append([i, j, k])
        window = np.array(window)

        dist = np.abs(window - ijk)
        weights = _cubic_bspline(dist).prod(1)
        coeffs = bspline._coeffs[window[:, 0], window[:, 1], window[:, 2]]

        return x + coeffs.T @ weights

    pts = np.array([[1.2, 1.5, 2.0], [3.3, 1.7, 2.4]])
    expected = np.vstack([manual_map(p) for p in pts])
    assert np.allclose(bspline.map(pts), expected, atol=1e-6)
