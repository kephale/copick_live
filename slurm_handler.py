import subprocess
import json
import sys

def run_ssh_command(slurm_host, command):
    ssh_command = f"ssh {slurm_host] '{command}'"
    result = subprocess.run(ssh_command, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr

def submit_job(sbatch_script):
    with open('temp_sbatch_script.sh', 'w') as f:
        f.write(sbatch_script)
    
    stdout, stderr = run_ssh_command("cat > temp_sbatch_script.sh")
    if stderr:
        return None, stderr
    
    stdout, stderr = run_ssh_command("sbatch temp_sbatch_script.sh")
    if stderr:
        return None, stderr
    
    job_id = stdout.strip().split()[-1]
    return job_id, None

def check_job_status(job_id):
    stdout, stderr = run_ssh_command(f"squeue -j {job_id} -h")
    if stderr:
        return None, stderr
    
    if stdout.strip():
        return "RUNNING", None
    else:
        return "COMPLETED", None

if __name__ == "__main__":
    action = sys.argv[1]
    slurm_host = sys.argv[2]
    if action == "submit":
        sbatch_script = sys.argv[3]
        job_id, error = submit_job(sbatch_script)
        print(json.dumps({"job_id": job_id, "error": error}))
    elif action == "status":
        job_id = sys.argv[3]
        status, error = check_job_status(job_id)
        print(json.dumps({"status": status, "error": error}))
