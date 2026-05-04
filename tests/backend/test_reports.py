"""
Tests for /api/reports/* endpoints (quarterly + monthly trends).

Covers the baseline (no-filter) behavior plus the warehouse/category/status/month
filter parameters that were added so the Reports page respects the global filter
bar like every other view does.
"""
import pytest


VALID_QUARTERS = {"Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"}
QUARTER_MONTHS = {
    "Q1-2025": {"2025-01", "2025-02", "2025-03"},
    "Q2-2025": {"2025-04", "2025-05", "2025-06"},
    "Q3-2025": {"2025-07", "2025-08", "2025-09"},
    "Q4-2025": {"2025-10", "2025-11", "2025-12"},
}


def _orders_for(client, **filters):
    """Helper: fetch /api/orders with the same filters and return the list.

    Used to cross-validate that reports aggregations match the underlying orders
    after the same filter is applied.
    """
    params = {k: v for k, v in filters.items() if v is not None}
    response = client.get("/api/orders", params=params)
    assert response.status_code == 200
    return response.json()


class TestQuarterlyReports:
    """Test suite for /api/reports/quarterly."""

    # ---- Baseline (no filters) ---------------------------------------------

    def test_get_quarterly_reports_baseline(self, client):
        """Test getting quarterly reports without any filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure of first quarter
        first = data[0]
        assert "quarter" in first
        assert "total_orders" in first
        assert "total_revenue" in first
        assert "delivered_orders" in first
        assert "avg_order_value" in first
        assert "fulfillment_rate" in first

    def test_quarterly_returns_all_four_quarters(self, client):
        """Test no-filter response includes all four 2025 quarters in order."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        quarters = [row["quarter"] for row in data]
        assert quarters == ["Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"]

    def test_quarterly_field_types(self, client):
        """Test that quarterly fields have the right numeric types."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for row in data:
            assert isinstance(row["quarter"], str)
            assert isinstance(row["total_orders"], int)
            assert isinstance(row["total_revenue"], (int, float))
            assert isinstance(row["delivered_orders"], int)
            assert isinstance(row["avg_order_value"], (int, float))
            assert isinstance(row["fulfillment_rate"], (int, float))
            assert row["total_orders"] >= 0
            assert row["total_revenue"] >= 0
            assert 0 <= row["delivered_orders"] <= row["total_orders"]

    def test_quarterly_fulfillment_rate_calculation(self, client):
        """Test fulfillment_rate matches delivered_orders / total_orders * 100."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for row in data:
            if row["total_orders"] == 0:
                continue
            expected = round((row["delivered_orders"] / row["total_orders"]) * 100, 1)
            assert abs(row["fulfillment_rate"] - expected) < 0.05

    def test_quarterly_avg_order_value_calculation(self, client):
        """Test avg_order_value matches total_revenue / total_orders."""
        response = client.get("/api/reports/quarterly")
        data = response.json()

        for row in data:
            if row["total_orders"] == 0:
                continue
            expected = round(row["total_revenue"] / row["total_orders"], 2)
            assert abs(row["avg_order_value"] - expected) < 0.01

    # ---- Filter: month / quarter -------------------------------------------

    def test_quarterly_filter_by_quarter(self, client):
        """Test filtering by quarter narrows to that single quarter row."""
        response = client.get("/api/reports/quarterly?month=Q1-2025")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["quarter"] == "Q1-2025"

    def test_quarterly_filter_by_specific_month(self, client):
        """Test filtering by a single month returns just that month's quarter."""
        response = client.get("/api/reports/quarterly?month=2025-03")
        assert response.status_code == 200

        data = response.json()
        # March belongs to Q1; with this filter only Q1 should appear
        assert len(data) == 1
        assert data[0]["quarter"] == "Q1-2025"

    def test_quarterly_month_filter_aggregates_only_filtered_orders(self, client):
        """Test that quarter totals reflect only orders inside the filter."""
        response = client.get("/api/reports/quarterly?month=2025-01")
        q1_jan_only = response.json()[0]

        # Cross-check against /api/orders for the same month
        jan_orders = _orders_for(client, month="2025-01")
        assert q1_jan_only["total_orders"] == len(jan_orders)
        expected_revenue = sum(o.get("total_value", 0) for o in jan_orders)
        assert abs(q1_jan_only["total_revenue"] - expected_revenue) < 0.01

    # ---- Filter: warehouse / category / status -----------------------------

    def test_quarterly_filter_by_warehouse(self, client):
        """Test filtering by warehouse narrows the underlying orders."""
        response = client.get("/api/reports/quarterly?warehouse=Tokyo")
        assert response.status_code == 200
        data = response.json()

        # Cross-check totals against /api/orders?warehouse=Tokyo
        tokyo_orders = _orders_for(client, warehouse="Tokyo")
        total_orders = sum(row["total_orders"] for row in data)
        assert total_orders == len(tokyo_orders)

    def test_quarterly_filter_by_category(self, client):
        """Test filtering by category narrows the underlying orders."""
        response = client.get("/api/reports/quarterly?category=Sensors")
        assert response.status_code == 200
        data = response.json()

        sensors_orders = _orders_for(client, category="Sensors")
        total_orders = sum(row["total_orders"] for row in data)
        assert total_orders == len(sensors_orders)

    def test_quarterly_filter_by_status(self, client):
        """Test filtering by status — when status=Delivered, total==delivered for every quarter."""
        response = client.get("/api/reports/quarterly?status=Delivered")
        assert response.status_code == 200
        data = response.json()

        for row in data:
            # When the filter narrows to Delivered only, total_orders == delivered_orders
            assert row["total_orders"] == row["delivered_orders"]
            if row["total_orders"] > 0:
                assert row["fulfillment_rate"] == 100.0

    # ---- Combined filters and edge cases -----------------------------------

    def test_quarterly_combined_filters(self, client):
        """Test that multiple filters compose (AND-style)."""
        response = client.get(
            "/api/reports/quarterly?warehouse=London&category=Sensors&status=Delivered"
        )
        assert response.status_code == 200
        data = response.json()

        london_sensors_delivered = _orders_for(
            client, warehouse="London", category="Sensors", status="Delivered"
        )
        total_orders = sum(row["total_orders"] for row in data)
        assert total_orders == len(london_sensors_delivered)

    def test_quarterly_all_filter_treated_as_no_filter(self, client):
        """Test passing 'all' as a filter value is equivalent to omitting it."""
        baseline = client.get("/api/reports/quarterly").json()
        with_all = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert baseline == with_all

    def test_quarterly_unmatched_filter_returns_empty(self, client):
        """Test that a filter matching no orders yields no quarter rows."""
        response = client.get("/api/reports/quarterly?warehouse=Mars")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrends:
    """Test suite for /api/reports/monthly-trends."""

    # ---- Baseline ----------------------------------------------------------

    def test_get_monthly_trends_baseline(self, client):
        """Test getting monthly trends without any filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "month" in first
        assert "order_count" in first
        assert "revenue" in first
        assert "delivered_count" in first

    def test_monthly_trends_returns_all_twelve_months(self, client):
        """Test that the 2025 dataset produces 12 month rows in chronological order."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        months = [row["month"] for row in data]
        assert months == [
            "2025-01", "2025-02", "2025-03", "2025-04",
            "2025-05", "2025-06", "2025-07", "2025-08",
            "2025-09", "2025-10", "2025-11", "2025-12",
        ]

    def test_monthly_trends_field_types(self, client):
        """Test types and non-negativity of every numeric field."""
        response = client.get("/api/reports/monthly-trends")
        data = response.json()

        for row in data:
            assert isinstance(row["month"], str)
            assert isinstance(row["order_count"], int)
            assert isinstance(row["revenue"], (int, float))
            assert isinstance(row["delivered_count"], int)
            assert row["order_count"] >= 0
            assert row["revenue"] >= 0
            assert 0 <= row["delivered_count"] <= row["order_count"]

    def test_monthly_trends_totals_match_all_orders(self, client):
        """Test that summed monthly counts equal total order count."""
        trends = client.get("/api/reports/monthly-trends").json()
        all_orders = _orders_for(client)
        total = sum(row["order_count"] for row in trends)
        assert total == len(all_orders)

    # ---- Filter: month / quarter -------------------------------------------

    def test_monthly_trends_filter_by_quarter(self, client):
        """Test filtering by quarter returns only that quarter's months."""
        response = client.get("/api/reports/monthly-trends?month=Q2-2025")
        assert response.status_code == 200
        data = response.json()

        months = {row["month"] for row in data}
        assert months <= QUARTER_MONTHS["Q2-2025"]
        assert len(months) > 0

    def test_monthly_trends_filter_by_specific_month(self, client):
        """Test filtering by a single month returns only that month."""
        response = client.get("/api/reports/monthly-trends?month=2025-07")
        assert response.status_code == 200
        data = response.json()

        assert len(data) == 1
        assert data[0]["month"] == "2025-07"

    # ---- Filter: warehouse / category / status -----------------------------

    def test_monthly_trends_filter_by_warehouse(self, client):
        """Test that warehouse filter narrows underlying orders."""
        response = client.get("/api/reports/monthly-trends?warehouse=San Francisco")
        assert response.status_code == 200
        trends = response.json()

        sf_orders = _orders_for(client, warehouse="San Francisco")
        total = sum(row["order_count"] for row in trends)
        assert total == len(sf_orders)

    def test_monthly_trends_filter_by_status(self, client):
        """Test status=Delivered makes order_count == delivered_count for every month."""
        response = client.get("/api/reports/monthly-trends?status=Delivered")
        data = response.json()

        for row in data:
            assert row["order_count"] == row["delivered_count"]

    # ---- Combined filters and edge cases -----------------------------------

    def test_monthly_trends_combined_filters(self, client):
        """Test combining quarter + warehouse + status filters."""
        response = client.get(
            "/api/reports/monthly-trends?month=Q1-2025&warehouse=Tokyo&status=Delivered"
        )
        assert response.status_code == 200
        trends = response.json()

        # Months returned must be a subset of Q1
        months = {row["month"] for row in trends}
        assert months <= QUARTER_MONTHS["Q1-2025"]

        # Cross-check: aggregate from /api/orders applying the same filters
        cross_orders = _orders_for(
            client, month="Q1-2025", warehouse="Tokyo", status="Delivered"
        )
        total = sum(row["order_count"] for row in trends)
        assert total == len(cross_orders)

    def test_monthly_trends_all_filter_equals_no_filter(self, client):
        """Test passing 'all' is equivalent to omitting the filter."""
        baseline = client.get("/api/reports/monthly-trends").json()
        with_all = client.get(
            "/api/reports/monthly-trends?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert baseline == with_all

    def test_monthly_trends_unmatched_filter_returns_empty(self, client):
        """Test a filter matching no orders yields no month rows."""
        response = client.get("/api/reports/monthly-trends?category=Bananas")
        assert response.status_code == 200
        assert response.json() == []
