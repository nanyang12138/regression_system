#!/tool/pandora64/.package/python-3.11.1/bin/python3  
  
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, stream_with_context  
import MySQLdb  
from datetime import datetime  
import subprocess  
import os  

app = Flask(__name__)  
app.secret_key = 'your_secret_key'  
  
# Constants  
reg_dir = "/proj/gfxip-cac/shgfxdv/gfx_reg"  
TIME = datetime.now().strftime("%Y-%m-%d")  
  
# Database connection  
def get_db_connection():  
    return MySQLdb.connect(  
        host="atlvmysqldp19.amd.com",  
        user="gfxinfra",  
        password="gfxdv180422",  
        database="gfx_reg"  
    )  
  
@app.route('/', methods=['GET', 'POST'])  
def login():  
    if request.method == 'POST':  
        user = request.form['username'].lower()  
        password = request.form['password']  
  
        dbh = get_db_connection()  
        cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
        cursor.execute(f"SELECT * FROM user_info_new WHERE user_name='{user}'")  
        fetch_user_value = cursor.fetchone()  
  
        if fetch_user_value and fetch_user_value['password'] == password:  
            session['user'] = user  
            session['team_manager'] = fetch_user_value['team_manager']  
            return redirect(url_for('main_menu'))  
        else:  
            flash("Invalid credentials", "danger")  
  
    return render_template('login.html')  
  
@app.route('/register', methods=['GET', 'POST'])  
def register():  
    if request.method == 'POST':  
        user = request.form['username'].lower()  
        email_address = request.form['email'].lower()  
        password = request.form['password']  
        re_password = request.form['re_password']  
        team_manager = request.form['team_manager'].lower()  
  
        if password != re_password:  
            flash("Passwords do not match", "danger")  
            return redirect(url_for('register'))  
  
        if len(password) <= 5:  
            flash("Password length must be greater than 5", "danger")  
            return redirect(url_for('register'))  
  
        if any(sub in password for sub in [user, "234", "345", "456", "678", "798", "987", "543", "good,x"]):  
            flash("Password must not contain your linux account or 1234567890", "danger")  
            return redirect(url_for('register'))  
  
        user_list = subprocess.getoutput("cat /tool/sysadmin/files/mail.aliases")  
        if f"{user}: {email_address}" in user_list and "@amd.com" in email_address:  
            if team_manager not in ["scott", "joey", "ginger", "jia", "simon", "xingxing"]:  
                flash("Please input the right team manager first name", "danger")  
                return redirect(url_for('register'))  
  
            dbh = get_db_connection()  
            cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
            cursor.execute(f"INSERT INTO user_info_new VALUES (NULL, '{user}', '{email_address}', 1, 0, 20, '{team_manager}', '{password}')")  
            dbh.commit()  
  
            flash("You have successfully registered, now you can login to setup and run regressions", "success")  
            return redirect(url_for('login'))  
        else:  
            flash("Please input your own correct email address", "danger")  
  
    return render_template('register.html')  
  
@app.route('/main_menu', methods=['GET', 'POST'])  
def main_menu():  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    if request.method == 'POST':  
        action = request.form['action']  
        if action == 'new_regression':  
            return redirect(url_for('new_regression'))  
        elif action == 'run_regression':  
            return redirect(url_for('regression_list'))  
        elif action == 'quit':  
            session.pop('user', None)  
            return redirect(url_for('login'))  
  
    return render_template('main_menu.html')  
  
@app.route('/new_regression', methods=['GET', 'POST'])  
def new_regression():  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
  
    if request.method == 'POST':  
        session['new_regression'] = {  
            'project': request.form['project'],  
            'codeline': request.form['codeline'],  
            'p4_branch': request.form['p4_branch'],  
            'reg_name': request.form['reg_name'],  
            'bootenv': request.form['bootenv'],  
            'disk': request.form['disk'],  
            'create_time': TIME,  
        }  
        return redirect(url_for('confirm'))  
  
    cursor.execute("SELECT * FROM proj_active WHERE active = 1")  
    projects = cursor.fetchall()  
  
    cursor.execute("SELECT DISTINCT codeline FROM codeline_info")  
    codelines = cursor.fetchall()  
  
    cursor.execute("SELECT DISTINCT p4_branch FROM codeline_info")  
    p4_branches = cursor.fetchall()  
  
    cursor.execute("SELECT DISTINCT disk FROM disk_info")  
    disks = [row['disk'] for row in cursor.fetchall()]  
  
    return render_template('new_regression.html', projects=projects, codelines=codelines, p4_branches=p4_branches, disks=disks)  
  
@app.route('/confirm', methods=['GET', 'POST'])  
def confirm():  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    new_regression = session.get('new_regression', {})  
    if not new_regression:  
        return redirect(url_for('new_regression'))  
  
    if request.method == 'POST':  
        if request.form['confirm'] == 'yes':  
            return redirect(url_for('setup_tree'))  
        else:  
            return redirect(url_for('new_regression'))  
  
    return render_template('confirm.html', new_regression=new_regression)  
  
@app.route('/setup_tree', methods=['GET', 'POST'])  
def setup_tree():  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    user = session['user']  
    new_regression = session.get('new_regression', {})  
    if not new_regression:  
        return redirect(url_for('new_regression'))  
  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
  
    project = new_regression['project']  
    codeline = new_regression['codeline']  
    p4_branch = new_regression['p4_branch']  
    reg_name = new_regression['reg_name']  
    bootenv = new_regression['bootenv']  
    disk = new_regression['disk']  
    create_time = new_regression['create_time']  
  
    cursor.execute(f"INSERT INTO regs_info VALUES (NULL, '{user}', '{project}', '{codeline}', '{p4_branch}', '{reg_name}', '{disk}', '{bootenv}', '{create_time}', 0)")  
    dbh.commit()  
  
    cursor.execute(f"UPDATE user_info_new SET current_num = current_num + 1 WHERE user_name = '{user}'")  
    dbh.commit()  
  
    tree_path = f"{disk}/{user}/{project}/{codeline}_{reg_name}"  
    if os.path.exists(tree_path):  
        flash(f"Dir '{tree_path}' already exists, please check it.", "warning")  
        return redirect(url_for('main_menu'))  
    else:  
        os.makedirs(tree_path, exist_ok=True)  
        os.chmod(tree_path, 0o750)  
        if project in ["mariner", "mariner1"]:  
            flash(f"Please setup tree in {tree_path}", "info")  
            return redirect(url_for('main_menu'))  
        else:  
            return render_template('setup_tree.html', new_regression=new_regression)  
  
@app.route('/stream')  
def stream():  
    def generate():  
        new_regression = session.get('new_regression', {})  
        tree_path = f"{new_regression['disk']}/{session['user']}/{new_regression['project']}/{new_regression['codeline']}_{new_regression['reg_name']}"  
        codeline = new_regression['codeline']  
        p4_branch = new_regression['p4_branch']  
        log_file_path = os.path.join(tree_path, 'setup_log.txt')  
  
        with open(log_file_path, 'w') as log_file:  
            process = subprocess.Popen(  
                ["/bin/bash", "-c", f". /proj/verif_release_ro/cbwa_initscript/current/cbwa_init.bash; cd {tree_path}; p4_mkwa -codeline {codeline} -branch {p4_branch}"],  
                stdout=subprocess.PIPE,  
                stderr=subprocess.PIPE,  
                text=True  
            )  
            for line in iter(process.stdout.readline, ''):  
                log_file.write(line)  
                yield f"data: {line}\n\n"  
            process.stdout.close()  
            process.wait()  
            if process.returncode != 0:  
                for line in iter(process.stderr.readline, ''):  
                    log_file.write(line)  
                    yield f"data: {line}\n\n"  
                process.stderr.close()  
  
        with open(log_file_path, 'r') as log_file:  
            log_content = log_file.read()  
            if any(keyword in log_content for keyword in ['error', 'Error', 'ERROR', 'fatal']):  
                dbh = get_db_connection()  
                cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
                cursor.execute(f"DELETE FROM regs_info WHERE user_name = '{session['user']}' AND proj_name = '{new_regression['project']}' AND codeline = '{codeline}' AND reg_name = '{new_regression['reg_name']}'")  
                dbh.commit()  
                yield "data: Setup encountered errors. Please check the log file.\n\n"  
            else:  
                yield "data: Setup completed successfully.\n\n"  
  
    return Response(stream_with_context(generate()), mimetype='text/event-stream')  
  
@app.route('/regression_list', methods=['GET', 'POST'])  
def regression_list():  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    user = session['user']  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
  
    cursor.execute(f"SELECT * FROM regs_info WHERE user_name='{user}' ORDER BY proj_name")  
    regressions = cursor.fetchall()  
  
    if request.method == 'POST':  
        reg_id = request.form['reg_id']  
        action = request.form['action']  
  
        if action == 'run':  
            run_regression(reg_id)  
        elif action == 'kill':  
            kill_regression(reg_id)  
        elif action == 'open_profile':  
            return redirect(url_for('edit_profile', reg_id=reg_id))  
        elif action == 'delete':  
            return redirect(url_for('confirm_delete', reg_id=reg_id))  
  
        return redirect(url_for('regression_list'))  
  
    status = get_regression_status()  
    return render_template('regression_list.html', regressions=regressions, status=status)  
  
def get_regression_status():  
    lsf_jobs_status = {}  
    lsf_jobs = subprocess.getoutput("lsf_bjobs -w | grep -v agent | grep -v sendmail | grep -E 'kick_off|common_build|sim_build|run_dv|tree_size'").splitlines()  
  
    for job in lsf_jobs:  
        parts = job.split()  
        status = parts[1]  
        job_name = parts[6]  
        alias = parts[6].split('.')[0]  
  
        if "kick_off" in job_name:  
            lsf_jobs_status[alias] = {"color": "GREEN" if status == "RUN" else "BLUE", "jobs_name": "kick_off"}  
        elif "common_build" in job_name:  
            if alias not in lsf_jobs_status:  
                lsf_jobs_status[alias] = {"color": "GREEN" if status == "RUN" else "BLUE", "jobs_name": "common_build"}  
        elif "sim_build" in job_name:  
            if alias not in lsf_jobs_status or lsf_jobs_status[alias]["jobs_name"] == "run_dv":  
                lsf_jobs_status[alias] = {"color": "GREEN" if status == "RUN" else "BLUE", "jobs_name": "sim_build"}  
        elif "run_dv" in job_name:  
            if alias not in lsf_jobs_status:  
                lsf_jobs_status[alias] = {"color": "GREEN" if status == "RUN" else "BLUE", "jobs_name": "run_dv"}  
        elif "tree_size" in job_name:  
            if alias not in lsf_jobs_status:  
                lsf_jobs_status[alias] = {"color": "GREEN" if status == "RUN" else "BLUE", "jobs_name": "tree_size"}  
  
    return lsf_jobs_status  
  
def run_regression(reg_id):  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
    cursor.execute(f"SELECT * FROM regs_info WHERE id={reg_id}")  
    regression = cursor.fetchone()  
  
    project = regression['proj_name']  
    user_name = regression['user_name']  
    codeline = regression['codeline']  
    reg_name = regression['reg_name']  
    disk = regression['disk']  
    p4_branch = regression['p4_branch']  
  
    if project in ["mariner", "mariner1"]:  
        codeline = "mariner"  
        subprocess.run([f"/proj/gfxip-cac/gfxinfra/package/gfxinfra_pkg/ng/start_regression.py", project, user_name, f"{codeline}_{reg_name}", str(reg_id)])  
    else:  
        configuration_id_path = f"{disk}/{user_name}/{project}/{codeline}_{reg_name}/configuration_id"  
        with open(configuration_id_path, 'r') as file:  
            configuration_id = file.read().strip()  
        if configuration_id.startswith(f"{codeline}/{p4_branch}@"):  
            subprocess.run([f"/proj/gfxip-cac/gfxinfra/package/gfxinfra_pkg/ng/start_regression.py", project, user_name, f"{codeline}_{reg_name}", str(reg_id)])  
        else:  
            flash(f"The tree configuration_id is not {codeline}/{p4_branch}, please setup your tree with the right codeline.", "danger")  
  
def kill_regression(reg_id):  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
    cursor.execute(f"SELECT * FROM regs_info WHERE id={reg_id}")  
    regression = cursor.fetchone()  
  
    project = regression['proj_name']  
    codeline = regression['codeline']  
    reg_name = regression['reg_name']  
  
    jobs = [  
        "kick_off", "common_build", "common_build.golden", "common_build.revise",  
        "sim_build", "run_dv", "triagedj", "sim_build.sendmail",  
        "common_build.sendmail", "run_dv.sendmail", "tree_size"  
    ]  
    for job in jobs:  
        subprocess.run(["lsf_bkill", "-J", f"{project}_{codeline}_{reg_name}.{job}"])  
  
@app.route('/edit_profile', methods=['GET', 'POST'])  
def edit_profile():  
    reg_id = request.args.get('reg_id')  
    if reg_id is None:  
        flash("No regression ID provided.", "danger")  
        return redirect(url_for('main_menu'))  
  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
    cursor.execute(f"SELECT * FROM regs_info WHERE id={reg_id}")  
    regression = cursor.fetchone()  
  
    project = regression['proj_name']  
    user_name = regression['user_name']  
    codeline = regression['codeline']  
    reg_name = regression['reg_name']  
    disk = regression['disk']  
    bootenv = regression['bootenv']  
  
    profile_path = f"{reg_dir}/profile/{project}/{codeline}_{reg_name}.env"  
    source_profile_path = f"{disk}/{user_name}/{project}/{codeline}_{reg_name}/profile.env"  
  
    if os.path.exists(profile_path):  
        os.remove(profile_path)  
        flash(f"Existing profile path '{profile_path}' removed.", "warning")  
  
    os.makedirs(os.path.dirname(profile_path), exist_ok=True)  
  
    if not os.path.exists(profile_path):  
        os.symlink(source_profile_path, profile_path)  
    else:  
        flash(f"Failed to remove existing profile path '{profile_path}'.", "danger")  
  
    if request.method == 'POST':  
        content = request.form['content']  
        with open(profile_path, 'w') as fh_profile:  
            fh_profile.write(content)  
        flash("Profile saved successfully.", "success")  
        return redirect(url_for('main_menu'))  
  
    if not os.path.exists(profile_path): 
        with open(profile_path, 'w', newline="\n") as fh_profile:  
            content = [  
            "# PROFILE",  
            "# REG_ID is used to setup cronjob to auto-run, do not delete.",  
            f"# REG_ID: {reg_id}",  
            f"setenv STEM {disk}/{user_name}/{project}/{codeline}_{reg_name};",  
            f"cd $STEM;source /proj/verif_release_ro/cbwa_bootcore/current/bin/_bootenv.csh" +   
            (f" -v {project}" if bootenv == "yes" else ""),  
            "",  
            "setenv DB_SITE  atl",  
            f"setenv TREE     {reg_name}",  
            f"setenv DATABASE {'mobile0' if project in ['mariner', 'mariner1'] else project}",  
            "",  
            "#setenv DJ_GCF_OPTS 'lsf_native:\"-P gfx-dgpu-ver\", select:\"type==RHEL7_64\", mem:800, queue:\"regr_high\"'",  
            "setenv BSUB_OPTS   '-q regr_high -P gfx-dgpu-ver'",  
            "setenv DJ_RUN_OPTS 'here.quick_tests'",  
            "#Please keep '--log_cmd_output none' in your profile to reduce the log size.",  
            "setenv DJ_OPTS     '--log_cmd_output none  -c'",  
            "setenv TDL_RUN_OPTS    ''",  
            "setenv TDL_OPTS    ''",  
            "",  
            "setenv change `lastgood`",  
            "#set rev_change = `lastgood`",  
            "",  
            "setenv SIM_BUILD_ONLY      0",  
            "setenv COMMON_BUILD        1",  
            "setenv RUN_DV_ONLY         0",  
            "setenv BYPASS_SANITY_CHECK 0",  
            "setenv NO_SYNC_TREE        0",  
            "setenv PRE_CHECK           0",  
            "setenv PRE_CHECK_OPT       \"--clean\"",  
            "setenv DEPOT               \"gfxip\"",  
            "setenv RM_IMPORT           0",  
            "setenv TRG_PATN_FILE       \"$STEM\"",  
            f"setenv regression_name     \"{project}_{codeline}_{reg_name}\"",  
            f"set    REG_USER =          ({user_name}) #(xx@amd.com,xxx@amd.com)"  
            ]  
            fh_profile.write("\n".join(content) + "\n")    
  
    with open(profile_path, 'r') as fh_profile:  
        content = fh_profile.read()  
  
    return render_template('edit_profile.html', content=content)  
  
@app.route('/confirm_delete/<int:reg_id>', methods=['GET', 'POST'])  
def confirm_delete(reg_id):  
    if 'user' not in session:  
        return redirect(url_for('login'))  
  
    if request.method == 'POST':  
        if request.form['confirmation'] == 'yes':  
            delete_regression(reg_id)  
            flash("Regression deleted successfully.", "success")  
        else:  
            flash("Deletion cancelled.", "info")  
        return redirect(url_for('regression_list'))  
  
    return render_template('confirm_delete.html', reg_id=reg_id)  
  
def delete_regression(reg_id):  
    dbh = get_db_connection()  
    cursor = dbh.cursor(MySQLdb.cursors.DictCursor)  
    cursor.execute(f"SELECT * FROM regs_info WHERE id={reg_id}")  
    regression = cursor.fetchone()  
  
    project = regression['proj_name']  
    user_name = regression['user_name']  
    codeline = regression['codeline']  
    p4_branch = regression['p4_branch']  
    reg_name = regression['reg_name']  
    disk = regression['disk']  
  
    subprocess.run(["rm", "-rf", f"{disk}/{user_name}/{project}/{codeline}_{reg_name}"])  
    subprocess.run(["rm", "-f", f"{reg_dir}/profile/{project}/{codeline}_{reg_name}.env"])  
    if os.path.isdir(f"{disk}/{user_name}/{project}/{codeline}_{reg_name}") or os.path.exists(f"{reg_dir}/profile/{project}/{codeline}_{reg_name}.env"):  
        flash(f"Deleting tree failed. Please delete dir '{disk}/{user_name}/{project}/{codeline}_{reg_name}' and '{reg_dir}/profile/{project}/{codeline}_{reg_name}.env' manually.", "danger")  
    else:  
        cursor.execute(f"DELETE FROM regs_info WHERE id={reg_id}")  
        dbh.commit()  
        cursor.execute(f"DELETE FROM regs_history WHERE proj_name='{project}' AND user_name='{user_name}' AND codeline='{codeline}' AND p4_branch='{p4_branch}' AND reg_name='{reg_name}'")  
        dbh.commit()  
        cursor.execute(f"SELECT * FROM user_info_new WHERE user_name='{user_name}'")  
        user_info = cursor.fetchone()  
        user_current_num = user_info['current_num']  
        if user_current_num >= 1:  
            user_current_num -= 1  
        cursor.execute(f"UPDATE user_info_new SET current_num={user_current_num} WHERE user_name='{user_name}'")  
        dbh.commit()  
  
if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=5000, debug=True)  
