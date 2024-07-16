import subprocess
import json
import sys
import logging
import os

logging.basicConfig(level=logging.DEBUG, filename='slurm_handler.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def run_ssh_command(slurm_host, command):
    ssh_command = f"ssh {slurm_host} '{command}'"
    logging.debug(f"Executing SSH command: {ssh_command}")
    result = subprocess.run(ssh_command, shell=True, capture_output=True, text=True)
    logging.debug(f"SSH command result - stdout: {result.stdout}, stderr: {result.stderr}")
    return result.stdout, result.stderr

def submit_job(slurm_host, sbatch_script):
    logging.debug(f"Submitting job to {slurm_host}")
    with open('temp_sbatch_script.sh', 'w') as f:
        f.write(sbatch_script)
    logging.debug("Wrote sbatch script to temp_sbatch_script.sh")
    
    stdout, stderr = run_ssh_command(slurm_host, "cat > temp_sbatch_script.sh < temp_sbatch_script.sh")
    if stderr:
        logging.error(f"Error copying script to remote host: {stderr}")
        return None, f"Error copying script to remote host: {stderr}"
    
    stdout, stderr = run_ssh_command(slurm_host, "sbatch temp_sbatch_script.sh")
    if stderr:
        logging.error(f"Error submitting job: {stderr}")
        return None, f"Error submitting job: {stderr}"
    
    if not stdout.strip():
        logging.error("No output from sbatch command")
        return None, "No output from sbatch command"
    
    try:
        job_id = stdout.strip().split()[-1]
        logging.info(f"Job submitted successfully. Job ID: {job_id}")
        return job_id, None
    except IndexError:
        logging.error(f"Unexpected sbatch output format: {stdout}")
        return None, f"Unexpected sbatch output format: {stdout}"

def check_job_status(slurm_host, job_id):
    stdout, stderr = run_ssh_command(slurm_host, f"squeue -j {job_id} -h")
    if stderr:
        return None, f"Error checking job status: {stderr}"
    
    if stdout.strip():
        return "RUNNING", None
    else:
        return "COMPLETED", None

if __name__ == "__main__":
    script_path = os.path.abspath(__file__)
    logging.info(f"Script path: {script_path}")
    print(f"Script path: {script_path}")
    
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
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(1)
