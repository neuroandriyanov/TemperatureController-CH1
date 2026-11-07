"""Overlay geometry in color-image pixels, independent of display size and Qt."""
import math

import cv2
import numpy as np

from imaging import solve_alignment

UNIT_CORNERS = np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]])


class OverlayGeometry:
    def __init__(self, color_size, thermal_size, matrix=None):
        self.color_size = tuple(color_size)
        self.thermal_size = tuple(thermal_size)
        self.scale = np.array([color_size[0]-1., color_size[1]-1.])
        self.corners = self.default_corners()
        if matrix is not None:
            matrix = np.asarray(matrix, dtype=float)
            homogeneous = np.c_[UNIT_CORNERS, np.ones(4)] @ matrix.T
            if np.all(np.abs(homogeneous[:, 2]) > 1e-8):
                candidate = homogeneous[:, :2] / homogeneous[:, 2, None] * self.scale
                if self.valid(candidate):
                    self.corners = candidate

    def default_corners(self):
        cw, ch = self.color_size
        tw, th = self.thermal_size
        factor = min(cw * .72 / tw, ch * .82 / th)
        width, height = (tw-1) * factor, (th-1) * factor
        left, top = (cw-1-width)/2, (ch-1-height)/2
        return np.array([[left, top], [left+width, top],
                         [left+width, top+height], [left, top+height]], float)

    def pairs(self, corners=None):
        points = self.corners if corners is None else np.asarray(corners)
        return [{'thermal': src.tolist(), 'color': dst.tolist()}
                for src, dst in zip(UNIT_CORNERS, points / self.scale)]

    def valid(self, corners):
        points = np.asarray(corners, dtype=float)
        if points.shape != (4, 2) or not np.isfinite(points).all():
            return False
        contour = points.astype(np.float32)
        # Keep the source corner order. Crossing / folded corners would create
        # a projective horizon and an ambiguous temperature projection.
        if not cv2.isContourConvex(contour) or cv2.contourArea(contour, oriented=True) <= 0:
            return False
        try:
            solve_alignment(self.pairs(points))
        except ValueError:
            return False
        return True

    def set_corners(self, corners):
        if not self.valid(corners):
            return False
        self.corners = np.asarray(corners, float).copy()
        return True

    def rotated(self, degrees, start=None):
        points = self.corners if start is None else np.asarray(start, float)
        center = points.mean(axis=0)
        angle = math.radians(degrees)
        rotation = np.array([[math.cos(angle), -math.sin(angle)],
                             [math.sin(angle), math.cos(angle)]])
        return (points-center) @ rotation.T + center

    def rotate(self, degrees):
        return self.set_corners(self.rotated(degrees))


def warp_overlay_rgba(thermal_bgr, corners, canvas_size):
    """Warp unaltered thermal pixels and their alpha together for the editor."""
    height, width = thermal_bgr.shape[:2]
    source = (UNIT_CORNERS * [width-1, height-1]).astype(np.float32)
    matrix = cv2.getPerspectiveTransform(source, np.asarray(corners, np.float32))
    rgba = cv2.cvtColor(thermal_bgr, cv2.COLOR_BGR2RGBA)
    return cv2.warpPerspective(rgba, matrix, tuple(map(int, canvas_size)),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
