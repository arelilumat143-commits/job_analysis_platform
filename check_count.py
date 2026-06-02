from storage.database import db_manager
print(f"当前职位数: {len(db_manager.get_all_jobs())} 条")
