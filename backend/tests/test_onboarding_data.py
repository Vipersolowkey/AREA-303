from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.core.exceptions import ValidationError
from app.services.onboarding_data import parse_tabular_file, validate_row


def test_csv_preview_preserves_headers_and_real_rows() -> None:
    kind, headers, rows = parse_tabular_file(
        "catalogue.csv", "SKU,Tên,Giá,Tồn\nAO-01,Áo thun,250000,12\n".encode()
    )
    assert kind == "csv"
    assert headers == ["SKU", "Tên", "Giá", "Tồn"]
    assert rows == [{"SKU": "AO-01", "Tên": "Áo thun", "Giá": "250000", "Tồn": "12"}]


def test_xlsx_preview_is_supported() -> None:
    book = Workbook()
    sheet = book.active
    sheet.append(["Mã đơn", "Thời gian", "Tổng"])
    sheet.append(["DH-1", "2026-09-05T10:30:00+07:00", 130000])
    output = io.BytesIO()
    book.save(output)

    kind, headers, rows = parse_tabular_file("orders.xlsx", output.getvalue())
    assert kind == "xlsx"
    assert headers == ["Mã đơn", "Thời gian", "Tổng"]
    assert rows[0]["Mã đơn"] == "DH-1"


def test_product_validation_reports_the_exact_bad_row_fields() -> None:
    normalized, errors = validate_row(
        "products",
        {"Mã": "AO-01", "Tên": "Áo thun", "Giá": "-1", "Tồn": "mười"},
        {"sku": "Mã", "name": "Tên", "price": "Giá", "stock": "Tồn"},
    )
    assert normalized["sku"] == "AO-01"
    assert errors == ["price phải là số không âm.", "stock phải là số không âm nguyên."]


def test_order_validation_requires_an_iso_datetime() -> None:
    _, errors = validate_row(
        "orders",
        {"Mã": "DH-1", "Ngày": "05/09/2026", "Tổng": "130000"},
        {"order_id": "Mã", "ordered_at": "Ngày", "total_amount": "Tổng"},
    )
    assert errors == ["ordered_at phải là ngày giờ ISO, ví dụ 2026-09-05T10:30:00+07:00."]


def test_rejects_duplicate_headers_before_staging() -> None:
    with pytest.raises(ValidationError, match="trùng"):
        parse_tabular_file("bad.csv", b"SKU,SKU\nA-1,A-1\n")
