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
def submit_slurm_job(self, catalog: str, group: str, name: str, version: str, slurm_host: str, gpus: int = 0, cpus: int = 24, memory: str = "125G", args: str = None):
    job_name = f"{catalog}_{group}_{name}_{version}"
    
    args_str = args if args else ""
    album_command = f"album run {catalog}:{group}:{name}:{version} {args_str}"
    
    sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}_%j.out
#SBATCH --error={job_name}_%j.err
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --ntasks-per-node=1
#SBATCH --mem={memory}
{"#SBATCH --gpus=" + str(gpus) if gpus > 0 else ""}

# micromamba activate album-nexus
# {album_command}

micromamba run -n album-nexus {album_command}    
"""

    try:
        result = subprocess.run(['python', 'slurm_handler.py', 'submit', slurm_host, sbatch_script], capture_output=True, text=True)
        
        logging.info(f"slurm_handler.py stdout: {result.stdout}")
        logging.info(f"slurm_handler.py stderr: {result.stderr}")
        
        if result.returncode != 0:
            raise Exception(f"slurm_handler.py failed with return code {result.returncode}. Stderr: {result.stderr}")
        
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON output from slurm_handler.py: {str(e)}. Output was: {result.stdout}")
        
        if output.get('error'):
            raise Exception(f"Failed to submit SLURM job: {output['error']}")
        
        job_id = output.get('job_id')
        if not job_id:
            raise Exception(f"No job ID returned from slurm_handler.py. Output was: {output}")
        
        self.update_state(state=states.SUCCESS, meta={'job_id': job_id})
        return {'job_id': job_id, 'slurm_host': slurm_host}
    
    except Exception as e:
        logging.exception("Error in submit_slurm_job task")
        self.update_state(state=states.FAILURE, meta={
            'exc_type': type(e).__name__,
            'exc_message': str(e),
            'exc_args': e.args
        })
        raise


@celery_app.task(bind=True)
def check_slurm_job_status(self, job_id: str, slurm_host: str):
    try:
        result = subprocess.run(['python', 'slurm_handler.py', 'status', slurm_host, job_id], capture_output=True, text=True)
        
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON output from slurm_handler.py: {str(e)}. Output was: {result.stdout}")
        
        if 'error' in output and output['error']:
            raise Exception(f"Failed to check SLURM job status: {output['error']}")
        
        status = output.get('status')
        if not status:
            raise Exception(f"No status returned from slurm_handler.py. Output was: {output}")
        
        if status == "RUNNING":
            self.update_state(state=states.STARTED, meta={'status': status})
            check_slurm_job_status.apply_async((job_id, slurm_host), countdown=60)
        elif status == "COMPLETED":
            self.update_state(state=states.SUCCESS, meta={'status': status})
        
        return {'status': status}

    except Exception as e:
        logging.exception("Error in check_slurm_job_status task")
        self.update_state(state=states.FAILURE, meta={
            'exc_type': type(e).__name__,
            'exc_message': str(e),
            'exc_args': e.args
        })
        raise


@celery_app.task(bind=True)
def run_album_solution(self, catalog, group, name, version, args_json):
    logger.info(f"Starting task for solution: {catalog}:{group}:{name}:{version}")
    args_dict = json.loads(args_json)
    args_list = [""]
    for key, value in args_dict.items():
        args_list.extend([f"--{key}", value])
    
    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            result = run_solution(catalog, group, name, version, args_list)
        logger.info(f"Task completed successfully. Output: {output.getvalue()}")
        return {"output": output.getvalue(), "result": result}
    except Exception as e:
        logger.error(f"Task failed with error: {str(e)}")
        self.update_state(state=states.FAILURE, meta={
            'exc_type': type(e).__name__,
            'exc_message': str(e),
            'exc_args': e.args
        })
        raise


@celery_app.task
def install_album_solution(catalog, group, name, version):
    return install_solution(catalog, group, name, version)

@celery_app.task
def uninstall_album_solution(catalog, group, name, version):
    return uninstall_solution(catalog, group, name, version)

@celery_app.task
def test_album_solution(catalog, group, name, version):
    return test_solution(catalog, group, name, version)
