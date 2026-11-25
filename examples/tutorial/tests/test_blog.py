import pytest

from flaskr.db import get_db


def test_index(client, auth):
    response = client.get("/")
    assert b"Log In" in response.data
    assert b"Register" in response.data

    auth.login()
    response = client.get("/")
    assert b"test title" in response.data
    assert b"by test on 2018-01-01" in response.data
    assert b"test\nbody" in response.data
    assert b'href="/1/update"' in response.data


@pytest.mark.parametrize("path", ("/create", "/1/update", "/1/delete"))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "/auth/login"


def test_author_required(app, client, auth):
    # change the post author to another user
    with app.app_context():
        db = get_db()
        db.execute("UPDATE post SET author_id = 2 WHERE id = 1")
        db.commit()

    auth.login()
    # current user can't modify other user's post
    assert client.post("/1/update").status_code == 403
    assert client.post("/1/delete").status_code == 403
    # current user doesn't see edit link
    assert b'href="/1/update"' not in client.get("/").data


@pytest.mark.parametrize("path", ("/2/update", "/2/delete"))
def test_exists_required(client, auth, path):
    auth.login()
    assert client.post(path).status_code == 404


def test_create(client, auth, app):
    auth.login()
    assert client.get("/create").status_code == 200
    client.post("/create", data={"title": "created", "body": ""})

    with app.app_context():
        db = get_db()
        count = db.execute("SELECT COUNT(id) FROM post").fetchone()[0]
        assert count == 2


def test_update(client, auth, app):
    auth.login()
    assert client.get("/1/update").status_code == 200
    client.post("/1/update", data={"title": "updated", "body": ""})

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post["title"] == "updated"


@pytest.mark.parametrize("path", ("/create", "/1/update"))
def test_create_update_validate(client, auth, path):
    auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert b"Title is required." in response.data


def test_delete(client, auth, app):
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "/"

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post is None


CLEAR_LINK = b'<a class="action" href="/">Clear</a>'
NO_RESULTS = b"No posts found matching your search."


def _add_post(app, title, body):
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO post (title, body, author_id, created)"
            " VALUES (?, ?, 1, '2018-01-02 00:00:00')",
            (title, body),
        )
        db.commit()


def test_search_matches_title(client, app):
    _add_post(app, "other post", "unrelated")
    response = client.get("/?q=title")
    assert b"test title" in response.data
    assert b"other post" not in response.data


def test_search_matches_body(client, app):
    _add_post(app, "other post", "unrelated")
    response = client.get("/?q=unrelated")
    assert b"other post" in response.data
    assert b"test title" not in response.data


def test_search_case_insensitive(client):
    response = client.get("/?q=TEST TITLE")
    assert b"test title" in response.data


@pytest.mark.parametrize("path", ("/", "/?q=", "/?q=%20%20"))
def test_search_empty_returns_all(client, app, path):
    _add_post(app, "other post", "unrelated")
    response = client.get(path)
    assert b"test title" in response.data
    assert b"other post" in response.data
    assert response.data.count(b'<article class="post">') == 2


def test_search_no_results(client):
    response = client.get("/?q=nomatch")
    assert response.status_code == 200
    assert NO_RESULTS in response.data
    assert b'<article class="post">' not in response.data


def test_search_without_login(client):
    response = client.get("/?q=test")
    assert response.status_code == 200
    assert b"Log In" in response.data
    assert b"test title" in response.data


def test_search_form_value(client):
    response = client.get("/?q=hello")
    assert b'name="q" value="hello"' in response.data


def test_clear_link(client):
    assert CLEAR_LINK in client.get("/?q=test").data
    assert CLEAR_LINK in client.get("/?q=nomatch").data
    assert CLEAR_LINK not in client.get("/").data
    assert CLEAR_LINK not in client.get("/?q=").data
