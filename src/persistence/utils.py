from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import or_

def hash_the_password(password):
    hashed_password = generate_password_hash(password)
    assert check_password_hash(hashed_password, password)
    return hashed_password


def inject_where_statement_using_attributes(stmt, mapped_class, **kwargs):
    """
    Utility function to build a conjunction of attributes with AND and OR by appending (.where) to the given stmt
    We need the mapped_class to get its attributes...
    see: https://stackoverflow.com/questions/72132330/can-i-pass-a-dict-to-where-in-sqlalchemy
    """

    # No parameters
    if kwargs is None or len(kwargs) == 0:
        return stmt

    updated_stmt = stmt

    for key, value in kwargs.items():
        if value is None:
            updated_stmt = updated_stmt.where(getattr(mapped_class, key).is_(None))
        elif type(value) == str and "|" in value:
            or_clauses = []
            for v in value.split("|"):
                if v is not None:
                    or_clauses.append(getattr(mapped_class, key) == v)
                else:
                    or_clauses.append(getattr(mapped_class, key).is_(None))

            updated_stmt = updated_stmt.where(or_(*or_clauses))
        else:
            updated_stmt = updated_stmt.where(getattr(mapped_class, key) == value)

    return updated_stmt

