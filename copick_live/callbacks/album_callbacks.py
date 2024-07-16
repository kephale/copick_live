from dash import Input, Output, State, callback, ALL, dcc, html
from copick_live.celery_tasks import run_album_solution, submit_slurm_job
import json

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
        return dcc.Loading(id="loading-run-solution", children=[
            html.Div(f"Solution started with task ID: {task.id}"),
            dcc.Interval(id='solution-output-interval', interval=1000, n_intervals=0),
            html.Div(id='solution-output'),
            dcc.Store(id='task-id-store', data=str(task.id))  # Ensure task.id is stored as a string
        ])
    return ""

@callback(
    Output("solution-output", "children"),
    Input("solution-output-interval", "n_intervals"),
    State("task-id-store", "data"),
    prevent_initial_call=True
)
def update_solution_output(n_intervals, task_id):
    if task_id:
        task = run_album_solution.AsyncResult(str(task_id))
        if task.state == 'PENDING':
            return 'Task is pending...'
        elif task.state != 'FAILURE':
            if task.result:
                return html.Pre(task.result['output'])
            else:
                return 'Task is in progress...'
        else:
            return f'Task failed: {str(task.result)}'
    return ''
