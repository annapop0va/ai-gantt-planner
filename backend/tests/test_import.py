from __future__ import annotations

from datetime import date

import pytest

from app.domain.errors import (
    FileTooLargeError,
    ImportValidationError,
    InvalidWorkbookError,
    TooManyTasksError,
    UnsupportedFileTypeError,
)
from app.services.excel_import import ExcelImportService
from tests.conftest import SAMPLE_XLSX_PATH, build_workbook_bytes


def test_valid_sample_imports_16_tasks():
    content = SAMPLE_XLSX_PATH.read_bytes()
    result = ExcelImportService().parse(content, filename=SAMPLE_XLSX_PATH.name)
    assert len(result.tasks) == 16
    assert result.project_name == "sample_patient_card_project"


def test_uses_first_non_empty_worksheet():
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 2, ""]],
        leading_blank_sheet=True,
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    assert len(result.tasks) == 1
    assert result.tasks[0].name == "Task A"


def test_normalized_headers_with_surrounding_whitespace():
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 2, ""]],
        headers=(" Задача ", "Описание", "Исполнитель", "Длительность", "Предшественники"),
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    assert len(result.tasks) == 1


def test_missing_column_is_rejected():
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 2]],
        headers=("Задача", "Описание", "Исполнитель", "Длительность"),  # no Предшественники
    )
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_MISSING_COLUMN" in codes


def test_duplicate_normalized_name_is_rejected():
    content = build_workbook_bytes(
        [
            ["Задача Один", "", "Alice", 1, ""],
            ["задача  один", "", "Bob", 1, ""],  # same after casefold + whitespace collapse
        ]
    )
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_DUPLICATE_TASK_NAME" in codes


def test_yo_ye_are_treated_as_equivalent_duplicates():
    content = build_workbook_bytes(
        [
            ["Ёлка проект", "", "Alice", 1, ""],
            ["Елка проект", "", "Bob", 1, ""],
        ]
    )
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_DUPLICATE_TASK_NAME" in codes


@pytest.mark.parametrize("bad_value", [0, -1, 2.5, "abc", 366])
def test_invalid_duration_is_rejected(bad_value):
    content = build_workbook_bytes([["Task A", "", "Alice", bad_value, ""]])
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_INVALID_DURATION" in codes


def test_duration_accepts_integer_like_float_and_numeric_string():
    content = build_workbook_bytes(
        [
            ["Task A", "", "Alice", 3.0, ""],
            ["Task B", "", "Bob", "4", ""],
        ]
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Task A"].duration_workdays == 3
    assert by_name["Task B"].duration_workdays == 4


def test_unknown_predecessor_is_rejected():
    content = build_workbook_bytes([["Task A", "", "Alice", 1, "Nonexistent Task"]])
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_UNKNOWN_PREDECESSOR" in codes


def test_forward_predecessor_reference_resolves():
    content = build_workbook_bytes(
        [
            ["Task A", "", "Alice", 1, "Task B"],  # references a row defined *after* it
            ["Task B", "", "Bob", 1, ""],
        ]
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Task B"].id in by_name["Task A"].predecessor_ids


def test_duplicate_predecessor_is_deduplicated_with_warning():
    content = build_workbook_bytes(
        [
            ["Task A", "", "Alice", 1, ""],
            ["Task B", "", "Bob", 1, "Task A;Task A"],
        ]
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    by_name = {t.name: t for t in result.tasks}
    assert by_name["Task B"].predecessor_ids == [by_name["Task A"].id]
    assert any("Task A" in w for w in result.warnings)


def test_self_dependency_is_rejected():
    content = build_workbook_bytes([["Task A", "", "Alice", 1, "Task A"]])
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_SELF_DEPENDENCY" in codes


def test_cycle_is_rejected_at_import():
    from app.domain.errors import DependencyCycleError
    from app.scheduler.engine import compute_schedule

    content = build_workbook_bytes(
        [
            ["Task A", "", "Alice", 1, "Task B"],
            ["Task B", "", "Bob", 1, "Task A"],
        ]
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    with pytest.raises(DependencyCycleError):
        compute_schedule(result.tasks, date(2026, 9, 7))


def test_formula_in_required_field_is_rejected():
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 1, ""]],
        formula_cells={(1, 1): "=1+1"},  # formula in "Задача" for the first data row
    )
    with pytest.raises(ImportValidationError) as exc_info:
        ExcelImportService().parse(content, filename="plan.xlsx")
    codes = [d["code"] for d in exc_info.value.details]
    assert "IMPORT_FORMULA_NOT_SUPPORTED" in codes


def test_optional_start_not_before_column_is_restored():
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 1, ""]],
        headers=("Задача", "Описание", "Исполнитель", "Длительность", "Предшественники", "Не ранее"),
    )
    # append the date manually since build_workbook_bytes only appends the base row list
    import openpyxl

    wb = openpyxl.load_workbook(__import__("io").BytesIO(content))
    ws = wb.active
    ws.cell(row=2, column=6).value = date(2026, 10, 1)
    buffer = __import__("io").BytesIO()
    wb.save(buffer)

    result = ExcelImportService().parse(buffer.getvalue(), filename="plan.xlsx")
    assert result.tasks[0].start_not_before == date(2026, 10, 1)


def test_calculated_columns_are_ignored_not_source_of_truth():
    headers = (
        "Задача",
        "Описание",
        "Исполнитель",
        "Длительность",
        "Предшественники",
        "Плановая трудоёмкость, ч",
        "Дата начала",
        "Дата окончания",
    )
    content = build_workbook_bytes(
        [["Task A", "", "Alice", 1, "", 999, "2099-01-01", "2099-01-01"]],
        headers=headers,
    )
    result = ExcelImportService().parse(content, filename="plan.xlsx")
    task = result.tasks[0]
    # Effort is always duration*8, never read from the sheet.
    assert task.planned_effort_hours == 8
    # start/end are placeholders here; the scheduler (not the sheet) decides them.
    assert task.start_date != date(2099, 1, 1)


def test_more_than_max_tasks_is_rejected():
    rows = [[f"Task {i}", "", "Alice", 1, ""] for i in range(501)]
    content = build_workbook_bytes(rows)
    with pytest.raises(TooManyTasksError):
        ExcelImportService().parse(content, filename="plan.xlsx")


def test_oversized_file_is_rejected():
    huge = b"0" * (5 * 1024 * 1024 + 1)
    with pytest.raises(FileTooLargeError):
        ExcelImportService().parse(huge, filename="plan.xlsx")


def test_non_xlsx_extension_is_rejected():
    with pytest.raises(UnsupportedFileTypeError):
        ExcelImportService().parse(b"whatever", filename="plan.csv")


def test_bad_workbook_bytes_are_rejected():
    with pytest.raises(InvalidWorkbookError):
        ExcelImportService().parse(b"not a real xlsx file", filename="plan.xlsx")


def test_filename_is_never_used_as_a_filesystem_path():
    content = build_workbook_bytes([["Task A", "", "Alice", 1, ""]])
    result = ExcelImportService().parse(content, filename="../../etc/passwd.xlsx")
    assert "/" not in result.project_name
    assert ".." not in result.project_name
