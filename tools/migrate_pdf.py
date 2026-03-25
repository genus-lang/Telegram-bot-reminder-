import pdfplumber
import os
import re
import json

from src.database import db

def parse_pdf_to_db():
    pdf_path = "src/timetable/time_table.pdf.pdf"
    print(f"Opening {pdf_path}...")
    
    # Store results in memory first
    schedules = {}
    
    times_map = {
        0: "08:00",
        1: "09:00",
        2: "10:00",
        3: "11:00",
        4: "12:00",
        5: "13:00",
        6: "14:00",
        7: "15:00",
        8: "16:00",
        9: "17:00",
        10: "18:00"
    }

    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    full_day_map = {"Mon":"Monday", "Tue":"Tuesday", "Wed":"Wednesday", "Thu":"Thursday", "Fri":"Friday"}

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            
            # Use real newlines to split lines
            lines = text.split("\n")
            header_line = ""
            for line in lines[:5]:
                if "Batch" in line or "Semester" in line or "M.Tech" in line:
                    header_line = line
                    break
                    
            if not header_line: continue
            
            # Determine Branch
            branch = "UNKNOWN"
            for b in ["CSE", "ECE", "MAE", "MEA", "MNC"]:
                if b in header_line:
                    branch = b
                    if branch == "MEA": branch = "MAE"
                    break
                    
            # Determine Year
            year = 0
            if "2025-29" in header_line: year = 1
            elif "2024-28" in header_line: year = 2
            elif "2023-27" in header_line: year = 3
            elif "2022-26" in header_line: year = 4
            elif "M.Tech" in header_line:
                year = 5
            
            if branch == "UNKNOWN":
                continue
                
            doc_id = f"{branch}_Year{year}"
            if doc_id not in schedules:
                schedules[doc_id] = {"_id": doc_id, "branch": branch, "year": year, "groups": {"1": {}, "2": {}}}
                for d in full_day_map.values():
                    schedules[doc_id]["groups"]["1"][d] = []
                    schedules[doc_id]["groups"]["2"][d] = []

            tables = page.extract_tables()
            if not tables: continue
            table = tables[0]
            
            current_day = None
            
            # Process rows, skipping the header row
            for row in table[1:]:
                col0 = row[0]
                if col0 and col0.strip() in days:
                    current_day = full_day_map[col0.strip()]
                    
                if not current_day: continue
                
                # Each column 1..11 corresponds to period 0..10
                for col_idx in range(1, len(row)):
                    if col_idx - 1 > 10: break
                    
                    cell_text = row[col_idx]
                    if not cell_text or not str(cell_text).strip():
                        continue
                        
                    cell_text = str(cell_text).strip()
                    
                    # Split on REAL newlines (pdfplumber uses actual \n)
                    parts = [p.strip() for p in cell_text.split("\n") if p.strip()]
                    if len(parts) < 2: continue  # Needs at least subject and room/faculty
                    
                    # Figure out target groups
                    target_groups = []
                    if "Group 1" in cell_text or "Group1" in cell_text:
                        target_groups = ["1"]
                    elif "Group 2" in cell_text or "Group2" in cell_text:
                        target_groups = ["2"]
                    else:
                        target_groups = ["1", "2"]  # Entire class
                        
                    # Find subject (usually second line, or first if no group/class header)
                    subject = parts[0]
                    if "class" in subject.lower() or "Group" in subject:
                        subject = parts[1] if len(parts) > 1 else subject
                        
                    # Find room and faculty (usually last line)
                    bottom_line = parts[-1]
                    room_str = bottom_line
                    faculty_str = "—"
                    
                    # Commonly: "C104 PKT" -> room="C104", faculty="PKT"
                    rm_fac = bottom_line.split(" ")
                    if len(rm_fac) > 1:
                        room_str = rm_fac[0]
                        faculty_str = " ".join(rm_fac[1:])
                        
                    start_time = times_map[col_idx - 1]
                    
                    lecture_obj = {
                        "start": start_time,
                        "subject": subject,
                        "room": room_str,
                        "faculty": faculty_str
                    }
                    
                    for g in target_groups:
                        # Prevent duplicate entry
                        existing_starts = [x["start"] for x in schedules[doc_id]["groups"][g][current_day]]
                        if start_time not in existing_starts:
                            schedules[doc_id]["groups"][g][current_day].append(lecture_obj)

    print(f"Extracted {len(schedules)} unique branches/years!")
    
    # Count total classes for verification
    total = 0
    for doc_id, data in schedules.items():
        doc_count = 0
        for g_id in ["1", "2"]:
            for d in data["groups"][g_id]:
                doc_count += len(data["groups"][g_id][d])
                data["groups"][g_id][d].sort(key=lambda x: x["start"])
        total += doc_count
        print(f"  {doc_id}: {doc_count} class slots")
    
    print(f"\nTotal class entries across all documents: {total}")
    
    timetable_col = db["timetable"]
    
    # Drop old data and re-insert
    timetable_col.delete_many({})
    
    count = 0
    for doc_id, data in schedules.items():
        timetable_col.insert_one(data)
        count += 1
        
    print(f"\n✅ Successfully migrated {count} Timetable profiles to MongoDB Atlas!")

if __name__ == "__main__":
    parse_pdf_to_db()
