from indra.databases import go_client


def test_invalid_id():
    go_name = go_client.get_go_label('34jkgfh')
    assert go_name is None


def test_go_id_lookup():
    go_id = 'GO:0001768'
    go_name = go_client.get_go_label(go_id)
    assert go_name == 'establishment of T cell polarity'

