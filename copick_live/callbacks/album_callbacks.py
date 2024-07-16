from dash import Input, Output, State, callback, ALL
from copick_live.celery_tasks import run_album_solution, submit_slurm_job

@callback(
    Output("run-solution-output", "children"),
    Input("run-solution-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State({"type": "arg-input", "index": ALL}, "value"),
    State({"type": "arg-input", "index": ALL}, "id"),
    prevent_initial_call=True
)
def run_solution(n_clicks, catalog, group, name, version, arg_values, arg_ids):
    if n_clicks:
        args = {}
        for arg_id, arg_value in zip(arg_ids, arg_values):
            if arg_value:
                args[arg_id['index']] = arg_value
        task = run_album_solution.delay(catalog, group, name, version, json.dumps(args))
        return f"Solution started with task ID: {task.id}"
    return ""

@callback(
    Output("submit-slurm-output", "children"),
    Input("submit-slurm-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State({"type": "arg-input", "index": ALL}, "value"),
    State({"type": "arg-input", "index": ALL}, "id"),
    prevent_initial_call=True
)
def submit_slurm_job_callback(n_clicks, catalog, group, name, version, arg_values, arg_ids):
    if n_clicks:
        args = {}
        for arg_id, arg_value in zip(arg_ids, arg_values):
            if arg_value:
                args[arg_id['index']] = arg_value
        task = submit_slurm_job.delay(catalog, group, name, version, json.dumps(args))
        return f"SLURM job submitted with task ID: {task.id}"
    return ""
