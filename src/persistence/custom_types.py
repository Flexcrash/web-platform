import sqlalchemy.types as types

from typing import Tuple

import numpy as np
from commonroad.geometry.shape import Rectangle
from shapely.geometry import Point

# See: https://variable-scope.com/posts/storing-and-verifying-passwords-with-sqlalchemy
import bcrypt

class PasswordHash(object):

    def __init__(self, hash_):
        # If this is decoded, the exception triggers and nothing happens; otherwise, the hash_will be decoded
        try:
            hash_ = hash_.decode()
        except (UnicodeDecodeError, AttributeError):
            pass

        assert len(hash_) == 60, 'bcrypt hash should be 60 chars.'
        assert hash_.count('$') == 3, 'bcrypt hash should have 3x "$".'
        self.hash = str(hash_)
        self.rounds = int(self.hash.split('$')[2])

    def __eq__(self, candidate):
        """Hashes the candidate string and compares it to the stored hash."""
        # if isinstance(candidate, basestring):
        encoded_hash = self.hash.encode('utf8')
        if isinstance(candidate, str):
            endcoded_candidate = candidate.encode('utf8')
            return bcrypt.hashpw(endcoded_candidate, encoded_hash) == encoded_hash
        else:
            # This is a PasswordHash
            endcoded_candidate = candidate.hash.encode('utf8')
            return encoded_hash == endcoded_candidate


        # return bcrypt.hashpw(candidate, self.hash) == self.hash
        # return False

    def __repr__(self):
        """Simple object representation."""
        return '<{}>'.format(type(self).__name__)

    @classmethod
    def new(cls, password, rounds):
        """Creates a PasswordHash from the given password."""
        # if isinstance(password, unicode):
        # unicode and str are the same now: https://stackoverflow.com/questions/22638069/python-unicode-error
        password = password.encode('utf8')
        return cls(bcrypt.hashpw(password, bcrypt.gensalt(rounds)))


class PasswordType(types.TypeDecorator):
    """Allows storing and retrieving password hashes using PasswordHash."""
    impl = types.String(250) # TODO Why not Text

    def __init__(self, rounds=12, **kwds):
        self.rounds = rounds
        super(PasswordType, self).__init__(**kwds)

    def process_bind_param(self, value, dialect):
        """Ensure the value is a PasswordHash and then return its hash."""
        return self._convert(value).hash

    def process_result_value(self, value, dialect):
        """Convert the hash to a PasswordHash, if it's non-NULL."""
        if value is not None:
            return PasswordHash(value)

    def validator(self, password):
        """Provides a validator/converter for @validates usage."""
        return self._convert(password)

    def _convert(self, value):
        """Returns a PasswordHash from the given string.

        PasswordHash instances or None values will return unchanged.
        Strings will be hashed and the resulting PasswordHash returned.
        Any other input will result in a TypeError.
        """
        if isinstance(value, PasswordHash):
            return value
        elif isinstance(value, str): # basestring
            return PasswordHash.new(value, self.rounds)
        elif value is not None:
            raise TypeError(
                'Cannot convert {} to a PasswordHash'.format(type(value)))


class PositionType(types.TypeDecorator):
    impl = types.String(250)

    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Given a tuple (x,y) return a string "x,y"
        """
        if value is None:
            return None
        else:
            return ",".join([str(value[0]), str(value[1])])

    def process_result_value(self, value: str, dialect) -> Tuple[float, float]:
        """
        Given a string "x,y" return a tuple
        """
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        x, y = [float(v) for v in value.split(",")]
        return (x, y)


class RectangleType(types.TypeDecorator):

    impl = types.String(250)

    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Given a Rectangle return a string "length,width,center.x,center.y,orientation"
        """
        if value is None:
            return None
        else:
            return ",".join([str(value.length), str(value.width),
                         str(value.center[0]), str(value.center[1]),
                         str(value.orientation)])

    def process_result_value(self, value, dialect):
        """
       Given a string "length,width,center.x,center.y,orientation" return a Rectangle
       """
        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode('utf-8')

        length, width, center_x, center_y, orientation = [float(v) for v in value.split(",")]
        center = np.array([center_x, center_y])
        # center: np.ndarray = None,
        return Rectangle(length, width, center, orientation)

    # def copy(self, **kw):
    #     return RectangleORM(self.impl.length)



# This can be used to map Enumerations, like STATE values
# class MyType(types.TypeDecorator):
#     impl = types.String
#
#     cache_ok = True
#
#     def __init__(self, choices):
#         self.choices = tuple(choices)
#         self.internal_only = True