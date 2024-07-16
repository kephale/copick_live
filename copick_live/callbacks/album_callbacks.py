from dash import Input, Output, State, callback
from copick_live.celery_tasks import run_album_solution, submit_slurm_job

@callback(
    Output("run-solution-output", "children"),
    Input("run-solution-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State("args-input", "value"),
    prevent_initial_call=True
)
def run_solution(n_clicks, catalog, group, name, version, args):
    if n_clicks:
        task = run_album_solution.delay(catalog, group, name, version, args)
        return f"Solution started with task ID: {task.id}"
    return ""

@callback(
    Output("submit-slurm-output", "children"),
    Input("submit-slurm-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State("gpus-input", "value"),
    State("cpus-input", "value"),
    State("memory-input", "value"),
    State("args-input", "value"),
    prevent_initial_call=True
)
def submit_slurm_job_callback(n_clicks, catalog, group, name, version, gpus, cpus, memory, args):
    if n_clicks:
        task = submit_slurm_job.delay(catalog, group, name, version, gpus, cpus, memory, args)
        return f"SLURM job submitted with task ID: {task.id}"
    return ""
