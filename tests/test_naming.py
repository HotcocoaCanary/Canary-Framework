from cf.core.utils.naming import to_snake


def test_simple():
    assert to_snake("DBService") == "db_service"
def test_compound():
    assert to_snake("DataSetAdminService") == "data_set_admin_service"
def test_acronym():
    assert to_snake("HttpAPI") == "http_api"
