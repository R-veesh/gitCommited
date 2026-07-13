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

    def __init__(self, assigned_by: str = "Altitude"):
        self.assigned_by = assigned_by

    def generate(self, date_str: str, task_summaries: list[dict],
                 repo_commits: dict[str, list[dict]], output_path: str):
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
        row = self._write_tasks_header(ws, row)
        row = self._write_task_rows(ws, row, task_summaries, repo_commits)
        row = self._write_overall_productivity(ws, row, task_summaries)
        row += 1
        row = self._write_delegated_header(ws, row)
        row = self._write_delegated_productivity(ws, row, task_summaries)

        wb.save(output_path)
        return output_path

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
        cell = ws.cell(row=row, column=self.COLUMNS["D"], value="Clean the desk ∥ Checked email")
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
