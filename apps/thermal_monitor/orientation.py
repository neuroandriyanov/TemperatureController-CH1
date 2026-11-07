"""Display rotation, applied after thermal decoding and OCR."""
from dataclasses import replace

import cv2
import numpy as np


def rotation_matrix(degrees):
    """Transform normalized image coordinates clockwise around the image centre."""
    return np.linalg.matrix_power(np.array([[0., -1., 1.], [1., 0., 0.], [0., 0., 1.]]),
                                  (degrees % 360) // 90)


def rotate_point(point, degrees):
    return (rotation_matrix(degrees) @ [*point, 1.])[:2].tolist()


def rotate_image(image, degrees):
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
             270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    return cv2.rotate(image, codes[degrees % 360]) if degrees % 360 else image


def rotate_thermal(frame, degrees):
    """Keep image, measurements, masks and camera annotations in one orientation."""
    if frame is None or degrees % 360 == 0:
        return frame
    height, width = frame.temps.shape
    new_scale = np.array([height-1, width-1] if degrees % 180 else [width-1, height-1])

    def pixel(point):
        if point is None:
            return None
        xy = np.asarray(point[:2]) / [width-1, height-1]
        target = np.rint(np.array(rotate_point(xy, degrees))*new_scale).astype(int)
        return (int(target[0]), int(target[1]), *point[2:])

    return replace(frame, screen=rotate_image(frame.screen, degrees),
        index=rotate_image(frame.index, degrees), temps=rotate_image(frame.temps, degrees),
        hot_xy=pixel(frame.hot_xy), cold_xy=pixel(frame.cold_xy),
        cam_points={key: pixel(point) for key, point in frame.cam_points.items()},
        _filled=rotate_image(frame._filled, degrees) if frame._filled is not None else None)


def rotate_annotations(settings, cursor, degrees):
    """Re-express existing points and calibration in the newly displayed coordinates."""
    for marker in settings['markers']:
        marker['thermal'] = rotate_point(marker['thermal'], degrees)
    if cursor:
        cursor['thermal'] = rotate_point(cursor['thermal'], degrees)
    calibration = settings['calibration']
    if calibration:
        matrix = np.asarray(calibration['matrix']) @ rotation_matrix(-degrees)
        normalizer = matrix[2, 2] if abs(matrix[2, 2]) > 1e-10 else np.max(np.abs(matrix))
        calibration['matrix'] = (matrix / normalizer).tolist()
        for pair in calibration['pairs']:
            pair['thermal'] = rotate_point(pair['thermal'], degrees)
        calibration['thermal_rotation'] = settings['thermal_rotation']
