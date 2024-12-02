#!/tool/pandora64/.package/python-3.11.1/bin/python3  
  
import os  
import sys  
import MySQLdb  
from datetime import datetime  
import subprocess  
  
def check_user_permission():  
    if os.getenv('USER') not in ["shgfxdv", "nanyang2"]:  
        sys.exit()  
  
def validate_input_args():  
    if len(sys.argv) != 5:  
        print("Wrong input parameters")  
        sys.exit()  
  
def connect_to_db():  
    try:  
        return MySQLdb.connect(  
            host="atlvmysqldp19.amd.com",  
            user="gfxinfra",  
            password="gfxdv180422",  
            database="gfx_reg"  
        )  
    except MySQLdb.Error:  
        print("Connect to regression.db failed!")  
        sys.exit()  
  
def check_user_db_permission(cursor, input_user_name):  
    cursor.execute(f"SELECT permission FROM user_info_new WHERE user_name='{input_user_name}'")  
    fetch_value = cursor.fetchone()  
    if fetch_value and not fetch_value['permission']:  
        print(f"User {input_user_name} doesn't have the permission to run regression.")  
        sys.exit()  
    elif not fetch_value:  
        print(f"Can't find the permission of user {input_user_name}.")  
        sys.exit()  
  
def validate_input_info(cursor, id, input_user_name, input_proj, input_codeline_reg_name):  
    cursor.execute(f"SELECT * FROM regs_info WHERE id={id}")  
    fetch_value = cursor.fetchone()  
    if not fetch_value or (  
        fetch_value['user_name'] != input_user_name or  
        fetch_value['proj_name'] != input_proj or  
        input_codeline_reg_name != f"{fetch_value['codeline']}_{fetch_value['reg_name']}"  
    ):  
        print("The input info to run regression are not correct.")  
        sys.exit()  
    return fetch_value  
  
def check_configuration_id(fetch_value, tree_path):  
    if fetch_value['proj_name'] != "mariner":  
        with open(f"{tree_path}/configuration_id", 'r') as file:  
            configuration_id = file.read().strip()  
        if not configuration_id.startswith(f"{fetch_value['codeline']}/{fetch_value['p4_branch']}@"):  
            print(f"{configuration_id} in {tree_path}/configuration_id are not {fetch_value['codeline']}/{fetch_value['p4_branch']}.")  
            sys.exit()  
  
def write_start_file(tree_path, profile, id, regs_history_id, time):  
    start_file_path = os.path.join(tree_path, "logs", "kick_off", "start") 
    logs_file_path = os.path.join(tree_path, "logs", "kick_off", f"{time}.log") 
    with open(start_file_path, "w") as fh:  
        fh.write(f"/proj/gfxip-cac/gfxinfra/package/gfxinfra_pkg/ng/bootenv_regress_soc15.py {profile} {id} {regs_history_id} {time} > {logs_file_path}")      

    os.chmod(start_file_path, 0o755)  
    return start_file_path  
  
def submit_bsub_job(input_proj, input_codeline_reg_name, start_file_path):  
    bsub_command = [  
        'lsf_bsub',  
        '-R', "\'select[type==RHEL7_64] rusage[mem=500]\'",  
        '-J', f"{input_proj}_{input_codeline_reg_name}.kick_off",  
        '-q', 'regr_high',  
        '-P', 'gfx-dgpu-ver',  
        start_file_path  
    ] 

    try:  
        result = subprocess.run(bsub_command, check=True, capture_output=True, text=True)  
        print("Job submitted successfully.")  
        print("Output:", result.stdout)  
    except subprocess.CalledProcessError as e:  
        print("Error submitting job:", e)  
        print("Standard Error:", e.stderr)  
  
def main():  
    check_user_permission()  
    validate_input_args()  
  
    input_proj, input_user_name, input_codeline_reg_name, id = sys.argv[1:5]  
  
    dbh = connect_to_db()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
  
    check_user_db_permission(cursor, input_user_name)  
    fetch_value = validate_input_info(cursor, id, input_user_name, input_proj, input_codeline_reg_name)  
  
    tree_path = f"{fetch_value['disk']}/{fetch_value['user_name']}/{fetch_value['proj_name']}/{fetch_value['codeline']}_{fetch_value['reg_name']}"  
    os.chmod(tree_path, 0o750)  
  
    check_configuration_id(fetch_value, tree_path)  
  
    time = datetime.now().strftime("%Y%m%d_%H%M")  
    cursor.execute(f"INSERT INTO regs_history VALUES (NULL, '{fetch_value['proj_name']}', '{fetch_value['user_name']}', '{fetch_value['codeline']}', '{fetch_value['p4_branch']}', '{fetch_value['reg_name']}', '{time}')")  
    dbh.commit()  
  
    os.makedirs(f"{tree_path}/logs/kick_off", exist_ok=True)  
  
    profile = f"{tree_path}/profile.env"  
    cursor.execute(f"SELECT id FROM regs_history WHERE proj_name='{fetch_value['proj_name']}' AND user_name='{fetch_value['user_name']}' AND codeline='{fetch_value['codeline']}' AND p4_branch='{fetch_value['p4_branch']}' AND reg_name='{fetch_value['reg_name']}' ORDER BY id DESC")  
    regs_history_id = cursor.fetchone()['id']  
  
    start_file_path = write_start_file(tree_path, profile, id, regs_history_id, time)  
    submit_bsub_job(input_proj, input_codeline_reg_name, start_file_path)  
  
    cursor.close()  
    dbh.close()  
  
if __name__ == "__main__":  
    main()  
