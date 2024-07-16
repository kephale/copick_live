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
from copick_live.album_utils import run_solution, install_solution, uninstall_solution, test_solution


from celery import Celery

celery_app = Celery('album_server', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

album_instance = Album.Builder().build()
album_instance.load_or_create_collection()

@celery_app.task(bind=True)
def submit_slurm_job(self, catalog: str, group: str, name: str, version: str, gpus: int = 0, cpus: int = 24, memory: str = "125G", args: Optional[str] = None):
    job_name = f"{catalog}_{group}_{name}_{version}"
    
    args_str = args if args else ""
    album_command = f"album run {catalog}:{group}:{name}:{version} {args_str}"
    
    metadata = {
        'album_solution': f"{catalog}:{group}:{name}:{version}",
        'args': args_str,
        'submission_time': datetime.utcnow().isoformat()
    }

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

    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.sh') as temp_script:
        temp_script.write(sbatch_script.strip())
        temp_script_path = temp_script.name

    try:
        print(f"Submitting SLURM job with script: {sbatch_script}")
        process = subprocess.Popen(['sbatch', temp_script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise Exception(f"Failed to submit SLURM job: {stderr.decode()}\nScript: {sbatch_script}")
        job_id = stdout.decode().strip().split()[-1]
        print(f"SLURM job submitted with job ID: {job_id}")
        metadata['slurm_job_id'] = job_id
        self.update_state(state=states.PENDING, meta=metadata)
        check_slurm_job_status.apply_async((self.request.id, job_id), countdown=60, kwargs={'metadata': metadata})
        return metadata
    finally:
        os.remove(temp_script_path)

@celery_app.task(bind=True)
def check_slurm_job_status(self, celery_task_id: str, job_id: str, metadata: Optional[dict] = None):
    print(f"Checking status for SLURM job ID: {job_id}")
    process = subprocess.Popen(['squeue', '--job', job_id, '--noheader'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if metadata is None:
        metadata = {}
    if process.returncode != 0 or not stdout:
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

@celery_app.task
def run_album_solution(catalog, group, name, version, args_json):
    args_dict = json.loads(args_json)
    args_list = [""]
    for key, value in args_dict.items():
        args_list.extend([f"--{key}", value])
    
    return run_solution(catalog, group, name, version, args_list)

@celery_app.task
def install_album_solution(catalog, group, name, version):
    return install_solution(catalog, group, name, version)

@celery_app.task
def uninstall_album_solution(catalog, group, name, version):
    return uninstall_solution(catalog, group, name, version)

@celery_app.task
def test_album_solution(catalog, group, name, version):
    return test_solution(catalog, group, name, version)
