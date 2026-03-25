import sys
from src.database import db

def test_mongodb_timetable():
    timetable_col = db["timetable"]
    
    docs = list(timetable_col.find())
    if not docs:
        print("❌ DATABASE EMPTY: Migration failed or pointing to wrong Atlas cluster!")
        sys.exit(1)
        
    with open("test_results.txt", "w", encoding="utf-8") as f:
        f.write(f"🔍 Found {len(docs)} documents in the timetable collection.\n\n")
        
        btech_docs = [d for d in docs if d.get("year", 0) <= 4]
        mtech_docs = [d for d in docs if d.get("year", 0) > 4]
        
        f.write(f"📘 B.Tech entries: {len(btech_docs)}\n")
        f.write(f"📗 M.Tech entries: {len(mtech_docs)}\n\n")
        
        branches = {"CSE": [], "ECE": [], "MAE": [], "MNC": []}
        missing = []
        total_classes = 0
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
        f.write("=" * 50 + "\n")
        f.write("📘 B.TECH VERIFICATION (Years 1-4)\n")
        f.write("=" * 50 + "\n")
        
        for doc in sorted(btech_docs, key=lambda x: x["_id"]):
            id_str = doc.get("_id")
            branch = doc.get("branch", "?")
            year = doc.get("year", 0)
            groups = doc.get("groups", {})
            
            classes_in_doc = 0
            
            for g in ["1", "2"]:
                group_data = groups.get(g, {})
                for day in days:
                    lectures = group_data.get(day, [])
                    classes_in_doc += len(lectures)
                        
            total_classes += classes_in_doc
            
            if classes_in_doc == 0:
                missing.append(id_str)
                f.write(f"  ❌ {id_str} -> 0 classes! FAILED!\n")
            else:
                if branch in branches:
                    branches[branch].append(year)
                f.write(f"  ✅ {id_str} -> {classes_in_doc} class slots mapped\n")
        
        f.write(f"\n{'=' * 50}\n")
        f.write("📗 M.TECH VERIFICATION (Year 5 - Informational)\n")
        f.write("=" * 50 + "\n")
        
        for doc in sorted(mtech_docs, key=lambda x: x["_id"]):
            id_str = doc.get("_id")
            groups = doc.get("groups", {})
            classes_in_doc = 0
            for g in ["1", "2"]:
                group_data = groups.get(g, {})
                for day in days:
                    lectures = group_data.get(day, [])
                    classes_in_doc += len(lectures)
            total_classes += classes_in_doc
            status = "✅" if classes_in_doc > 0 else "⚠️ (empty)"
            f.write(f"  {status} {id_str} -> {classes_in_doc} class slots\n")

        f.write(f"\n{'=' * 50}\n")
        f.write("📊 BRANCH COVERAGE SUMMARY\n")
        f.write("=" * 50 + "\n")
        
        all_covered = True
        for branch_name, years_found in branches.items():
            years_found.sort()
            missing_years = [y for y in [1, 2, 3, 4] if y not in years_found]
            if missing_years:
                f.write(f"  ❌ {branch_name}: Years {years_found} found, MISSING Years {missing_years}\n")
                all_covered = False
            else:
                f.write(f"  ✅ {branch_name}: All 4 years covered ✓\n")
        
        f.write(f"\n{'=' * 50}\n")
        f.write(f"📈 TOTAL: {len(docs)} documents, {total_classes} class slot references\n")
        f.write("=" * 50 + "\n")
        
        if missing:
            f.write(f"\n🚨 B.Tech entries with ZERO classes: {missing}\n")
        elif not all_covered:
            f.write(f"\n⚠️ WARNING: Some branches are missing year coverage!\n")
        else:
            f.write("\n🎉 ALL B.TECH YEARS & BRANCHES VERIFIED: 100% SUCCESSFUL!\n")
    
    print("Test results written to test_results.txt")

if __name__ == "__main__":
    test_mongodb_timetable()
