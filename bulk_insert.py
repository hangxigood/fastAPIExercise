# bulk_insert.py
import requests
from datetime import datetime, timedelta

base_url = "http://localhost:8080"
start_date = datetime(2024, 1, 1)

def create_student(student_num):
    # Calculate date (each student gets a consecutive date)
    current_date = start_date + timedelta(days=student_num-2)
    date_str = current_date.strftime("%d/%m/%Y")
    
    student_data = {
        "studentID": f"{student_num}",
        "studentName": f"student{student_num}",
        "courseName": f"course{student_num}",
        "Date": date_str
    }
    
    try:
        response = requests.post(f"{base_url}/student", json=student_data)
        if response.status_code == 201:
            print(f"Successfully created student{student_num}")
        else:
            print(f"Failed to create student{student_num}: {response.json()}")
    except Exception as e:
        print(f"Error creating student{student_num}: {str(e)}")

def main():
    for i in range(2, 26):  # Create students 2 through 25
        create_student(i)

if __name__ == "__main__":
    main()