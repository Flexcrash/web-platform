from persistence.data_access import create_where_statement_using_attributes

def test_create_conjunction_no_fields():
    kwargs = {}
    where_statement, values_as_tuple = create_where_statement_using_attributes(**kwargs)
    assert where_statement.strip() == ""


def test_create_conjunction_with_one_field():
    kwargs = { "user_id" : 1}
    where_statement, values_as_tuple = create_where_statement_using_attributes(**kwargs)
    assert where_statement.strip() == "WHERE user_id = ?"
    assert values_as_tuple[0] == 1


def test_create_conjunction_with_two_fields():
    kwargs = { "user_id" : 1, "email" : "test@email.me"}
    where_statement, values_as_tuple = create_where_statement_using_attributes(**kwargs)
    assert where_statement.strip() == "WHERE user_id = ? AND email = ?"
    assert values_as_tuple[0] == 1
    assert values_as_tuple[1] == "test@email.me"


def test_create_conjunction_with_three_fields():
    kwargs = { "user_id" : 1, "email" : "test@email.me", "password" : "Foobar"}
    where_statement, values_as_tuple = create_where_statement_using_attributes(**kwargs)
    assert where_statement.strip() == "WHERE user_id = ? AND email = ? AND password = ?"
    assert values_as_tuple[0] == 1
    assert values_as_tuple[1] == "test@email.me"
    assert values_as_tuple[2] == "Foobar"


def test_create_conjunction_with_one_field_none():
    kwargs = { "user_id" : 1, "email" : None}
    where_statement, values_as_tuple = create_where_statement_using_attributes(**kwargs)
    assert where_statement.strip() == "WHERE user_id = ? AND email IS NULL"
    assert len(values_as_tuple) == 1
    assert values_as_tuple[0] == 1