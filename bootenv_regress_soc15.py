#!/tool/pandora64/.package/python-3.11.1/bin/python3  
  
import os  
import subprocess  
from datetime import datetime  
import sys  
import re  
import time  
import tempfile  
  
def load_env_vars():  
    return {  
        'SIM_BUILD_ONLY': '0',  
        'COMMON_BUILD': '1',  
        'RUN_DV_ONLY': '0',  
        'BYPASS_SANITY_CHECK': '0',  
        'NO_SYNC_TREE': '0',  
        'PRE_CHECK': '0',  
        'PRE_CHECK_OPTS': '',  
        'DEPOT': 'gfxip',  
        'BSUB_OPTS': '',  
        'DJ_OPTS': '',  
        'DJ_RUN_OPTS': '',  
        'DJ_GCF_OPTS': '',  
        'TDL_RUN_OPTS': '',  
        'TDL_OPTS': '',  
        'regression_name': '',  
        'DB_SITE': 'cyb',  
        'RM_IMPORT': '0',  
        'TRG_PATN_FILE': '',  
        'SET_TMP_RUNWS': '0',  
        'SET_TIDY_RUN': '1',  
        'SET_CLEAN_RUN': '0',  
        'SET_NO_CLOBBER': '0',  
        'TRIAGEDJ_OLD': '0',  
        'GFX_LARGE_MEM': '0'  
    }  
  
def update_env_vars(config):  
    os.environ.update(config)  
  
def run_command(command):  
    os.system(command)
  
def setup_logging(logdir, log_timestamp):  
    log_directory = os.path.join(logdir, log_timestamp)  
    os.makedirs(log_directory, exist_ok=True)  
    return log_directory  
  
def write_log_file(filepath, content):  
    with open(filepath, 'w') as f:  
        f.write(content)  
  
def execute_command(command):  
    script_content = "\n".join(command)  
    try:  
        with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.csh') as script_file:  
            script_file.write(script_content)  
            script_path = script_file.name  
            print("Temporary script file created at:", script_path)  
  
        os.chmod(script_path, 0o755)  
        print("Running the script...")  
        result = subprocess.run(['csh', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)  
    except Exception as e:  
        print("An error occurred:", e)  
        result = None 
   
    finally:  
        if os.path.exists(script_path):  
            os.remove(script_path)  
  
    return result  
  
def wait_for_job(job_name):  
    while True:  
        result = subprocess.run(['bjobs', '-J', job_name], capture_output=True, text=True)  
        if 'PEND' not in result.stdout and 'RUN' not in result.stdout:  
            break  
        time.sleep(10)  
  
def sync_tree():  
    if os.environ.get('NO_SYNC_TREE') == '1' or os.environ.get('SIM_BUILD_ONLY') == '1' or os.environ.get('RUN_DV_ONLY') == '1':  
        print("Jump sync_tree")  
    else:  
        change = os.environ.get('change', '')  
        sanity_check = os.environ.get('sanity_check', '')  
        combined_command = [  
            "source /proj/verif_release_ro/cbwa_initscript/current/cbwa_init.csh",  
            f"p4w sync_all @{change} {sanity_check}"  
        ]  
        result = execute_command(combined_command)  
        print(result.stdout)  
  
def send_mail(phase_name, log_suffix, mail_suffix):  
    mail_content_path = f"{os.environ['STEM']}/mail_content_{mail_suffix}.txt"  
    with open(mail_content_path, 'w') as f:  
        f.write(f"To: {os.environ['REG_RESULT_USER']}\n")  
        f.write(f"Subject: {os.environ['regression_name']}.{phase_name} has finished!\n")  
        f.write("Importance: High\n")  
        f.write(f"{os.environ['regression_name']} {phase_name} has finished, you can check the result.\n")  
        f.write("CL info:\n")  
        subprocess.run(['grep', 'change', f"{os.environ['STEM']}/profile.env"], stdout=f)  
        f.write("Regression info:\n")  
    subprocess.run(['/usr/sbin/sendmail', '-bm', '-t'], input=open(mail_content_path).read(), text=True)  
  
def run_profile_env(profile_path):  
    try:  
        env_file = tempfile.NamedTemporaryFile('w', delete=False, suffix='.env')  
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.csh') as temp_script:  
            temp_script.write(f"source {profile_path}\n")  
            temp_script.write(f"env > {env_file.name}\n")  
            script_path = temp_script.name  
        subprocess.run(['csh', script_path], check=True)  
        with open(env_file.name, 'r') as f:  
            for line in f:  
                key, _, value = line.partition("=")  
                os.environ[key.strip()] = value.strip()  
    except Exception as e:  
        print("An error occurred:", e)  
  
def main():  
    if len(sys.argv) < 5:  
        print("Usage: script.py <profile> <id> <his_id> <rtime>")  
        sys.exit(1)  
  
    profile, id, his_id, rtime = sys.argv[1:5]  
  
    print(f"Profile: {profile}")  
    print(f"ID: {id}")  
    print(f"History ID: {his_id}")  
    print(f"Runtime: {rtime}")  
  
    query_result = subprocess.getoutput(  
        f"mysql -h atlvmysqldp19.amd.com --user=gfxinfra --password=gfxdv180422 gfx_reg -Ne \"select run_time from regs_history where id={his_id}\""  
    )  
  
    if rtime not in query_result:  
        print("The runtime doesn't match the history record.")  
        sys.exit()  
  
    update_env_vars(load_env_vars())  
  
    cron_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    write_db_file = "/proj/verif_release_ro/testflow_pkg/58.5.13/src/tools/regression/regression_db_pg.rb"  
    if "_lec_" in profile:  
        write_db_file = "/proj/gfxip-cac/shgfxdv/gfx_reg/script/regression_db_pg_rhea_lec.rb"  
  
    if not os.path.exists(profile):  
        print("ERROR: bootenv_regress_soc15.py requires a profile file to set up the regression environment.")  
        sys.exit()  
  
    print(f"INFO: bootenv_regress_soc15.py: loading configuration from {profile}")  
  
    tree_path = os.path.dirname(profile)  
    os.chdir(tree_path)  
  
    os.system(f"/tool/pandora64/hdk-2021/1.1/bin/dos2unix {profile}")  
    run_profile_env(profile)  
  
    if os.environ['SET_CLEAN_RUN'] == '1':  
        os.environ['DJ_RUN_OPTS'] = re.sub(r'(--clean)?', ' --clean', os.environ['DJ_RUN_OPTS'])  
  
    if os.environ['SET_TIDY_RUN'] == '1' and '_lec_' not in profile:  
        os.environ['DJ_RUN_OPTS'] = re.sub(r'(--tidy)?', ' --tidy', os.environ['DJ_RUN_OPTS'])  
  
    os.environ['DJ_OPTS'] = re.sub(r'-m\s+\d+', '', os.environ['DJ_OPTS'])  
  
    if os.environ['SET_TMP_RUNWS'] == '1':  
        os.environ['DJ_RUN_OPTS'] = re.sub(r'(--tmp_runws)?', ' --tmp_runws', os.environ['DJ_RUN_OPTS'])  
  
    if '--log_cmd_output none' not in os.environ['DJ_OPTS']:  
        os.environ['DJ_OPTS'] += ' --log_cmd_output none'  
  
    change = os.environ.get('change', 0)  
    rev_change = os.environ.get('rev_change', 0)  
  
    print(f"change = {change}, rev_change = {rev_change}\n")  
  
    if change == 0:  
        print("INFO: bootenv_regress_soc15.py: no change in environment variables\n")  
        sys.exit()  
  
    if rev_change == 0 and '_lec_' in profile:  
        print("INFO: bootenv_regress_soc15.py: no rev_change in environment variables\n")  
        sys.exit()  
  
    logdir = f"{os.environ['STEM']}/logs/{os.environ['DATABASE']}/logs"  
    log_directory = setup_logging(logdir, rtime)  
  
    regress_log = f"{log_directory}/tree_regress.log"  
    if not os.path.exists(regress_log):  
        write_log_file(regress_log, f"REGRESS_TIME {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nSYNC_TIME {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nSYNC_CHANGE {change}.\n")  
  
    profile_log = f"{log_directory}/profile.log"  
    write_log_file(profile_log, f"cron_time {cron_time}\ncshrc_time {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n")  
  
    bkill_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    print(f"INFO: bootenv_regress_soc15.py: killing jobs matching {os.environ['regression_name']}")  
  
    jobs = ['sim_build', 'command_build', 'run_dv', 'triagedj', 'sendmail', 'tree_size']  
    for job in jobs:  
        run_command(f"/tool/pandora/bin/lsf_bkill -J {os.environ['regression_name']}.{job}")  
  
    with open(profile_log, 'a') as f:  
        f.write(f"bkill_time {bkill_time}\n")  
  
    if os.environ['RM_IMPORT'] == '1':  
        print("INFO: bootenv_regress_soc15.py: removing import files")  
        os.system(f"rm -rf {os.environ['STEM']}/import/*")  
  
    if os.environ['SIM_BUILD_ONLY'] == '1' or os.environ['RUN_DV_ONLY'] == '1' or os.environ['SET_NO_CLOBBER'] == '1':  
        print("Jump common build, don't remove the out dir")  
    else:  
        print(f"Running: rm -rf {os.environ['STEM']}/out_del")  
        run_command(f"mv {os.environ['STEM']}/out {os.environ['STEM']}/out_del")  
        run_command(f"rm -rf {os.environ['STEM']}/out_del")  
  
    if '_lec_' in profile:  
        print(f"Running: rm -rf {os.environ['STEM']}/out_del")  
        run_command(f"mv {os.environ['STEM']}/out {os.environ['STEM']}/out_del")  
        run_command(f"rm -rf {os.environ['STEM']}/out_del") 
  
    if os.environ['PRE_CHECK'] == '1':  
        print("INFO: bootenv_regress_soc15.py: running pre_check")  
        run_command(['pre_check', os.environ['PRE_CHECK_OPTS']])  
  
    sync_tree()  
  
    if os.environ['NO_SYNC_TREE'] == '0' and '_lec_' in profile:  
        print("Sync golden LEC tree ...")  
        run_command(f"p4w sync_all @{change}" + "-bypass_sanity_check" if os.environ['BYPASS_SANITY_CHECK'] == '1' else "")  
  
    sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    with open(profile_log, 'a') as f:  
        f.write(f"sync_time {sync_time}\n")  
  
    os.chdir(os.getenv('STEM', 'default_stem'))  
    os.makedirs(f"{os.environ['STEM']}/out", exist_ok=True)  
    os.makedirs(f"{log_directory}/cov", exist_ok=True)  
  
    parse_report_path = f"{os.environ['STEM']}/parse_report.csh"  
    with open(parse_report_path, 'w') as f:  
        f.write("#DO NOT TOUCH THIS FILE ! This is automatically generated by bootenv_regress_soc.csh ...\n")  
        f.write("echo Parsing DJ Triage report ...\n")  
        f.write("pushd `pwd`\n")  
        f.write(f"cd {log_directory};\n")  
  
    os.chmod(parse_report_path, 0o755)  
  
    trg_patn_file = os.getenv('TRG_PATN_FILE', '')  
    patt_opt = f"-patterns {trg_patn_file}" if os.path.isfile(trg_patn_file) else ""  
  
    with open(parse_report_path, 'a') as f:  
        f.write(f"perl /proj/verif_release_ro/gc_infra/current/src/tools/scripts/triagedj/bin/TriageDJ.pl -results_dir agent_logs.run_dv/test_results\n")  
        f.write("echo Done : Parsing DJ Triage report\n")  
    
    
    print("Starting dj")  
  
    os.environ.pop('DJ_ABORT_NO_ERROR', None)  
    RHEL_TYPE = 'RHEL7_64'  
    bsub_opts = os.environ['BSUB_OPTS']  
    dj_opts = os.environ['DJ_OPTS'] 
    tdl_run_opts = os.environ['TDL_RUN_OPTS']  
    

    def run_build_phase(phase_name, log_suffix, additional_opts):  
        print(f"{phase_name} log is: {logdir}/{rtime}/{os.environ['TREE']}.{log_suffix}.log") 
         
        csh_command = [
            "source /proj/gfx_meth_user0/nanyang2/mi400/gfxip_mi400_rhel8_test/profile.env",
            "source /proj/gfxip-cac/shgfxdv/gfx_reg/script/postgresql.mi400.env"
        ]

        dj_command = f"/tool/pandora/bin/lsf_bsub -J {os.environ['regression_name']}.{phase_name} -R 'select[type=={RHEL_TYPE}] rusage[mem=3000:duration=1440]' {bsub_opts} dj -J lsf -m 150 {dj_opts} -f {write_db_file} -l {logdir}/{rtime}/{os.environ['TREE']}.{log_suffix}.log -o {logdir}/{rtime}/agent_logs.{log_suffix} {additional_opts}"

        csh_command.append(dj_command) 

        pg_host = os.getenv('PGHOST', 'default_host')    
        pg_database = os.getenv('PGDATABASE', 'default_database')    
        pg_user = os.getenv('PGUSER', 'default_user')    
        pg_password = os.getenv('PGPASSWORD', 'default_password')    

        print(f"Database: {pg_host} {pg_database} {pg_user} {pg_password}")    
        print(f"write db using {write_db_file}")  
        print(f"command is : {csh_command}")  
  
        execute_command(csh_command)  
        wait_for_job(f"{os.environ['regression_name']}.{phase_name}")  
        print(f"Finished {phase_name}.")  
  
    if os.environ['COMMON_BUILD'] == '1':  
        run_build_phase('common_build', 'common_build', f"{tdl_run_opts} -a build")  
  
    if os.environ['SIM_BUILD_ONLY'] == '1':  
        run_build_phase('sim_build', 'sim_build', f"{tdl_run_opts} -a build_sim")  
  
    if os.environ['RUN_DV_ONLY'] == '1':  
        run_build_phase('run_dv', 'run_dv', f"{tdl_run_opts} -a run_phase")  
  
    if os.environ['RUN_DV_ONLY'] == '0' and os.environ['SIM_BUILD_ONLY'] == '0' and os.environ['COMMON_BUILD'] == '0':  
        print("ERROR: bootenv_regress_soc15.py: no build or run_dv option is set")  
        sys.exit()  
  
    print("INFO: bootenv_regress_soc15.py: finished")  
  
    dj_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
    with open(f"{logdir}/{rtime}/profile.log", 'a') as f:  
        f.write(f"dj_time {dj_time}\n")  
  
    if (os.environ['RUN_DV_ONLY'] == '0' and os.environ['SIM_BUILD_ONLY'] == '0') or os.environ['RUN_DV_ONLY'] == '1' or (os.environ['SIM_BUILD_ONLY'] == '1' and os.environ['RUN_DV_ONLY'] == '1'):  
        print("After the run_dv test on lsf has been finished, TriageDJ.pl will be executed automatically.")  
        run_command(f"/tool/pandora/bin/lsf_bsub -w \"ended({os.environ['regression_name']}.run_dv)\" -J {os.environ['regression_name']}.triagedj -R \"select[type=={RHEL_TYPE}] rusage[mem=100:duration=1440]\" {os.environ['BSUB_OPTS']} /tool/pandora64/bin/tcsh {os.environ['STEM']}/parse_report.csh")  
  
    run_command(f"rm -rf {os.environ['STEM']}/mail_content_triage.txt")  
    
    parse_triage_path = f"{os.environ['STEM']}/parse_triage.sh"

    os.environ['REG_RESULT_USER'] = "nanyang2@amd.com"  
    if os.environ['REG_RESULT_USER']:  
        print("After triage on lsf has been finished, send result will be executed automatically.")  
        with open(f"{os.environ['STEM']}/mail_triage.txt", 'w') as f:  
            f.write(f"To: {os.environ['REG_RESULT_USER']}\nSubject: {os.environ['regression_name']}.triagedj has finished!\nImportance: High\n{os.environ['regression_name']} triagedj has finished, you can check the result.\n")  
            f.write("CL info:\n")  
            subprocess.run(['grep', 'change', f"{os.environ['STEM']}/profile.env"], stdout=f)  
            f.write("Regression info:\n") 

        with open(f"parse_triage_path", 'w') as f:  
            f.write('#! /bin/bash\n')  
            f.write('total=$(grep "Total tests" $1/$2/triage.txt | awk \'{print $3}\')\n')  
            f.write('pass=$(grep "Passing tests:" $1/$2/triage.txt | awk \'{print $3}\')\n')  
            f.write('fail=$(grep "Failing tests" $1/$2/triage.txt | awk \'{print $3}\')\n')  
            f.write('pend=$(grep "Pending tests" $1/$2/triage.txt | awk \'{print $3}\')\n')  
            f.write('echo "        Total tests nums: $total" >>  $3/mail_triage.txt\n')  
            f.write('echo "        Passing tests nums: $pass" >>  $3/mail_triage.txt\n')  
            f.write('echo "        Failing tests nums: $fail" >>  $3/mail_triage.txt\n')  
            f.write('echo "        Pending tests nums: $pend" >>  $3/mail_triage.txt\n')  
            f.write('pass_rate=$(echo "scale=2; $pass/$total*100" | bc)\n')  
            f.write('echo "        Passing rate: $pass_rate %" >>  $3/mail_triage.txt\n')  
            f.write('echo "Failing test list: $fail" >> $3/mail_triage.txt\n')  
            f.write(f"cat {logdir}/{rtime}/triage.csv | grep FAILED | tr ',' ' ' | awk '{{print $2}}' | sed 's/^/        /g' >> {os.environ['STEM']}/mail_triage.txt\n")  
            f.write('echo "Pending test list: $pend" >> $3/mail_triage.txt\n')  
            f.write(f"cat {logdir}/{rtime}/triage.csv | grep UNKNOWN | tr ',' ' ' | awk '{{print $2}}' | sed 's/^/        /g' >> {os.environ['STEM']}/mail_triage.txt\n")  
            f.write(f"/usr/sbin/sendmail -bm -t < {os.environ['STEM']}/mail_content_name.txt")  

        os.chmod(parse_triage_path, 0o755) 

    if os.environ['SIM_BUILD_ONLY'] == '1':  
        send_mail('sim_build', 'sim_build', 'sim_build')  
  
    if os.environ['COMMON_BUILD'] == '1':  
        send_mail('common_build', 'common_build', 'common_build')  
  
    if os.environ['RUN_DV_ONLY'] == '0':  
        send_mail('run_dv', 'run_dv', 'run_dv')  
        print("After the run_dv test on lsf has been finished, TriageDJ.pl will be executed automatically.") 
        run_command(parse_report_path)
        run_command(parse_triage_path)
        run_command(f"/tool/pandora/bin/lsf_bsub -w \"ended({os.environ['regression_name']}.triagedj)\" -J {os.environ['regression_name']}.tree_size -R \"select[type=={RHEL_TYPE}] rusage[mem=100:duration=1440]\" {os.environ['BSUB_OPTS']} /tool/pandora64/bin/tcsh /proj/gfxip-cac/shgfxdv/gfx_reg/script/update_tree_size.csh {id}")  
  
if __name__ == "__main__":  
    main()  

