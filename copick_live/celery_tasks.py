import paramiko
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
import json
import os
import tempfile
from typing import Optional
from celery import Celery, states
import subprocess
import album
from album.api import Album
from album.runner.core.model.coordinates import Coordinates
from datetime import datetime
from copick_live.utils.album_utils import run_solution, install_solution, uninstall_solution, test_solution

import logging
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

celery_app = Celery('album_server', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

album_instance = Album.Builder().build()
album_instance.load_or_create_collection()

@celery_app.task(bind=True)
def submit_slurm_job(self, catalog: str, group: str, name: str, version: str, gpus: int = 0, cpus: int = 24, memory: str = "125G", args: Optional[str] = None):
    logger.info(f"Starting SLURM job submission for {catalog}:{group}:{name}:{version}")
    job_name = f"{catalog}_{group}_{name}_{version}"
    
    args_str = args if args else ""
    album_command = f"album run {catalog}:{group}:{name}:{version} {args_str}"
    
    metadata = {
        'album_solution': f"{catalog}:{group}:{name}:{version}",
        'args': args_str,
        'submission_time': datetime.utcnow().isoformat()
    }

    logger.info(f"Preparing SLURM script for job: {job_name}")
    if gpus > 0:
        sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
#SBATCH --time=24:00:00
#SBATCH --gpus={gpus}
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={memory}

micromamba activate album-nexus

{album_command}
"""
    else:
        sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={memory}

micromamba activate album-nexus

{album_command}
"""

    logger.info(f"SLURM script prepared:\n{sbatch_script}")

    try:
        logger.info("Attempting to connect to SSH tunnel")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('localhost', port=17017)
        logger.info("Successfully connected to SSH tunnel")

        logger.info("Creating temporary file on remote system")
        stdin, stdout, stderr = ssh.exec_command('mktemp')
        temp_script_path = stdout.read().strip().decode()
        logger.info(f"Temporary file created: {temp_script_path}")

        logger.info("Writing SLURM script to temporary file")
        ssh.exec_command(f"cat > {temp_script_path} << EOL\n{sbatch_script}\nEOL")

        logger.info(f"Submitting SLURM job: sbatch {temp_script_path}")
        stdin, stdout, stderr = ssh.exec_command(f'sbatch {temp_script_path}')
        job_id_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode().strip()
        
        logger.info(f"SLURM submission output: {job_id_output}")
        if stderr_output:
            logger.error(f"SLURM submission error: {stderr_output}")
        
        if "Submitted batch job" not in job_id_output:
            raise Exception(f"Failed to submit SLURM job: {stderr_output}\nScript: {sbatch_script}")
        
        job_id = job_id_output.split()[-1]
        logger.info(f"SLURM job submitted successfully with job ID: {job_id}")
        metadata['slurm_job_id'] = job_id
        self.update_state(state=states.PENDING, meta=metadata)
        logger.info(f"Scheduling job status check for job ID: {job_id}")
        check_slurm_job_status.apply_async((self.request.id, job_id), countdown=60, kwargs={'metadata': metadata})
        return metadata
    except Exception as e:
        logger.exception(f"Error submitting SLURM job: {str(e)}")
        raise
    finally:
        if 'ssh' in locals():
            logger.info("Closing SSH connection")
            ssh.close()

@celery_app.task(bind=True)
def check_slurm_job_status(self, celery_task_id: str, job_id: str, metadata: Optional[dict] = None):
    print(f"Checking status for SLURM job ID: {job_id}")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('localhost', port=17017)
    
    stdin, stdout, stderr = ssh.exec_command(f'squeue --job {job_id} --noheader')
    output = stdout.read().decode().strip()
    
    ssh.close()
    
    if metadata is None:
        metadata = {}
    
    if not output:
        print(f"SLURM job {job_id} completed or not found.")
        metadata.update({'status': 'SLURM job completed', 'job_id': job_id})
        celery_app.backend.store_result(celery_task_id, metadata, state=states.SUCCESS)
        return metadata
    else:
        print(f"SLURM job {job_id} is still running.")
        metadata.update({'slurm_job_id': job_id, 'status': 'running'})
        self.update_state(state=states.STARTED, meta=metadata)
        check_slurm_job_status.apply_async((celery_task_id, job_id), countdown=60, kwargs={'metadata': metadata})
        return {'status': 'SLURM job running', 'job_id': job_id}

@celery_app.task(bind=True)
def run_album_solution(self, catalog, group, name, version, args_json):
    logger.info(f"Starting task for solution: {catalog}:{group}:{name}:{version}")
    args_dict = json.loads(args_json)
    args_list = [""]
    for key, value in args_dict.items():
        args_list.extend([f"--{key}", value])
    
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        try:
            result = run_solution(catalog, group, name, version, args_list)
            logger.info(f"Task completed successfully. Output: {output.getvalue()}")
        except Exception as e:
            logger.error(f"Task failed with error: {str(e)}")
            raise
    
    return {"output": output.getvalue(), "result": result}

@celery_app.task
def install_album_solution(catalog, group, name, version):
    return install_solution(catalog, group, name, version)

@celery_app.task
def uninstall_album_solution(catalog, group, name, version):
    return uninstall_solution(catalog, group, name, version)

@celery_app.task
def test_album_solution(catalog, group, name, version):
    return test_solution(catalog, group, name, version)
