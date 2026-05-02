"""Smoke tests for the worker against a live Redshift Serverless workgroup.

Requires:
- LINA_REDSHIFT_DSN to be exported.
- Migrations and seed already applied to the workgroup
  (run `lina-redshift --target redshift migrate up && lina-redshift --target redshift seed`).
"""

from __future__ import annotations

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.caller import CallerContext
from lina_redshift.packet import ResultPacket
from lina_redshift.worker import RedshiftWorker


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"legal_ops"}),
        request_id="integration_req",
    )


@pytest.mark.integration
def test_matter_lookup_against_redshift(
    redshift_conn: PgConnection,
    legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "matter_acme_v_beta"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["matter_name"] == "Acme v. Beta Litigation"


@pytest.mark.integration
def test_matter_spend_summary_against_redshift(
    redshift_conn: PgConnection,
    legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="matter_spend_summary",
        params={"matter_ids": ["matter_acme_v_beta"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0


@pytest.mark.integration
def test_vendor_spend_summary_against_redshift(
    redshift_conn: PgConnection,
    legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="vendor_spend_summary",
        params={"vendor_ids": ["vendor_walker"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)


@pytest.mark.integration
def test_invoice_search_returns_named_invoice(
    redshift_conn: PgConnection,
    legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="invoice_search",
        params={"matter_ids": ["matter_acme_v_beta"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    invoice_ids = {r["invoice_id"] for r in packet.metrics}
    assert "inv_walker_2024q3" in invoice_ids
