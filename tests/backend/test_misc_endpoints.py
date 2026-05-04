"""
Tests for miscellaneous API endpoints (demand, backlog, spending).
"""
import pytest


class TestDemandEndpoints:
    """Test suite for demand forecast endpoints."""

    def test_get_demand_forecasts(self, client):
        """Test getting demand forecasts."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Check structure if data exists
        if len(data) > 0:
            forecast = data[0]
            assert "id" in forecast
            assert "item_sku" in forecast
            assert "item_name" in forecast
            assert "current_demand" in forecast
            assert "forecasted_demand" in forecast
            assert "trend" in forecast
            assert "period" in forecast

    def test_demand_forecast_trends(self, client):
        """Test that demand forecasts have valid trend values."""
        response = client.get("/api/demand")
        data = response.json()

        valid_trends = ["increasing", "stable", "decreasing"]

        for forecast in data:
            assert forecast["trend"].lower() in valid_trends

    def test_demand_forecast_values(self, client):
        """Test that demand forecast values are non-negative."""
        response = client.get("/api/demand")
        data = response.json()

        for forecast in data:
            assert forecast["current_demand"] >= 0
            assert forecast["forecasted_demand"] >= 0

    def test_stable_demand_items_have_small_changes(self, client):
        """Test that items with 'stable' trend have less than 2% change."""
        response = client.get("/api/demand")
        data = response.json()

        stable_items = [item for item in data if item["trend"].lower() == "stable"]

        # Should have at least 5 stable items
        assert len(stable_items) >= 5, f"Expected at least 5 stable items, found {len(stable_items)}"

        for item in stable_items:
            current = item["current_demand"]
            forecasted = item["forecasted_demand"]

            # Calculate percentage change
            if current > 0:
                percent_change = abs((forecasted - current) / current) * 100
                assert percent_change < 2.0, \
                    f"Item {item['item_name']} has {percent_change:.2f}% change, expected < 2%"

    def test_demand_forecast_has_new_items(self, client):
        """Test that new demand forecast items exist."""
        response = client.get("/api/demand")
        data = response.json()

        # Check for the new items we added
        skus = [item["item_sku"] for item in data]

        # Should have Temperature Sensor Module and Logic Controller Board
        assert "SNR-420" in skus, "Missing Temperature Sensor Module"
        assert "CTL-330" in skus, "Missing Logic Controller Board"

        # Verify they are marked as stable
        for item in data:
            if item["item_sku"] in ["SNR-420", "CTL-330"]:
                assert item["trend"].lower() == "stable", \
                    f"New item {item['item_name']} should have stable trend"


class TestBacklogEndpoints:
    """Test suite for backlog endpoints."""

    def test_get_backlog(self, client):
        """Test getting backlog items."""
        response = client.get("/api/backlog")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Check structure if data exists
        if len(data) > 0:
            backlog_item = data[0]
            assert "id" in backlog_item
            assert "order_id" in backlog_item
            assert "item_sku" in backlog_item
            assert "item_name" in backlog_item
            assert "quantity_needed" in backlog_item
            assert "quantity_available" in backlog_item
            assert "days_delayed" in backlog_item
            assert "priority" in backlog_item

    def test_backlog_priority_values(self, client):
        """Test that backlog items have valid priority values."""
        response = client.get("/api/backlog")
        data = response.json()

        valid_priorities = ["high", "medium", "low"]

        for item in data:
            assert item["priority"].lower() in valid_priorities

    def test_backlog_quantity_logic(self, client):
        """Test that backlog quantities are non-negative."""
        response = client.get("/api/backlog")
        data = response.json()

        for item in data:
            # Quantities should be non-negative
            assert item["quantity_needed"] >= 0
            assert item["quantity_available"] >= 0

    def test_backlog_days_delayed(self, client):
        """Test that days delayed is non-negative."""
        response = client.get("/api/backlog")
        data = response.json()

        for item in data:
            assert item["days_delayed"] >= 0

    # ---- Filter behavior (added when /api/backlog gained warehouse/category) ----

    def test_backlog_no_filters_returns_all(self, client):
        """Test that /api/backlog with no filters returns the full set."""
        baseline = client.get("/api/backlog").json()
        with_all = client.get("/api/backlog?warehouse=all&category=all").json()
        assert baseline == with_all
        assert len(baseline) > 0

    def test_backlog_filter_by_warehouse(self, client):
        """Test that warehouse filter narrows backlog correctly via SKU-join.

        The invariant: every item in the filtered response must have a SKU that
        exists in that warehouse's inventory. With seed data where no backlog
        SKUs exist in any inventory, the result will be empty — which is the
        correct behavior (matches Dashboard.vue's existing client-side filter).
        """
        all_inventory = client.get("/api/inventory").json()
        warehouses = {inv["warehouse"] for inv in all_inventory}
        assert len(warehouses) > 0

        for warehouse in warehouses:
            response = client.get(f"/api/backlog?warehouse={warehouse}")
            assert response.status_code == 200
            filtered = response.json()

            warehouse_skus = {
                inv["sku"] for inv in all_inventory if inv["warehouse"] == warehouse
            }
            for item in filtered:
                assert item["item_sku"] in warehouse_skus, (
                    f"Backlog item {item['id']} (SKU {item['item_sku']}) "
                    f"survived warehouse={warehouse} filter but its SKU isn't in that warehouse"
                )

    def test_backlog_filter_by_category(self, client):
        """Test that category filter narrows backlog correctly via SKU-join."""
        all_inventory = client.get("/api/inventory").json()
        categories = {inv["category"] for inv in all_inventory}
        assert len(categories) > 0

        for category in categories:
            response = client.get(f"/api/backlog?category={category}")
            assert response.status_code == 200
            filtered = response.json()

            category_skus = {
                inv["sku"] for inv in all_inventory
                if inv["category"].lower() == category.lower()
            }
            for item in filtered:
                assert item["item_sku"] in category_skus

    def test_backlog_combined_warehouse_and_category(self, client):
        """Test that warehouse + category compose as the SKU-set intersection."""
        all_inventory = client.get("/api/inventory").json()
        # Pick the first inventory row to seed the combined filter
        seed = all_inventory[0]
        warehouse, category = seed["warehouse"], seed["category"]

        response = client.get(
            f"/api/backlog?warehouse={warehouse}&category={category}"
        )
        assert response.status_code == 200
        filtered = response.json()

        # Every returned item's SKU must be in inventory rows matching BOTH filters
        target_skus = {
            inv["sku"] for inv in all_inventory
            if inv["warehouse"] == warehouse
            and inv["category"].lower() == category.lower()
        }
        for item in filtered:
            assert item["item_sku"] in target_skus

    def test_backlog_orphaned_skus_excluded_when_filtered(self, client):
        """Test that backlog items whose SKU is absent from inventory get hidden under any filter.

        Documents the project's existing semantic: when a warehouse/category
        filter is active, backlog items that can't be SKU-joined to inventory
        are excluded. This matches Dashboard.vue's client-side filter.
        """
        full_backlog = client.get("/api/backlog").json()
        all_inventory = client.get("/api/inventory").json()
        inv_skus = {inv["sku"] for inv in all_inventory}
        orphaned = {b["item_sku"] for b in full_backlog if b["item_sku"] not in inv_skus}

        # If the seed data has no orphaned SKUs this test is trivially satisfied;
        # if it has some (current state), they must not appear under any filter.
        if not orphaned:
            return

        # Pick any real warehouse — none of its results should reference orphaned SKUs
        warehouse = next(iter(inv_skus and {inv["warehouse"] for inv in all_inventory}))
        filtered = client.get(f"/api/backlog?warehouse={warehouse}").json()
        for item in filtered:
            assert item["item_sku"] not in orphaned

    def test_backlog_unmatched_warehouse_returns_empty(self, client):
        """Test that a warehouse with no matching inventory yields no backlog items."""
        response = client.get("/api/backlog?warehouse=Mars")
        assert response.status_code == 200
        assert response.json() == []

    def test_backlog_filter_preserves_has_purchase_order_flag(self, client):
        """Test that filtered results still carry the has_purchase_order field."""
        # Use the unfiltered call to find a real warehouse
        all_inv = client.get("/api/inventory").json()
        warehouse = all_inv[0]["warehouse"]

        response = client.get(f"/api/backlog?warehouse={warehouse}")
        for item in response.json():
            # Field must always be present even when the filter narrows the list
            assert "has_purchase_order" in item
            assert isinstance(item["has_purchase_order"], bool)


class TestSpendingEndpoints:
    """Test suite for spending-related endpoints."""

    def test_get_spending_summary(self, client):
        """Test getting spending summary."""
        response = client.get("/api/spending/summary")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

    def test_get_monthly_spending(self, client):
        """Test getting monthly spending data."""
        response = client.get("/api/spending/monthly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Check structure if data exists
        if len(data) > 0:
            month_data = data[0]
            assert "month" in month_data or "period" in month_data

    def test_monthly_spending_has_all_cost_categories(self, client):
        """Test that monthly spending includes all cost categories."""
        response = client.get("/api/spending/monthly")
        data = response.json()

        required_fields = ["procurement", "operational", "labor", "overhead"]

        for month_data in data:
            for field in required_fields:
                assert field in month_data, f"Missing {field} in monthly spending"
                assert isinstance(month_data[field], (int, float))
                assert month_data[field] >= 0

    def test_monthly_spending_has_variety(self, client):
        """Test that monthly spending data has variety (not all the same)."""
        response = client.get("/api/spending/monthly")
        data = response.json()

        # Collect all procurement values
        procurement_values = [month["procurement"] for month in data]

        # Should have at least 3 different values (variety)
        unique_values = set(procurement_values)
        assert len(unique_values) >= 3, \
            "Monthly spending should have variety, not all the same values"

        # Same for other categories
        operational_values = set(month["operational"] for month in data)
        assert len(operational_values) >= 3, \
            "Operational costs should have variety across months"

    def test_get_category_spending(self, client):
        """Test getting spending by category."""
        response = client.get("/api/spending/categories")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Check structure if data exists
        if len(data) > 0:
            category_data = data[0]
            assert "category" in category_data or "name" in category_data

    def test_get_recent_transactions(self, client):
        """Test getting recent transactions."""
        response = client.get("/api/spending/transactions")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # Check structure if data exists
        if len(data) > 0:
            transaction = data[0]
            # Transactions should have some identifying fields
            assert isinstance(transaction, dict)


class TestRootEndpoint:
    """Test suite for root endpoint."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)
        assert "message" in data or "version" in data

    def test_root_endpoint_structure(self, client):
        """Test root endpoint has expected structure."""
        response = client.get("/")
        data = response.json()

        # Should have message and version
        assert "message" in data
        assert "version" in data
        assert isinstance(data["message"], str)
        assert isinstance(data["version"], str)
