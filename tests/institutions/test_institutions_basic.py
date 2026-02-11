"""
Tests for Institutions API – AutomaSEI v2.0

Scope:
- Basic CRUD for institutions (NO DELETE)
- Filtering by active_only
- Payload validation

IMPORTANT:
- These tests validate API contracts only
- No legacy process logic is tested here
"""

class TestInstitutionsBasic:

    def test_list_empty(self, test_client):
        """
        When there are no institutions,
        the list endpoint must return an empty list.
        """
        response = test_client.get("/institutions")
        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_create_institution(self, test_client, sample_institution_data):
        """Creating a valid institution must succeed."""
        response = test_client.post(
            "/institutions",
            json=sample_institution_data
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["name"] == sample_institution_data["name"]
        assert data["sei_url"] == sample_institution_data["sei_url"]
        assert data["is_active"] is True

    def test_list_with_data(self, test_client, sample_institution_data):
        """After creating an institution, it must appear in the list."""
        test_client.post("/institutions", json=sample_institution_data)
        response = test_client.get("/institutions")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1

    def test_get_institution_by_id(self, test_client, sample_institution_data):
        """It must be possible to retrieve an institution by its ID."""
        create_response = test_client.post(
            "/institutions",
            json=sample_institution_data
        )
        institution_id = create_response.json()["id"]
        response = test_client.get(f"/institutions/{institution_id}")
        assert response.status_code == 200
        assert response.json()["id"] == institution_id

    def test_update_institution_partial(self, test_client, sample_institution_data):
        """Partial updates must be supported (PUT with partial body)."""
        create_response = test_client.post(
            "/institutions",
            json=sample_institution_data
        )
        institution_id = create_response.json()["id"]
        response = test_client.put(
            f"/institutions/{institution_id}",
            json={"is_active": False}
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_active_only_filter(self, test_client, sample_institution_data):
        """The active_only filter must hide inactive institutions."""
        create_response = test_client.post(
            "/institutions",
            json=sample_institution_data
        )
        institution_id = create_response.json()["id"]
        test_client.put(
            f"/institutions/{institution_id}",
            json={"is_active": False}
        )
        response = test_client.get("/institutions?active_only=true")
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_create_validation_error(self, test_client):
        """Invalid payloads must return 422."""
        response = test_client.post("/institutions", json={})
        assert response.status_code == 422
