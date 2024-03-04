import numpy as np


def _direction_along_segment(a, b):

    u = [1, 0]
    # Compute the direction of the segment defined by the two points

    # this moves the vector in the origin
    road_direction = [b.x - a.x, b.y - a.y]
    # Compute the angle between the road_direction and the vector u
    # E.g. see: https://www.quora.com/What-is-the-angle-between-the-vector-A-2i+3j-and-y-axis
    # https://www.kite.com/python/answers/how-to-get-the-angle-between-two-vectors-in-python
    unit_vector_1 = road_direction / np.linalg.norm(road_direction)
    dot_product = np.dot(unit_vector_1, u)
    # TODO this might have weird behaviors?
    return np.arccos(dot_product)

# https://math.stackexchange.com/questions/654315/how-to-convert-a-dot-product-of-two-vectors-to-the-angle-between-the-vectors
def direction_along_segment(a, b):
    u = [1, 0]
    road_direction = [b.x - a.x, b.y - a.y]
    unit_vector_1 = road_direction / np.linalg.norm(road_direction)
    return np.arctan2(unit_vector_1[1], unit_vector_1[0]) - np.arctan2(u[1], u[0])