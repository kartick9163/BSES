from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import connection
from datetime import datetime
import os, re, json, jwt, datetime, bcrypt
from datetime import datetime, timedelta
from . import process_bill, extract_amount_in_words


JWT_SECRET = 'arodek'
JWT_ALGORITHM = 'HS256'

@csrf_exempt
def upload_bill(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid request method", "status": False, "code": 0}, status=400)

    try:
        if not request.FILES:
            return JsonResponse({"msg": "No files uploaded", "status": False, "code": 0}, status=400)

        file_path = settings.MEDIA_ROOT
        os.makedirs(file_path, exist_ok=True)
        
        uploaded_files = request.FILES.getlist('file')
        typeOfBills = request.POST.get('typeOfBills')
        modeOfBills = request.POST.get('modeOfBills')
        companyName = request.POST.get('companyName')
        month_input = request.POST.get('month')
        year = request.POST.get('year')
        uploaded_by = request.POST.get('uploaded_by')

        if not all([typeOfBills, modeOfBills, companyName, month_input, year, uploaded_by]):
            return JsonResponse({"msg": "All fields are required", "status": False, "code": 0}, status=400)

        # Convert month format (e.g. '2025-04') to 'APR'
        try:
            month = month_input.split('-')[1]
            month_map = {'01': 'JAN', '02': 'FEB', '03': 'MAR', '04': 'APR', '05': 'MAY', '06': 'JUN','07': 'JUL', '08': 'AUG', '09': 'SEP', '10': 'OCT', '11': 'NOV', '12': 'DEC'}
            month = month_map.get(month, month)
        except:
            return JsonResponse({"msg": "Invalid month format", "status": False, "code": 0}, status=400)

        # Validate all files first
        for uploaded_file in uploaded_files:
            if not (uploaded_file.name.lower().endswith('.pdf') and uploaded_file.content_type == 'application/pdf'):
                return JsonResponse({"msg": "Only PDF files are allowed", "status": False, "code": 0}, status=400)

        saved_files = []
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y%m%d%H%M%S")
        # formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

        for uploaded_file in uploaded_files:
            counter = 0
            base_name = os.path.splitext(uploaded_file.name)[0]
            new_file_name = formatted_datetime+'_'+uploaded_file.name
            file_save_path = os.path.join(file_path, new_file_name)

            # If needed, rename file to avoid overwriting
            # while os.path.exists(file_save_path):
            #     counter += 1
            #     new_file_name = f"{base_name}_{counter}.pdf"
            #     file_save_path = os.path.join(file_path, new_file_name)

            with open(file_save_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            saved_files.append(new_file_name)

            file_location = settings.MEDIA_ROOT + new_file_name

            # OCR and data extraction
            ocr_output = process_bill(file_location)
            amount = extract_amount_in_words(ocr_output)

            # Match "Provisional energy" data pattern
            pattern = re.compile(r"Provisional energy\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)")            
            match = pattern.search(ocr_output)

            if match:
                hsn_code = match.group(1)
                energy_raw = match.group(2).replace(',', '')
                try:
                    energy = int(energy_raw)
                    energy_mwh = energy / 1000
                except ValueError:
                    energy_mwh = 0

                rate = match.group(4)
            else:
                hsn_code, energy_mwh, rate = None, 0, None

            # Save record to DB
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT name FROM user_master WHERE id = %s', [uploaded_by])
                    uploader_name = cursor.fetchone()[0]
                    cursor.execute("""
                        INSERT INTO file_information 
                        (file_name, file_path, type_of_bills, mode_of_bills, company_name, 
                        month, year, hsn_code, energy_mwh, amount, uploaded_by, status, uploader_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        new_file_name, file_path, typeOfBills, modeOfBills,
                        companyName, month, year, hsn_code, energy_mwh, amount, uploaded_by, 'uploaded', uploader_name
                    ])
            except Exception as db_err:
                return JsonResponse({"msg": f"Database error: {str(db_err)}", "status": False})
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        return JsonResponse({
            "data": {
                "file_name": new_file_name,
                "hsn_code": hsn_code,
                "energy": energy_mwh,
                "rate": rate,
                "amount": amount,
                "uploaded_date": formatted_datetime,
                "msg1": "Energy Value is matched with the supporting document."
            },
            "msg": "File Uploaded Successfully",
            "status": True,
            "code": 1
        }, status=200)

    except Exception as e:
        return JsonResponse({"msg": f"Unexpected error: {str(e)}", "status": False, "code": 0})

@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request", "code": 0})

    try:
        reqbody = json.loads(request.body.decode('utf-8'))
        email = reqbody.get('email')
        password = reqbody.get('password')

        if not email or not password:
            return JsonResponse({"msg": "Email and password are required", "code": 0})

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.id, u.email_id, u.name, u.password, r.role, u.mobile_no, m.module_name
                FROM user_master u
                INNER JOIN role_master r ON u.role_id = r.id
                LEFT JOIN module_master m ON r.id = m.role_id
                WHERE BINARY u.email_id = %s
            """, (email,))
            results = cursor.fetchall()

            if not results:
                return JsonResponse({"msg": "Invalid credentials", "code": 0})

            user_id, user_email, name, db_password, role_name, mobile_no, _ = results[0]

            
            if not bcrypt.checkpw(password.encode('utf-8'), db_password.encode('utf-8')):
                return JsonResponse({"msg": "Invalid credential", "code": 0})

            module_names = list(set(row[6] for row in results if row[6]))

            jwt_payload = {
                'user_id': user_id,
                'email': user_email,
                'exp': datetime.utcnow() + timedelta(hours=3)
            }
            token = jwt.encode(jwt_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

            cursor.execute("UPDATE user_master SET token = %s WHERE id = %s", (token, user_id))

        return JsonResponse({
            "msg": "Login successful",
            "result": {
                "id": user_id,
                "name": name,
                "email": user_email,
                "modules": module_names,
                "rolename": role_name,
                "mobile": mobile_no
            },
            "code": 1
        })

    except Exception as e:
        return JsonResponse({"msg": "Something went wrong","error": str(e),"code": 0})

@csrf_exempt
def create_user(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"}, status=405)

    try:
        reqbody = json.loads(request.body.decode('utf-8'))

        role_id = reqbody.get('role_id')
        name = reqbody.get('name')
        email_id = reqbody.get('email_id')
        password = reqbody.get('password')

        if not all([role_id, name, email_id, password]):
            return JsonResponse({"msg": "All fields are required", "code": 0})

        # Check if email already exists
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM user_master WHERE BINARY email_id = %s", (email_id,))
            if cursor.fetchone():
                return JsonResponse({"msg": "Email already exists", "code": 0})

        # Encrypt password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with connection.cursor() as cursor:
            # insert_query = """
            #     INSERT INTO user_master (role_id, name, email_id, password)
            #     VALUES (%s, %s, %s, %s)
            # """
            cursor.execute("""
                INSERT INTO user_master (role_id, name, email_id, password)
                VALUES (%s, %s, %s, %s)
            """, (role_id, name, email_id, hashed_pw))

        return JsonResponse({"msg": "User created successfully", "code": 1}, status=200)

    except Exception as e:
        return JsonResponse({"msg": "Something went wrong", "error": str(e), "code": 0})

@csrf_exempt
def bill_details(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"}, status=400)

    try:
        reqbody = json.loads(request.body.decode('utf-8'))

        uploaded_by = reqbody.get('uploaded_by')
        bill_type = reqbody.get('bill_type')
        bill_mode = reqbody.get('bill_mode')
        company_name = reqbody.get('company_name')
        start_date = reqbody.get('start_date')  # Format: 'YYYY-MM-DD'
        end_date = reqbody.get('end_date')      # Format: 'YYYY-MM-DD'
        page = reqbody.get('page')
        
        limit = 5
        offset = (page - 1) * limit

        if not uploaded_by:
            return JsonResponse({"msg": "uploaded_by is required"}, status=400)

        where_clauses = ["uploaded_by = %s"]
        params = [uploaded_by]

        if bill_type:
            where_clauses.append("type_of_bills = %s")
            params.append(bill_type)
        if bill_mode:
            where_clauses.append("mode_of_bills = %s")
            params.append(bill_mode)
        if company_name:
            where_clauses.append("company_name = %s")
            params.append(company_name)


        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return JsonResponse({"msg": "Invalid start_date format. Use YYYY-MM-DD"}, status=400)

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)
            except ValueError:
                return JsonResponse({"msg": "Invalid end_date format. Use YYYY-MM-DD"}, status=400)

        if start_dt and end_dt:
            where_clauses.append("uploaded_date BETWEEN %s AND %s")
            params.extend([start_dt, end_dt])
        elif start_dt:
            where_clauses.append("uploaded_date >= %s")
            params.append(start_dt)
        elif end_dt:
            where_clauses.append("uploaded_date <= %s")
            params.append(end_dt)

        where_sql = " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) FROM file_information WHERE {where_sql}"
        with connection.cursor() as cursor:
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

        total_pages = (total_count + limit - 1) // limit

        select_query = f"""
            SELECT * FROM file_information WHERE {where_sql}
            LIMIT %s OFFSET %s
        """
        paginated_params = params + [limit, offset]

        with connection.cursor() as cursor:
            cursor.execute(select_query, paginated_params)
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            
        exclude_fields = {'uploaded_by', 'file_path'}
        records = [
            {k: v for k, v in zip(columns, row) if k not in exclude_fields}
            for row in rows
        ]

        return JsonResponse({
            "total_records": total_count,
            "total_pages": total_pages,
            "records": records
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"msg": "Invalid JSON format"}, status=400)
    except Exception as e:
        return JsonResponse({"msg": str(e)})

@csrf_exempt
def change_pass(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"})

    try:
        reqbody = json.loads(request.body.decode('utf-8'))
        email_id = reqbody.get('email_id')
        new_password = reqbody.get('new_password')

        if not email_id or not new_password:
            return JsonResponse({"msg": "Email and new password are required"})

        with connection.cursor() as cursor:
            cursor.execute("""SELECT COUNT(*) FROM user_master WHERE BINARY email_id = %s""", [email_id])
            count = cursor.fetchone()[0]

        if count == 0:
            return JsonResponse({"msg": "User not found"})

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE user_master SET password = %s WHERE BINARY email_id = %s
            """, [hashed_password, email_id])

        return JsonResponse({"msg": "Password updated successfully", "status":True, "code":1},status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})
    
@csrf_exempt
def typeofbills_master(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"})

    try:
        with connection.cursor() as c:
            c.execute('SELECT type FROM typeofbills_master')
            result = c.fetchall()

        # Convert list of tuples to list of values
        types = [row[0] for row in result]

        return JsonResponse({"msg": types}, status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})
    
@csrf_exempt
def modeofbills_master(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"})

    try:
        with connection.cursor() as c:
            c.execute('SELECT mode FROM modeofbills_master')
            result = c.fetchall()

        # Convert list of tuples to list of values
        types = [row[0] for row in result]

        return JsonResponse({"msg": types}, status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})
    
@csrf_exempt
def companyname_master(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"})

    try:
        with connection.cursor() as c:
            c.execute('SELECT company_name FROM company_name_master')
            result = c.fetchall()

        # Convert list of tuples to list of values
        types = [row[0] for row in result]

        return JsonResponse({"msg": types}, status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})
    
@csrf_exempt
def role_master(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"}, status=400)

    try:
        with connection.cursor() as c:
            c.execute('SELECT id, role FROM role_master')
            result = c.fetchall()

        roles = [
            {
                "id": row[0],
                "role": row[1]
            }
            for row in result
        ]

        return JsonResponse({"roles": roles}, status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})

@csrf_exempt
def user_master(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"}, status=400)

    try:
        with connection.cursor() as c:
            c.execute('''
                SELECT u.id, u.name, u.email_id, u.role_id, r.role
                FROM user_master u
                INNER JOIN role_master r ON u.role_id = r.id
            ''')
            result = c.fetchall()
        users = [
            {
                "id": row[0],
                "name": row[1],
                "email_id": row[2],
                "role_id": row[3],
                "role_name": row[4]
            }
            for row in result
        ]

        return JsonResponse({"users": users, "code":1}, status=200)

    except Exception as e:
        return JsonResponse({"msg": str(e)})
    
@csrf_exempt
def last_five_bill_details(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid Request"})

    try:
        reqbody = json.loads(request.body.decode('utf-8'))
        uploaded_id = reqbody.get('uploaded_id')

        if not uploaded_id:
            return JsonResponse({"msg": "uploaded_id is required"})

        with connection.cursor() as c:
            c.execute('SELECT * FROM file_information WHERE uploaded_by = %s ORDER BY id DESC LIMIT 5', [uploaded_id])
            result = c.fetchall()
            columns = [col[0] for col in c.description]

        records = [dict(zip(columns, row)) for row in result]

        return JsonResponse({"msg": records}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"msg": "Invalid JSON format"})
    except Exception as e:
        return JsonResponse({"msg": str(e)})

@csrf_exempt
def dashboard_count(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid request method", "status": False}, status=405)

    try:
        reqbody = json.loads(request.body.decode('utf-8'))
        user_id = reqbody.get('userid')

        if not user_id:
            return JsonResponse({"msg": "User ID is required", "status": False}, status=400)

        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM file_information WHERE status = %s AND uploaded_by = %s', ['uploaded', user_id])
            upload_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM file_information WHERE status = %s AND uploaded_by = %s', ['approved', user_id])
            approved_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM file_information WHERE status = %s AND uploaded_by = %s', ['verified', user_id])
            verified_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM file_information WHERE status = %s AND uploaded_by = %s', ['failed', user_id])
            failed_count = cursor.fetchone()[0]

        return JsonResponse({
            "data": {
                "upload": upload_count,
                "approved": approved_count,
                "verified":verified_count,
                "failed":failed_count
            },
            "status": True
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"msg": "Invalid JSON format", "status": False}, status=400)
    except Exception as e:
        return JsonResponse({"msg": "Server error", "error": str(e), "status": False})

@csrf_exempt
def update_profile(request):
    if request.method != 'POST':
        return JsonResponse({"msg": "Invalid request method", "status": False})

    try:
        reqbody = json.loads(request.body.decode('utf-8'))
        email = reqbody.get('email')
        name = reqbody.get('name')
        mobile_no = reqbody.get('phone')

        if not email:
            return JsonResponse({"msg": "Email is missing", "status": False})

        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM user_master WHERE BINARY email_id = %s', [email])
            user_exists = cursor.fetchone()[0]

        if user_exists != 1:
            return JsonResponse({"msg": "User not found", "status": False})

        update_fields = []
        params = []

        if name:
            update_fields.append("name = %s")
            params.append(name)

        if mobile_no:
            # hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            update_fields.append("mobile_no = %s")
            params.append(mobile_no)

        if update_fields:
            query = f"UPDATE user_master SET {', '.join(update_fields)} WHERE BINARY email_id = %s"
            params.append(email)
            with connection.cursor() as cursor:
                cursor.execute(query, params)
            return JsonResponse({"msg": "Profile updated successfully", "status": True})
        else:
            return JsonResponse({"msg": "No data to update", "status": False})

    except Exception as e:
        return JsonResponse({"msg": "Server error", "error": str(e), "status": False})
    
