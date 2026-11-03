import openpyxl

wb = openpyxl.load_workbook(r"C:\Users\win10\Downloads\FieldOps_Complete_Functional_Testing_Report_Retest.xlsx", data_only=True)

# 1. Defect status
ws_ret = wb["Retest_Summary"]
print("=" * 80)
print("DEFECTS IN RETEST SUMMARY:")
print("=" * 80)
retest_defects = []
for r in list(ws_ret.iter_rows(values_only=True))[14:41]:
    if any(r) and r[0] and str(r[0]).startswith("DEF-"):
        retest_defects.append({
            "defect": r[0],
            "severity": r[1],
            "summary": r[2],
            "retest_status": r[3]
        })
        print(f"{r[0]} [{r[1]}]: {r[3]} -> {r[2]}")

print("\n" + "=" * 80)
print("FAILED CASES IN MODULE SHEETS:")
print("=" * 80)
failed_cases = []
for sheet in wb.sheetnames:
    if sheet in ["Executive_Summary", "Retest_Summary", "Summary_Breakdown", "Defect_Log", "Blocked_Skipped", "API_Coverage", "Test_Env_Data"]:
        continue
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        continue
    headers = [str(c).strip() if c is not None else "" for c in rows[0]]
    retest_status_idx = None
    status_idx = None
    tc_id_idx = None
    desc_idx = None
    
    for i, h in enumerate(headers):
        hl = h.lower()
        if "retest_status" in hl or "retest status" in hl:
            retest_status_idx = i
        elif "status" in hl and status_idx is None:
            status_idx = i
        if "id" in hl or "tc" in hl:
            if tc_id_idx is None:
                tc_id_idx = i
        if "scenario" in hl or "desc" in hl or "title" in hl or "name" in hl:
            if desc_idx is None:
                desc_idx = i
            
    for r_idx, r in enumerate(rows[1:], start=2):
        r_status = str(r[status_idx]).strip() if status_idx is not None and status_idx < len(r) and r[status_idx] is not None else ""
        r_retest = str(r[retest_status_idx]).strip() if retest_status_idx is not None and retest_status_idx < len(r) and r[retest_status_idx] is not None else ""
        
        tc_id = r[tc_id_idx] if tc_id_idx is not None and tc_id_idx < len(r) else ""
        desc = r[desc_idx] if desc_idx is not None and desc_idx < len(r) else ""
        
        # Check if failed in retest or baseline
        is_retest_failed = "fail" in r_retest.lower()
        is_baseline_failed = "fail" in r_status.lower()
        
        if is_retest_failed or (is_baseline_failed and not r_retest):
            failed_cases.append({
                "sheet": sheet,
                "row": r_idx,
                "tc_id": tc_id,
                "desc": desc,
                "baseline_status": r_status,
                "retest_status": r_retest,
                "full_row": r
            })

print(f"Total failed cases: {len(failed_cases)}")
for f in failed_cases:
    print(f"[{f['sheet']}] {f['tc_id']}: {f['desc']} | Baseline: {f['baseline_status']} | Retest: {f['retest_status']}")

