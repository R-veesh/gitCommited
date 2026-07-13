from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


class ExcelGenerator:
    COLUMNS = {
        "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8
    }

    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    SECTION_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
    TASK_HEADER_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    THIN_BORDER = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    def __init__(self, assigned_by: str = "Altitude", breaks: list[tuple[str, str, str]] = None):
        self.assigned_by = assigned_by
        self.breaks = breaks or [
            ("10.30am", "11.00am", "Tea break"),
            ("1.00pm", "2.00pm", "Lunch break"),
            ("4.00pm", "4.20pm", "Tea break"),
        ]

    def generate(self, date_str: str, task_summaries: list[dict],
                 repo_commits: dict[str, list[dict]], output_path: str, merge_existing: bool = False):
        path = Path(output_path)

        if merge_existing and path.exists():
            existing = self._load_existing_tasks(path)
            all_tasks = existing + task_summaries
            all_tasks.sort(key=lambda t: t.get("start_time", "9.00am"))
            task_summaries = all_tasks
            try:
                path.unlink()
            except PermissionError:
                raise PermissionError(
                    f"Cannot overwrite '{output_path}' — file is open in another program. "
                    f"Close it and try again."
                )
        else:
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    raise PermissionError(
                        f"Cannot overwrite '{output_path}' — file is open in another program. "
                        f"Close it and try again."
                    )

        wb = Workbook()
        ws = wb.active
        ws.title = "Task Log"
        ws.sheet_properties.pageSetUpPr = None

        col_widths = {2: 14, 3: 14, 4: 50, 5: 16, 6: 18, 7: 16, 8: 16}
        for col, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width

        row = 1

        row = self._write_date_header(ws, row, date_str)
        row = self._write_shift_start(ws, row)
        row = self._write_desk_cleanup(ws, row)
        row = self._write_day_plan(ws, row)
        row = self._write_break_rows(ws, row)
        row = self._write_tasks_header(ws, row)
        row = self._write_task_rows(ws, row, task_summaries, repo_commits)
        row = self._write_overall_productivity(ws, row, task_summaries)
        row += 1
        row = self._write_delegated_header(ws, row)
        row = self._write_delegated_productivity(ws, row, task_summaries)

        wb.save(output_path)
        return output_path

    def _load_existing_tasks(self, path: Path) -> list[dict]:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        ws = wb.active
        tasks = []
        in_task_section = False
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
            vals = [str(v) if v is not None else "" for v in row]
            col_d = vals[3] if len(vals) > 3 else ""
            col_b = vals[1] if len(vals) > 1 else ""
            if "Tasks completed by myself" in col_d:
                in_task_section = True
                continue
            if "Overall Productivity" in col_b:
                break
            if in_task_section and col_b and (len(vals) > 3 and vals[3]):
                tasks.append({
                    "start_time": vals[1] if len(vals) > 1 else "",
                    "end_time": vals[2] if len(vals) > 2 else "",
                    "task": vals[3] if len(vals) > 3 else "",
                    "priority": vals[4] if len(vals) > 4 and vals[4] else "Medium",
                    "status": vals[6] if len(vals) > 6 and vals[6] else "Completed",
                    "productivity": float(vals[7]) if len(vals) > 7 and vals[7] else 0.8,
                })
        return tasks

    def _write_date_header(self, ws, row: int, date_str: str) -> int:
        cell = ws.cell(row=row, column=self.COLUMNS["B"], value=date_str)
        cell.font = Font(bold=True, size=12, color="FFFFFF")
        cell.fill = self.HEADER_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.merge_cells(start_row=row, start_column=self.COLUMNS["B"],
                       end_row=row, end_column=self.COLUMNS["H"])
        for c in range(self.COLUMNS["B"], self.COLUMNS["H"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
            ws.cell(row=row, column=c).fill = self.HEADER_FILL
        return row + 1

    def _write_shift_start(self, ws, row: int) -> int:
        headers = ["Start time", "End time", "Task Logs"]
        for i, h in enumerate(headers):
            col = self.COLUMNS["B"] + i
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.SECTION_FILL
            cell.border = self.THIN_BORDER
        for c in range(self.COLUMNS["B"], self.COLUMNS["H"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
            ws.cell(row=row, column=c).fill = self.SECTION_FILL
        return row + 1

    def _write_desk_cleanup(self, ws, row: int) -> int:
        ws.cell(row=row, column=self.COLUMNS["B"], value="8.30am").border = self.THIN_BORDER
        ws.cell(row=row, column=self.COLUMNS["C"]).border = self.THIN_BORDER
        cell = ws.cell(row=row, column=self.COLUMNS["D"], value="Clean the desk // Checked email")
        cell.border = self.THIN_BORDER
        for c in range(self.COLUMNS["E"], self.COLUMNS["H"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
        return row + 1

    def _write_day_plan(self, ws, row: int) -> int:
        ws.cell(row=row, column=self.COLUMNS["B"], value="8.30am").border = self.THIN_BORDER
        ws.cell(row=row, column=self.COLUMNS["C"], value="8.45am").border = self.THIN_BORDER
        cell = ws.cell(row=row, column=self.COLUMNS["D"], value="Prepared the Day Plan")
        cell.border = self.THIN_BORDER
        for c in range(self.COLUMNS["E"], self.COLUMNS["H"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
        return row + 1

    def _write_break_rows(self, ws, row: int) -> int:
        for start, end, label in self.breaks:
            ws.cell(row=row, column=self.COLUMNS["B"], value=start).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["C"], value=end).border = self.THIN_BORDER
            cell = ws.cell(row=row, column=self.COLUMNS["D"], value=label)
            cell.border = self.THIN_BORDER
            for c in range(self.COLUMNS["E"], self.COLUMNS["H"] + 1):
                ws.cell(row=row, column=c).border = self.THIN_BORDER
            row += 1
        return row

    def _write_tasks_header(self, ws, row: int) -> int:
        headers = ["", "", "Tasks completed by myself",
                    "Priority Level", "Assigned by", "Task Status", "Productivity (%)"]
        for i, h in enumerate(headers):
            col = self.COLUMNS["B"] + i
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True, size=11)
            cell.fill = self.TASK_HEADER_FILL
            cell.border = self.THIN_BORDER
        return row + 1

    def _write_task_rows(self, ws, row: int, summaries: list[dict],
                         repo_commits: dict[str, list[dict]]) -> int:
        if not summaries:
            ws.cell(row=row, column=self.COLUMNS["D"],
                    value="No commits found for this date").border = self.THIN_BORDER
            for c in range(self.COLUMNS["B"], self.COLUMNS["H"] + 1):
                ws.cell(row=row, column=c).border = self.THIN_BORDER
            return row + 1

        for i, summary in enumerate(summaries):
            start_time = summary.get("start_time", "9.00am")
            end_time = summary.get("end_time", "5.00pm")

            ws.cell(row=row, column=self.COLUMNS["B"], value=start_time).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["C"], value=end_time).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["D"],
                    value=summary.get("task", "")).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["E"],
                    value=summary.get("priority", "Medium")).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["F"],
                    value=self.assigned_by).border = self.THIN_BORDER
            ws.cell(row=row, column=self.COLUMNS["G"],
                    value=summary.get("status", "Completed")).border = self.THIN_BORDER

            prod = summary.get("productivity", 0.8)
            prod_cell = ws.cell(row=row, column=self.COLUMNS["H"], value=prod)
            prod_cell.number_format = '0.0'
            prod_cell.border = self.THIN_BORDER

            ws.row_dimensions[row].height = 30
            row += 1

        return row

    def _write_overall_productivity(self, ws, row: int, summaries: list[dict]) -> int:
        cell = ws.cell(row=row, column=self.COLUMNS["B"], value="Overall Productivity (Myself)")
        cell.font = Font(bold=True)
        cell.fill = self.SECTION_FILL
        cell.border = self.THIN_BORDER
        ws.merge_cells(start_row=row, start_column=self.COLUMNS["B"],
                       end_row=row, end_column=self.COLUMNS["G"])
        for c in range(self.COLUMNS["B"], self.COLUMNS["G"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
            ws.cell(row=row, column=c).fill = self.SECTION_FILL

        if summaries:
            avg = sum(s.get("productivity", 0.8) for s in summaries) / len(summaries)
            prod_cell = ws.cell(row=row, column=self.COLUMNS["H"], value=round(avg, 1))
        else:
            prod_cell = ws.cell(row=row, column=self.COLUMNS["H"], value=0.0)
        prod_cell.number_format = '0.0'
        prod_cell.border = self.THIN_BORDER
        prod_cell.fill = self.SECTION_FILL
        prod_cell.font = Font(bold=True)

        return row + 1

    def _write_delegated_header(self, ws, row: int) -> int:
        headers = ["", "", "Delegated / Assigned Task",
                    "Team member", "Assigned by", "Task Status", "Productivity (%)"]
        for i, h in enumerate(headers):
            col = self.COLUMNS["B"] + i
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True, size=11)
            cell.fill = self.TASK_HEADER_FILL
            cell.border = self.THIN_BORDER
        return row + 1

    def _write_delegated_productivity(self, ws, row: int, summaries: list[dict]) -> int:
        cell = ws.cell(row=row, column=self.COLUMNS["B"], value="Overall Productivity (Assigned)")
        cell.font = Font(bold=True)
        cell.fill = self.SECTION_FILL
        cell.border = self.THIN_BORDER
        ws.merge_cells(start_row=row, start_column=self.COLUMNS["B"],
                       end_row=row, end_column=self.COLUMNS["G"])
        for c in range(self.COLUMNS["B"], self.COLUMNS["G"] + 1):
            ws.cell(row=row, column=c).border = self.THIN_BORDER
            ws.cell(row=row, column=c).fill = self.SECTION_FILL

        prod_cell = ws.cell(row=row, column=self.COLUMNS["H"], value=0.0)
        prod_cell.number_format = '0.0'
        prod_cell.border = self.THIN_BORDER
        prod_cell.fill = self.SECTION_FILL
        prod_cell.font = Font(bold=True)

        return row + 1
