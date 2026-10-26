def test_login_valid(client, admin_user):
    response = client.post("/login", data={
        "username": "admin_test",
        "password": "AdminPass123!"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome back, Admin Test User!" in response.data


def test_login_invalid_password(client, admin_user):
    response = client.post("/login", data={
        "username": "admin_test",
        "password": "WrongPassword!"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_login_inactive_user(client, inactive_user):
    response = client.post("/login", data={
        "username": "inactive_test",
        "password": "InactivePass123!"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"This account has been deactivated" in response.data


def test_logout(client, staff_user):
    # Log in
    client.post("/login", data={"username": "staff_test", "password": "StaffPass123!"})
    # Log out
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been signed out" in response.data


def test_protected_routes_require_login(client):
    response = client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please log in to access this page" in response.data


def test_staff_denied_admin_routes(client, staff_user):
    # Login as Staff
    client.post("/login", data={"username": "staff_test", "password": "StaffPass123!"})
    
    # Attempt Admin-only routes
    res1 = client.get("/users")
    assert res1.status_code == 403

    res2 = client.get("/suppliers")
    assert res2.status_code == 403

    res3 = client.get("/stock/adjust")
    assert res3.status_code == 403


def test_admin_allowed_admin_routes(client, admin_user):
    # Login as Admin
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})

    res = client.get("/users")
    assert res.status_code == 200
    assert b"User Management" in res.data
