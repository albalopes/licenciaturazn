def test_home(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Licenciatura em' in response.data


def test_matrices(client):
    response = client.get('/matrizes')
    assert response.status_code == 200


def test_public_api_unknown_matrix(client):
    response = client.get('/api/matrizes/2018/disciplinas')
    assert response.status_code == 404
