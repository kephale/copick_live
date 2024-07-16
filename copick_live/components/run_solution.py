import json
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, State, ALL
from dash.exceptions import PreventUpdate
from copick_live.utils.album_utils import get_catalogs, get_groups, get_names, get_versions, get_solution_args
from copick_live.celery_tasks import submit_slurm_job, check_slurm_job_status

import logging
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

def layout():
    catalogs = get_catalogs()
    
    return html.Div([
        html.H1("Album Solutions"),
        dbc.Form([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Catalog"),
                    dcc.Dropdown(id="catalog-input", options=[{'label': cat['name'], 'value': cat['name']} for cat in catalogs], placeholder="Select catalog"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Group"),
                    dcc.Dropdown(id="group-input", placeholder="Select group"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Name"),
                    dcc.Dropdown(id="name-input", placeholder="Select solution name"),
                ], width=6),
                dbc.Col([
                    dbc.Label("Version"),
                    dcc.Dropdown(id="version-input", placeholder="Select version"),
                ], width=6),
            ]),
            html.Div(id="dynamic-args"),
            dbc.Row([
                dbc.Col([
                    dbc.Button("Run Solution", id="run-solution-button", color="primary", className="mt-3"),
                ], width=6),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id="run-solution-output", className="mt-3"),
                ], width=12),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Input(id="slurm-host-input", type="text", placeholder="Enter SLURM host", className="mb-3"),                    
                    dbc.Button("Submit SLURM Job", id="submit-slurm-button", color="secondary", className="mt-3"),
                    html.Div(id="submit-slurm-output", className="mt-3"),
                ], width=12),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id="solution-output"),
                ], width=12),
            ]),
            dcc.Store(id='task-id-store'),
            dcc.Interval(id='solution-output-interval', interval=1000, n_intervals=0, disabled=True),
        ]),
    ])

@callback(
    Output("group-input", "options"),
    Input("catalog-input", "value")
)
def update_groups(catalog):
    if not catalog:
        return []
    groups = get_groups(catalog)
    return [{'label': group, 'value': group} for group in groups]

@callback(
    Output("name-input", "options"),
    Input("catalog-input", "value"),
    Input("group-input", "value")
)
def update_names(catalog, group):
    if not catalog or not group:
        return []
    names = get_names(catalog, group)
    return [{'label': name, 'value': name} for name in names]

@callback(
    Output("version-input", "options"),
    Input("catalog-input", "value"),
    Input("group-input", "value"),
    Input("name-input", "value")
)
def update_versions(catalog, group, name):
    if not catalog or not group or not name:
        return []
    versions = get_versions(catalog, group, name)
    return [{'label': version, 'value': version} for version in versions]

@callback(
    Output("dynamic-args", "children"),
    Input("catalog-input", "value"),
    Input("group-input", "value"),
    Input("name-input", "value"),
    Input("version-input", "value")
)
def update_dynamic_args(catalog, group, name, version):
    if not catalog or not group or not name or not version:
        return []
    
    args = get_solution_args(catalog, group, name, version)
    
    arg_inputs = []
    for arg in args:
        arg_inputs.append(dbc.Row([
            dbc.Col([
                dbc.Label(f"{arg['name']} ({arg['type']}){'*' if arg.get('required') else ''}"),
                dcc.Input(id={'type': 'arg-input', 'index': arg['name']}, type="text", placeholder=arg.get('default', ''), className="form-control")
            ], width=12)
        ]))
    return arg_inputs

@callback(
    Output("submit-slurm-output", "children"),
    Input("submit-slurm-button", "n_clicks"),
    State("catalog-input", "value"),
    State("group-input", "value"),
    State("name-input", "value"),
    State("version-input", "value"),
    State("slurm-host-input", "value"),
    State({"type": "arg-input", "index": ALL}, "value"),
    State({"type": "arg-input", "index": ALL}, "id"),
    prevent_initial_call=True
)
def submit_slurm(n_clicks, catalog, group, name, version, slurm_host, arg_values, arg_ids):
    logger.info(f"submit_slurm function called. n_clicks: {n_clicks}")
    if not n_clicks:
        logger.info("No clicks detected, preventing update")
        raise PreventUpdate

    if not all([catalog, group, name, version, slurm_host]):
        logger.warning("Missing required inputs for SLURM job submission")
        return "Please fill in all required fields (catalog, group, name, version, SLURM host)"

    args = {}
    for arg_id, arg_value in zip(arg_ids, arg_values):
        if arg_value:
            args[arg_id['index']] = arg_value
    
    # Convert the arguments to album format for the command line
    args_str = ' '.join([f'--{k} {v}' for k, v in args.items()])
    
    logger.info(f"Submitting SLURM job for {catalog}:{group}:{name}:{version} on {slurm_host} with args: {args_str}")
    try:
        task = submit_slurm_job.delay(catalog, group, name, version, slurm_host, args=args_str)
        logger.info(f"SLURM job submission task created with ID: {task.id}")
        return dcc.Loading(id="loading-submit-slurm", children=[
            html.Div(f"SLURM job submission started with task ID: {task.id}"),
            dcc.Interval(id='slurm-output-interval', interval=1000, n_intervals=0),
            html.Div(id='slurm-status-output'),
            dcc.Store(id='slurm-task-id-store', data=str(task.id))
        ])
    except Exception as e:
        logger.exception("Error occurred while submitting SLURM job")
        return f"An error occurred while submitting the SLURM job: {str(e)}"

@callback(
    Output("slurm-status-output", "children"),
    Input("slurm-output-interval", "n_intervals"),
    State("slurm-task-id-store", "data"),
    prevent_initial_call=True
)
def update_slurm_status(n_intervals, task_id):
    if task_id:
        task = check_slurm_job_status.AsyncResult(str(task_id))
        logger.info(f"SLURM status task {task_id} state: {task.state}")
        if task.state == 'PENDING':
            return 'Checking SLURM job status...'
        elif task.state == 'STARTED':
            status = task.info.get('status', 'Unknown')
            return f'SLURM job status: {status}'
        elif task.state == 'SUCCESS':
            status = task.result.get('status', 'Unknown')
            output = task.result.get('output', '')
            if status == "COMPLETED" or status == 'SUCCESS':
                return html.Div([
                    html.P(f"SLURM job completed"),
                    html.H4("Job Output:"),
                    html.Pre(output)
                ])
            else:
                return f'SLURM job status: {status}'
        elif task.state == 'FAILURE':
            return f'Failed to check SLURM job status: {str(task.result)}'
        else:
            return f'Unknown task state: {task.state}'
    return ''
