import pexpect
import os
import sys
import termios
import tty
import select
import re
import json
import logging

logging.basicConfig(level=logging.DEBUG, filename='slurm_handler.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def set_terminal_mode():
    oldtty = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())
    return oldtty

def reset_terminal_mode(oldtty):
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)

def run_ssh_command(hostname, command):
    ssh_command = f"ssh {hostname} '{command}'"
    child = pexpect.spawn(ssh_command)
    child.logfile_read = sys.stdout.buffer
    
    output = ""
    while True:
        index = child.expect([pexpect.TIMEOUT, pexpect.EOF])
        output += child.before.decode('utf-8')
        if index == 1:
            break
    
    child.close()
    return output.strip()

def submit_job(slurm_host, sbatch_script):
    logging.debug(f"Submitting job to {slurm_host}")
    logging.debug(f"Sbatch script content:\n{sbatch_script}")
    
    with open('temp_sbatch_script.sh', 'w') as f:
        f.write(sbatch_script)
    logging.debug("Wrote sbatch script to temp_sbatch_script.sh")
    
    scp_command = f"scp temp_sbatch_script.sh {slurm_host}:temp_sbatch_script.sh"
    os.system(scp_command)
    
    output = run_ssh_command(slurm_host, "sbatch temp_sbatch_script.sh")
    
    if not output:
        logging.error("No output from sbatch command")
        return None, "No output from sbatch command"
    
    try:
        job_id = output.strip().split()[-1]
        logging.info(f"Job submitted successfully. Job ID: {job_id}")
        return job_id, None
    except IndexError:
        logging.error(f"Unexpected sbatch output format: {output}")
        return None, f"Unexpected sbatch output format: {output}"

def check_job_status(slurm_host, job_id):
    output = run_ssh_command(slurm_host, f"squeue -j {job_id} -h")
    
    if output.strip():
        return "RUNNING", None
    else:
        return "COMPLETED", None

def get_job_output(slurm_host, job_id):
    output = run_ssh_command(slurm_host, f"cat slurm-{job_id}.out")
    return output, None

if __name__ == "__main__":
    script_path = os.path.abspath(__file__)
    logging.info(f"Script path: {script_path}")
    
    logging.info(f"slurm_handler.py called with arguments: {sys.argv}")
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Insufficient arguments"}))
        sys.exit(1)

    action = sys.argv[1]
    slurm_host = sys.argv[2]

    if action == "submit":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Missing sbatch script"}))
            sys.exit(1)
        sbatch_script = sys.argv[3]
        job_id, error = submit_job(slurm_host, sbatch_script)
        print(json.dumps({"job_id": job_id, "error": error}))
    elif action == "status":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Missing job ID"}))
            sys.exit(1)
        job_id = sys.argv[3]
        status, error = check_job_status(slurm_host, job_id)
        print(json.dumps({"status": status, "error": error}))
    elif action == "output":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Missing job ID"}))
            sys.exit(1)
        job_id = sys.argv[3]
        output, error = get_job_output(slurm_host, job_id)
        print(json.dumps({"output": output, "error": error}))        
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(1)
