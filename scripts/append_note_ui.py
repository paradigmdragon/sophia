import sys
import json
from sophia_kernel.executor.executor import execute_skill

def main():
    try:
        # Args: script_name, title, body, tags_csv, date
        if len(sys.argv) < 5:
            raise ValueError("Insufficient arguments. Usage: python append_note_ui.py <title> <body> <tags> <date>")
            
        title = sys.argv[1]
        body = sys.argv[2]
        tags_str = sys.argv[3]
        date = sys.argv[4]
        
        tags = tags_str.split(",") if tags_str else []
        
        data = {
            "namespace": "notes",
            "data": {
                "title": title,
                "body": body,
                "tags": tags,
                "refs": {"date": date, "source": "ui"}
            }
        }
        
        # Execute skill
        result = execute_skill("memory.append", "0.1.0", data)
        
        print(json.dumps({"status": "ok", "result": result}))
        
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
