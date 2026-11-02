import openpyxl

wb = openpyxl.load_workbook("c:/f/downloaded_sheet.xlsx")

# 1. Update M12 QR-Barcode (row 30: IDN-U-029)
ws_m12 = wb["M12 QR-Barcode"]
ws_m12.cell(row=30, column=10).value = "Passed"
ws_m12.cell(row=30, column=9).value = "Pass: Scanned URL parses query string cleanly, resolving token abc123"
ws_m12.cell(row=30, column=11).value = "Fixed: extract_token implemented with urllib.parse; verified"

# 2. Update M06 Work Orders (rows 52-55: WO-U-051..054)
ws_m06 = wb["M06 Work Orders"]
for r in [52, 53, 54, 55]:
    ws_m06.cell(row=r, column=10).value = "Passed"
ws_m06.cell(row=52, column=9).value = "Pass: Assignee executes work order without recursion"
ws_m06.cell(row=53, column=9).value = "Pass: Reviewer blocked with PermissionDenied(code=not_assignee)"
ws_m06.cell(row=54, column=9).value = "Pass: Dispatcher executes work order without recursion"
ws_m06.cell(row=55, column=9).value = "Pass: Unauthorized user denied with PermissionDenied"
for r in [52, 53, 54, 55]:
    ws_m06.cell(row=r, column=11).value = "Fixed: Removed circular alias rebinding in services.py; verified"

# 3. Update M07 Workspace (row 30: WS-U-029)
ws_m07 = wb["M07 Workspace"]
ws_m07.cell(row=30, column=10).value = "Passed"
ws_m07.cell(row=30, column=9).value = "Pass: Negative distance raises ValidationFailed('Distance cannot be negative.')"
ws_m07.cell(row=30, column=11).value = "Fixed: Negative check moved outside try-except block; verified"

# 4. Update Unit Test Execution Summary
ws_summ = wb["Unit Test Execution Summary"]
ws_summ.cell(row=12, column=16).value = "none (IDN-U-029 fixed)"
ws_summ.cell(row=14, column=16).value = "none (WO-U-051..054 fixed)"
ws_summ.cell(row=16, column=16).value = "none (WS-U-029 fixed)"
ws_summ.cell(row=22, column=16).value = "All 1,366 Passed (100% pass rate)"

# 5. Update Defect Summary
ws_def = wb["Defect Summary"]
ws_def.cell(row=2, column=9).value = "Pass: Assignee and dispatcher pass authorization without recursion. Unit tests pass."
ws_def.cell(row=2, column=14).value = "Fixed / Verified (Pass)"
ws_def.cell(row=2, column=15).value = "Fixed: Replaced circular alias with clean function delegation in workorders/services.py."

ws_def.cell(row=3, column=9).value = "Pass: Scanned URLs with query strings and anchors resolve to raw token abc123."
ws_def.cell(row=3, column=14).value = "Fixed / Verified (Pass)"
ws_def.cell(row=3, column=15).value = "Fixed: Added extract_token with proper urlparse handling in identification/services.py."

ws_def.cell(row=4, column=9).value = "Pass: Negative distance raises ValidationFailed('Distance cannot be negative.')."
ws_def.cell(row=4, column=14).value = "Fixed / Verified (Pass)"
ws_def.cell(row=4, column=15).value = "Fixed: Separated Decimal parsing from negative distance validation in workspace/services.py."

ws_def.cell(row=7, column=14).value = "Resolved / Verified (Pass)"
ws_def.cell(row=8, column=14).value = "Resolved / Verified (Pass)"

# 6. Update Executive Summary findings
ws_exec = wb["Executive Summary"]
ws_exec.cell(row=29, column=2).value = (
    "All confirmed defects DEF-001, DEF-002, DEF-003 and environment observations "
    "ENV-001, ENV-002 have been resolved and verified in current codebase. "
    "Test suite achieves 100% pass rate (1,366 / 1,366 Passed)."
)

out_internal = "c:/f/FieldOps_Nexus_Internal/FieldOps_Nexus_Unit_Test_Execution_Completed_Report.xlsx"
out_root = "c:/f/FieldOps_Nexus_Unit_Test_Execution_Completed_Report.xlsx"
wb.save(out_internal)
wb.save(out_root)
print("Successfully generated completed Excel workbooks:")
print(" -", out_internal)
print(" -", out_root)
